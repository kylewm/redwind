from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask import current_app
from flask.ext.login import current_user, login_required
from flask.ext.micropub import MicropubClient

import mf2py
import mf2util
import requests

from redwind import hooks
from redwind import util
from redwind.models import get_settings, Post, PosseTarget
from redwind.extensions import db
from redwind.tasks import get_queue, async_app_context


posse = Blueprint('posse', __name__, url_prefix='/posse',)
micropub = MicropubClient(client_id='https://github.com/kylewm/redwind')


def register(app):
    app.register_blueprint(posse)
    micropub.init_app(app)
    hooks.register('post-saved', syndicate)


@posse.context_processor
def inject_settings_variable():
    return {
        'settings': get_settings()
    }


@posse.route('/')
@login_required
def index():
    return render_template('posse/index.jinja2')


@posse.route('/add', methods=['POST'])
@login_required
def add():
    me = request.form.get('me')
    state = '|'.join((request.form.get('style', ''),
                      request.form.get('name', '')))
    return micropub.authorize(me, scope='post', state=state)


@posse.route('/callback')
@micropub.authorized_handler
def callback(info):
    if info.error:
        flash('Micropub failure: {}'.format(info.error))
    else:
        flash('Micropub success! Authorized {}'.format(info.me))

    p = mf2py.parse(url=info.me)
    hcard = mf2util.representative_hcard(p, source_url=info.me)
    author = mf2util.parse_author(hcard)

    current_app.logger.debug('found author info %s', author)

    target = PosseTarget(
        me=info.me,
        name=author.get('name'),
        photo=author.get('photo'),
        style='microblog',
        micropub_endpoint=info.micropub_endpoint,
        access_token=info.access_token)
    current_user.posse_targets.append(target)
    db.session.commit()
    return redirect(url_for('.edit', target_id=target.id))


@posse.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'GET':
        target_id = request.args.get('target_id')
        target = PosseTarget.query.get(target_id)
        return render_template('posse/edit.jinja2', target=target)

    target_id = request.form.get('target_id')
    target = PosseTarget.query.get(target_id)
    target.name = request.form.get('name')
    target.style = request.form.get('style')
    db.session.commit()
    return redirect(url_for('.edit', target_id=target_id))


@posse.route('/delete', methods=['POST'])
@login_required
def delete():
    target_id = request.form.get('target_id')
    target = PosseTarget.query.get(target_id)
    db.session.delete(target)
    db.session.commit()
    return redirect(url_for('.index'))


def syndicate(post, args):
    for target_name in args.getlist('syndicate-to'):
        if target_name.startswith('posse:'):
            target_id = target_name[len('posse:'):]
            get_queue().enqueue(do_syndicate, post.id, target_id,
                                current_app.config)


def do_syndicate(post_id, target_id, app_config):
    with async_app_context(app_config):
        post = Post.query.get(post_id)
        target = PosseTarget.query.get(target_id)

        data = {'access_token': target.access_token}
        files = None

        if post.repost_of:
            data['repost-of'] = post.repost_of[0]
        if post.like_of:
            data['like-of'] = post.like_of[0]
        if post.in_reply_to:
            data['in-reply-to'] = post.in_reply_to[0]

        if post.post_type == 'review':
            item = post.item or {}
            data['item[name]'] = data['item'] = item.get('name')
            data['item[author]'] = item.get('author')
            data['rating'] = post.rating
            data['description'] = data['description[value]'] = post.content
            data['description[html]'] = post.content_html
        else:
            data['name'] = post.title
            data['content'] = data['content[value]'] = post.content
            data['content[html]'] = post.content_html

        data['url'] = (post.shortlink if target.style == 'microblog'
                       else post.permalink)

        if post.post_type == 'photo' and post.attachments:
            if len(post.attachments) == 1:
                a = post.attachments[0]
                files = {'photo': (a.filename, open(a.disk_path(), 'rb'),
                                   a.mimetype)}
            else:
                files = [('photo[]', (a.filename, open(a.disk_path(), 'rb'),
                                      a.mimetype)) for a in post.attachments]

        data['location'] = post.get_location_as_geo_uri()
        data['place-name'] = post.venue and post.venue.name

        categories = [tag.name for tag in post.tags]
        for person in post.people:
            categories.append(person.url)
            if person.social:
                categories += person.social
        data['category[]'] = categories

        resp = requests.post(target.micropub_endpoint,
                             data=util.filter_empty_keys(data), files=files)
        resp.raise_for_status()

        post.add_syndication_url(resp.headers['Location'])
