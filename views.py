from app import app, db
from models import Post, Mention, User
from auth import load_user
from twitter_plugin import TwitterClient
from webmention_plugin import MentionClient
from push_plugin import PushClient
from facebook_plugin import FacebookClient

import webmention_receiver

from datetime import datetime
import os
import re
import requests
import pytz
from sqlalchemy import cast as sqlcast

from flask import request, redirect, url_for, render_template,\
    flash, abort, make_response, jsonify, Markup
from flask.ext.login import login_required, login_user,\
    logout_user, current_user
from bs4 import BeautifulSoup, Comment

from werkzeug import secure_filename

TIMEZONE = pytz.timezone('US/Pacific')

twitter_client = TwitterClient(app)
facebook_client = FacebookClient(app)
mention_client = MentionClient(app)
push_client = PushClient(app)


class DisplayPost:

    @classmethod
    def get_posts(cls, post_type, page, per_page):
        query = Post.query
        if post_type:
            query = query.filter_by(post_type=post_type)
        query = query.order_by(Post.pub_date.desc())
        pagination = query.paginate(page, per_page)
        return pagination, [cls(post) for post in pagination.items]

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    def markdown_filter(self, data):
        from markdown import markdown
        from smartypants import smartypants
        return smartypants(markdown(data, extensions=['codehilite']))

    def plain_text_filter(self, plain):
        plain = re.sub(r'\b(?<!href=.)https?://([a-zA-Z0-9/\.\-_:%?@$#&=]+)',
                       r'<a href="\g<0>">\g<1></a>', plain)
        plain = re.sub(r'(?<!\w)@([a-zA-Z0-9_]+)',
                       r'<a href="http://twitter.com/\g<1>">\g<0></a>', plain)
        plain = plain.replace('\n', '<br/>')
        return plain

    def repost_preview_filter(self, url):
        #youtube embeds
        m = re.match(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)', url)
        if m:
            preview = """<iframe width="560" height="315" """
            """src="//www.youtube.com/embed/{}" frameborder="0" """
            """allowfullscreen></iframe>"""\
                .format(m.group(1))
            return preview, True

        #instagram embeds
        m = re.match(r'https?://instagram\.com/p/(\w+)/?#?', url)
        if m:
            preview = """<iframe src="//instagram.com/p/{}/embed/" """
            """width="400" height="500" frameborder="0" scrolling="no" """
            """allowtransparency="true"></iframe>"""\
                .format(m.group(1))
            return preview, True

        preview = twitter_client.repost_preview(self.author, url)
        if preview:
            return preview, True

        #fallback
        m = re.match(r'https?://(.*)', url)
        if m:
            preview = """<a href="{}" class="u-repost u-repost-of">{}</a>"""\
                .format(url, m.group(1))
            return preview, False

        # TODO when the post is first created, we should fetch the
        # reposted URL and save some information about it (i.e.,
        # information we can't get from the page title, whether it is an
        # image, etc.)

    def format_text(self, text):
        if self.content_format == 'markdown':
            return self.markdown_filter(text)
        elif self.content_format == 'plain':
            return self.plain_text_filter(text)
        else:
            return text

    def add_preview(self, text):
        preview = self.repost_preview

        if not preview and self.repost_source:
            preview, cache = self.repost_preview_filter(self.repost_source)
            if preview and cache:
                self.wrapped.repost_preview = preview
                db.session.commit()

        if preview:
            text += '<div>' + preview + '</div>'

        return text

    @property
    def html_content(self):
        return Markup(self.get_html_content(True))

    def get_html_content(self, include_preview=True):
        text = self.format_text(self.content)
        if include_preview:
            text = self.add_preview(text)
        return text

    @property
    def html_excerpt(self):
        text = self.format_text(self.content)
        split = text.split('<!-- more -->', 1)
        text = self.add_preview(split[0])
        if len(split) > 1:
            text += "<br/><a href={}>Keep Reading...</a>"\
                . format(self.permalink_url)
        return Markup(text)


def render_posts(title, post_type, page, per_page):
    pagination, posts = DisplayPost.get_posts(post_type, page, per_page)
    return render_template('posts.html', pagination=pagination,
                           posts=posts, post_type=post_type, title=title,
                           authenticated=current_user.is_authenticated())


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    return render_posts(None, None, page, 30)


@app.route('/articles', defaults={'page': 1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', 'article', page, 10)


@app.route('/notes', defaults={'page': 1})
@app.route('/notes/page/<int:page>')
def notes(page):
    return render_posts('All Notes', 'note', page, 30)


def render_posts_atom(title, post_type, count):
    _, posts = DisplayPost.get_posts(post_type, 1, count)
    return make_response(render_template('posts.atom', title=title,
                                         posts=posts), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route("/all.atom")
def all_atom():
    return render_posts_atom('All Posts', None, 30)


@app.route("/notes.atom")
def notes_atom():
    return render_posts_atom('Notes', 'note', 30)


@app.route("/articles.atom")
def articles_atom():
    return render_posts_atom('Articles', 'article', 10)


@app.route('/<post_type>/<int:year>/<int:month>/<int:day>/<int:index>', defaults={'slug': None})
@app.route('/<post_type>/<int:year>/<int:month>/<int:day>/<int:index>/<slug>')
def post_by_date(post_type, year, month, day, index, slug):
    post = Post.lookup_post_by_date(post_type, year, month, day, index)
    if not post:
        abort(404)

    dpost = DisplayPost(post)
    return render_template('post.html', post=dpost, title=dpost.title,
                           authenticated=current_user.is_authenticated())

@app.route('/<post_type>/<int:year>/<int:dbid>', defaults={'slug': None})
@app.route('/<post_type>/<int:year>/<int:dbid>/<slug>')
def post_by_id(post_type, year, dbid, slug):
    post = Post.lookup_post_by_id(dbid)
    if not post:
        abort(404)

    dpost = DisplayPost(post)
    return render_template('post.html', post=dpost, title=dpost.title,
                           authenticated=current_user.is_authenticated())


@app.route("/indieauth")
def indie_auth():
    token = request.args.get('token')
    response = requests.get('http://indieauth.com/verify',
                            params={'token': token})

    if response.status_code == 200:
        domain = response.json().get('me')
        user = load_user(domain)
        if user:
            login_user(user, remember=True)
            flash('Logged in {} with domain {}'.format(user.login, domain))
        else:
            flash('No user for domain {}'.format(domain))

    else:
        respjson = response.json()
        flash('Login failed {}: {}'.format(respjson.get('error'),
                                           respjson.get('error_description')))

    return redirect(url_for('index'))


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin/settings')
@login_required
def settings():
    return render_template("settings.html", user=current_user,
                           authenticated=current_user.is_authenticated())


@app.route('/admin/delete/<post_type>/<post_id>')
@login_required
def delete_by_id(post_type, post_id):

    if post_type == 'mention':
        post = Mention.query.filter_by(id=post_id).first()
    else:
        post = Post.query.filter_by(id=post_id).first()

    if not post:
        abort(404)

    db.session.delete(post)
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


def handle_new_or_edit(request, post):
    if request.method == 'POST':
        # populate the Post object and save it to the database,
        # redirect to the view
        post.title = request.form.get('title', '')
        post.content = request.form.get('content')
        post.slug = request.form.get('slug')
        post.in_reply_to = request.form.get('in_reply_to', '')
        post.repost_source = request.form.get('repost_source', '')
        post.content_format = request.form.get('content_format', 'plain')
        if not post.pub_date:
            post.pub_date = datetime.utcnow()

        # generate the date/index identifier
        if not post.date_index:
            post.date_index = 1
            same_day_posts = Post.query\
                             .filter(Post.post_type == post.post_type,
                                     sqlcast(Post.pub_date, db.Date) == post.pub_date.date())\
                             .all()
            if same_day_posts:
                post.date_index += max(post.date_index for post in same_day_posts)

        send_to_twitter = request.form.get("send_to_twitter")
        send_to_facebook = request.form.get("send_to_facebook")

        twitter_status_id = request.form.get("twitter_status_id")
        if not send_to_twitter and twitter_status_id:
            post.twitter_status_id = twitter_status_id

        facebook_post_id = request.form.get("facebook_post_id")
        if not send_to_facebook and facebook_post_id:
            post.facebook_post_id = facebook_post_id

        if not post.id:
            db.session.add(post)
        db.session.commit()

        # TODO everything else could be asynchronous
        # post or update this post on twitter
        if send_to_twitter:
            try:
                twitter_client.handle_new_or_edit(post)
                db.session.commit()
            except:
                flash("error while posting to twitter")
                app.logger.exception('posting to twitter')

        if send_to_facebook:
            try:
                facebook_client.handle_new_or_edit(post)
                db.session.commit()
            except:
                flash("error while posting to facebook")
                app.logger.exception('posting to facebook')

        try:
            push_client.handle_new_or_edit(post)
        except:
            flash("error while sending PuSH")
            app.logger.exception('posting to PuSH')

        try:
            mention_client.handle_new_or_edit(post)
            db.session.commit()
        except:
            flash("error sending webmentions")
            app.logger.exception('sending webmentions')

        return redirect(post.permalink_url)

    return render_template('edit_post.html', post=post,
                           authenticated=current_user.is_authenticated())


@app.route('/admin/new/<post_type>', methods=['GET', 'POST'])
@login_required
def new_post(post_type):
    author = User.query.first()
    content_format = 'plain' if post_type == 'note' else 'markdown'

    date = datetime.utcnow()
    post = Post('', '', '', post_type, content_format, author,
                date)
    return handle_new_or_edit(request, post)


@app.route('/admin/edit/<post_type>/<post_id>', methods=['GET', 'POST'])
@login_required
def edit_by_id(post_type, post_id):
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        abort(404)
    return handle_new_or_edit(request, post)


@app.template_filter('strftime')
def strftime_filter(date, fmt='%Y %b %d'):
    if date:
        localdate = pytz.utc.localize(date).astimezone(TIMEZONE)
        return localdate.strftime(fmt)


@app.template_filter('isotime')
def isotime_filter(date):
    if date:
        utctime = pytz.utc.localize(date)
        return utctime.isoformat('T')


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page


@app.template_filter('html_to_plain')
def html_to_plain(content):
    soup = BeautifulSoup(str(content))
    text = soup.get_text()
    return Markup.escape(text)


@app.template_filter('atom_sanitize')
def atom_sanitize(content):
    soup = BeautifulSoup(str(content))
    for tag in soup.find_all('script'):
        tag.replace_with(soup.new_string('removed script tag', Comment))
    result = Markup(soup)
    return result


@app.route('/admin/upload', methods=['POST'])
@login_required
def receive_upload():
    file = request.files['file']
    filename = secure_filename(file.filename)
    now = datetime.utcnow()
    directory = os.path.join('static', 'uploads',
                             str(now.year), str(now.month).zfill(2))
    path = os.path.join(directory, filename)
    if not os.path.exists(directory):
        os.makedirs(directory)
    file.save(path)
    return jsonify({'path': '/' + path})


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    source = request.form.get('source')
    target = request.form.get('target')

    app.logger.debug("Webmention from %s to %s received", source, target)

    result = webmention_receiver.process_webmention(source, target)
    if not result:
        abort(404)
    return result
