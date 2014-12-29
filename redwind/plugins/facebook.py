from .. import app
from .. import db
from .. import util
from ..models import Post, Setting, get_settings

from flask.ext.login import login_required
from flask import request, redirect, url_for, render_template, flash,\
    has_request_context

import requests
import json
import urllib


def register():
    pass


@app.route('/authorize_facebook')
@login_required
def authorize_facebook():
    import urllib.parse
    import urllib.request
    redirect_uri = url_for('authorize_facebook', _external=True)
    params = {
        'client_id': get_settings().facebook_app_id,
        'redirect_uri': redirect_uri,
        'scope': 'publish_stream,user_photos',
    }

    code = request.args.get('code')
    if code:
        params['code'] = code
        params['client_secret'] = get_settings().facebook_app_secret

        r = urllib.request.urlopen(
            'https://graph.facebook.com/oauth/access_token?'
            + urllib.parse.urlencode(params))
        payload = urllib.parse.parse_qs(r.read())

        access_token = payload[b'access_token'][0].decode('ascii')
        Setting.query.get('facebook_access_token').value = access_token
        db.session.commit()
        return redirect(url_for('edit_settings'))
    else:
        return redirect('https://graph.facebook.com/oauth/authorize?'
                        + urllib.parse.urlencode(params))


@app.route('/share_on_facebook', methods=['GET', 'POST'])
@login_required
def share_on_facebook():
    from .twitter import collect_images

    if request.method == 'GET':
        post = Post.load_by_id(request.args.get('id'))

        preview = post.title + '\n\n' if post.title else ''
        preview += format_markdown_as_facebook(post.content)
        imgs = [urllib.parse.urljoin(get_settings().site_url, img)
                for img in collect_images(post)]

        albums = []
        if imgs:
            app.logger.debug('fetching user albums')
            resp = requests.get(
                'https://graph.facebook.com/v2.2/me/albums',
                params={'access_token': get_settings().facebook_access_token})
            resp.raise_for_status()
            app.logger.debug('user albums response %s: %s', resp, resp.text)
            albums = resp.json().get('data', [])

        return render_template('admin/share_on_facebook.jinja2', post=post,
                               preview=preview, imgs=imgs, albums=albums)

    try:
        post_id = request.form.get('post_id')
        preview = request.form.get('preview')
        img_url = request.form.get('img')
        post_type = request.form.get('post_type')
        album_id = request.form.get('album')

        if album_id == 'new':
            album_id = create_album(
                request.form.get('new_album_name'),
                request.form.get('new_album_message'))

        post = Post.load_by_id(post_id)
        facebook_url = handle_new_or_edit(post, preview, img_url,
                                          post_type, album_id)
        db.session.commit()
        if has_request_context():
            flash('Shared on Facebook: <a href="{}">Original</a>, '
                  '<a href="{}">On Facebook</a><br/>'
                  .format(post.permalink, facebook_url))
            return redirect(post.permalink)

    except Exception as e:
        if has_request_context():
            app.logger.exception('posting to facebook')
            flash('Share on Facebook Failed! Exception: {}'.format(e))
        return redirect(url_for('index'))


class PersonTagger:
    def __init__(self):
        self.tags = []
        self.taggable_friends = None

    def get_taggable_friends(self):
        if not self.taggable_friends:
            r = requests.get(
                'https://graph.facebook.com/v2.0/me/taggable_friends',
                params={
                    'access_token': get_settings().facebook_access_token
                })
            self.taggable_friends = r.json()

        return self.taggable_friends or {}

    def __call__(self, fullname, displayname, entry, pos):
        fbid = entry.get('facebook')
        if fbid:
            # return '@[' + fbid + ']'
            self.tags.append(fbid)
        return displayname


def create_album(name, msg):
    app.logger.debug('creating new facebook album %s', name)
    resp = requests.post(
        'https://graph.facebook.com/v2.0/me/albums', data={
            'access_token': get_settings().facebook_access_token,
            'name': name,
            'message': msg,
            'privacy': json.dumps({'value': 'EVERYONE'}),
        })
    resp.raise_for_status()
    app.logger.debug('new facebook album response: %s, %s', resp, resp.text)
    return resp.json()['id']


def handle_new_or_edit(post, preview, img_url, post_type,
                       album_id):
    app.logger.debug('publishing to facebook')

    #TODO I cannot figure out how to tag people via the FB API
    #tagger = PersonTagger()
    #preview = util.autolink(preview, url_processor=None, person_processor=tagger)

    post_args = {
        'access_token': get_settings().facebook_access_token,
        'message': preview.strip(),
        'actions': json.dumps({'name': 'See Original',
                               'link': post.permalink}),
        #'privacy': json.dumps({'value': 'SELF'}),
        'privacy': json.dumps({'value': 'EVERYONE'}),
        #'article': post.permalink,
    }

    if post.title:
        post_args['name'] = post.title

    is_photo = False

    share_link = next(iter(post.repost_of), None)
    if share_link:
        post_args['link'] = share_link
    elif img_url:
        if post_type == 'photo':
            is_photo = True  # special case for posting photos
            post_args['url'] = img_url
        else:
            # link back to the original post, and use the image
            # as the preview image
            post_args['link'] = post.permalink
            post_args['picture'] = img_url

    if is_photo:
        app.logger.debug('Sending photo %s to album %s', post_args, album_id)
        response = requests.post(
            'https://graph.facebook.com/v2.0/{}/photos'.format(
                album_id if album_id else 'me'),
            data=post_args)
    else:
        app.logger.debug('Sending post %s', post_args)
        response = requests.post('https://graph.facebook.com/v2.0/me/feed',
                                 data=post_args)
    response.raise_for_status()
    app.logger.debug("Got response from facebook %s", response)

    if 'json' in response.headers['content-type']:
        result = response.json()

    app.logger.debug('published to facebook. response {}'.format(result))
    if result:
        if is_photo:
            facebook_photo_id = result['id']
            facebook_post_id = result['post_id']  # actually the album

            split = facebook_post_id.split('_', 1)
            if split and len(split) == 2:
                user_id, post_id = split
                fb_url = 'https://facebook.com/{}/posts/{}'.format(
                    user_id, facebook_photo_id)
                new_syndication = list(post.syndication)
                new_syndication.append(fb_url)
                post.syndication = new_syndication
                return fb_url

        else:
            facebook_post_id = result['id']
            split = facebook_post_id.split('_', 1)
            if split and len(split) == 2:
                user_id, post_id = split
                fb_url = 'https://facebook.com/{}/posts/{}'.format(
                    user_id, post_id)
                new_syndication = list(post.syndication)
                new_syndication.append(fb_url)
                post.syndication = new_syndication
                return fb_url


def format_markdown_as_facebook(data):
    return util.format_as_text(
        util.markdown_filter(
            data, url_processor=None, person_processor=None))
