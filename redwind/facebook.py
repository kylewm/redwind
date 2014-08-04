from . import app
from .models import Post

from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, render_template

import requests
import json
import urllib


@app.route('/authorize_facebook')
@login_required
def authorize_facebook():
    import urllib.parse
    import urllib.request
    redirect_uri = app.config.get('SITE_URL') + '/authorize_facebook'
    params = {'client_id': app.config.get('FACEBOOK_APP_ID'),
              'redirect_uri': redirect_uri,
              'scope': 'publish_stream,user_photos'}

    code = request.args.get('code')
    if code:
        params['code'] = code
        params['client_secret'] = app.config.get('FACEBOOK_APP_SECRET')

        r = urllib.request.urlopen(
            'https://graph.facebook.com/oauth/access_token?'
            + urllib.parse.urlencode(params))
        payload = urllib.parse.parse_qs(r.read())

        access_token = payload[b'access_token'][0].decode('ascii')
        current_user.facebook_access_token = access_token
        current_user.save()
        return redirect(url_for('settings'))
    else:
        return redirect('https://graph.facebook.com/oauth/authorize?'
                        + urllib.parse.urlencode(params))


@app.route('/share_on_facebook', methods=['GET', 'POST'])
@login_required
def share_on_facebook():
    from .twitter import collect_images

    if request.method == 'GET':
        post = Post.load_by_shortid(request.args.get('id'))

        preview = post.title + '\n\n' if post.title else ''
        preview += format_markdown_as_facebook(post.content)
        imgs = [urllib.parse.urljoin(app.config['SITE_URL'], img)
                for img in collect_images(post)]

        albums = []
        if imgs:
            app.logger.debug('fetching user albums')
            resp = requests.get(
                'https://graph.facebook.com/v2.0/me/albums',
                params={'access_token': current_user.facebook_access_token})
            resp.raise_for_status()
            app.logger.debug('user albums response %s: %s', resp, resp.text)
            albums = resp.json().get('data', [])

        return render_template('share_on_facebook.html', post=post,
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

        with Post.writeable(Post.shortid_to_path(post_id)) as post:
            facebook_url = handle_new_or_edit(post, preview, img_url,
                                              post_type, album_id)
            post.save()

            return """Shared on Facebook<br/>
            <a href="{}">Original</a><br/>
            <a href="{}">On Facebook</a><br/>
            """.format(post.permalink, facebook_url)

    except Exception as e:
        app.logger.exception('posting to facebook')
        return """Share on Facebook Failed!<br/>Exception: {}""".format(e)


class PersonTagger:
    def __init__(self):
        self.tags = []
        self.taggable_friends = None

    def get_taggable_friends(self):
        if not self.taggable_friends:
            r = requests.get(
                'https://graph.facebook.com/v2.0/me/taggable_friends',
                params={
                    'access_token': current_user.facebook_access_token
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
            'access_token': current_user.facebook_access_token,
            'name': name,
            'message': msg,
            'privacy': json.dumps({'value': 'EVERYONE'}),
        })
    resp.raise_for_status()
    app.logger.debug('new facebook album response: %s, %s', resp, resp.text)
    return resp.json()['id']


def handle_new_or_edit(post, preview, img_url, post_type,
                       album_id):
    from .controllers import process_people
    app.logger.debug('publishing to facebook')

    tagger = PersonTagger()
    preview = process_people(preview, tagger)

    post_args = {
        'access_token': current_user.facebook_access_token,
        'message': preview.strip(),
        'actions': json.dumps({'name': 'See Original', 'link': post.permalink}),
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
                post.syndication.append(fb_url)
                return fb_url

        else:
            facebook_post_id = result['id']
            split = facebook_post_id.split('_', 1)
            if split and len(split) == 2:
                user_id, post_id = split
                fb_url = 'https://facebook.com/{}/posts/{}'.format(
                    user_id, post_id)
                post.syndication.append(fb_url)
                return fb_url


def format_markdown_as_facebook(data):
    from .controllers import markdown_filter, format_as_text
    return format_as_text(
        markdown_filter(data, link_twitter_names=False,
                        person_processor=None))
