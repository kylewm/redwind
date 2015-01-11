from .. import app
from .. import db
from .. import util
from .. import hooks
from .. import queue
from ..models import Post, Setting, get_settings

from flask.ext.login import login_required
from flask import request, redirect, url_for, render_template, flash,\
    has_request_context, make_response

import requests
import json
import urllib.request
import urllib.parse


API_TOKEN_URL = 'https://public-api.wordpress.com/oauth2/token'
API_AUTHORIZE_URL = 'https://public-api.wordpress.com/oauth2/authorize'
API_AUTHENTICATE_URL = 'https://public-api.wordpress.com/oauth2/authenticate'
API_SITE_URL = 'https://public-api.wordpress.com/rest/v1.1/sites/{}'
API_POST_URL = 'https://public-api.wordpress.com/rest/v1.1/sites/{}/posts/{}'
API_NEW_LIKE_URL = 'https://public-api.wordpress.com/rest/v1.1/sites/{}/posts/{}/likes/new'
API_NEW_REPLY_URL = 'https://public-api.wordpress.com/rest/v1.1/sites/{}/posts/{}/replies/new'
API_ME_URL = 'https://public-api.wordpress.com/rest/v1.1/me'


def register():
    hooks.register('post-saved', send_to_wordpress)


@app.route('/install_wordpress')
@login_required
def install():
    settings = [
        Setting(key='wordpress_client_id', name='WordPress Client ID'),
        Setting(key='wordpress_client_secret', name='WordPress Client Secret'),
        Setting(key='wordpress_access_token', name='WordPress Access Token'),
    ]

    for s in settings:
        if not Setting.query.get(s.key):
            db.session.add(s)
    db.session.commit()

    return 'Success'


@app.route('/authorize_wordpress')
@login_required
def authorize_wordpress():
    redirect_uri = url_for('authorize_wordpress', _external=True)

    code = request.args.get('code')
    if code:
        r = requests.post(API_TOKEN_URL, data={
            'client_id': get_settings().wordpress_client_id,
            'redirect_uri': redirect_uri,
            'client_secret': get_settings().wordpress_client_secret,
            'code': code,
            'grant_type': 'authorization_code',
        })

        if r.status_code // 100 != 2:
            return make_response(
                'Code: {}. Message: {}'.format(r.status_code, r.text),
                r.status_code)

        payload = r.json()

        access_token = payload.get('access_token')
        Setting.query.get('wordpress_access_token').value = access_token
        db.session.commit()
        return redirect(url_for('edit_settings'))
    else:
        return redirect(API_AUTHORIZE_URL + '?' + urllib.parse.urlencode({
            'client_id': get_settings().wordpress_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'global',
        }))


def send_to_wordpress(post, args):
    if 'wordpress' in args.getlist('syndicate-to'):
        queue.enqueue(do_send_to_wordpress, post.id)


def do_send_to_wordpress(post_id):
    post = Post.load_by_id(post_id)

    if post.like_of:
        for url in post.like_of:
            try_post_like(url, post)

    elif post.in_reply_to:
        for url in post.in_reply_to:
            try_post_reply(url, post)


def try_post_like(url, post):
    app.logger.debug('wordpress. posting like to %s', url)
    myid = find_my_id()
    siteid, postid = find_post_id(url)
    app.logger.debug('wordpress. posting like to site-id %d, post-id %d',
                     siteid, postid)
    if myid and siteid and postid:
        endpoint = API_NEW_LIKE_URL.format(siteid, postid)
        app.logger.debug('wordpress: POST to endpoint %s', endpoint)
        r = requests.post(endpoint, headers={
            'authorization': 'Bearer ' + get_settings().wordpress_access_token,
        })
        r.raise_for_status()
        if r.json().get('success'):
            wp_url = '{}#liked-by-{}'.format(url, myid)
            post.add_syndication_url(wp_url)
            db.session.commit()
            return wp_url

        app.logger.error(
            'failed to post wordpress like. response: %r: %r', r, r.text)


def try_post_reply(url, post):
    app.logger.debug('wordpress. posting reply to %s', url)
    myid = find_my_id()
    siteid, postid = find_post_id(url)
    app.logger.debug('wordpress. posting reply to site-id %d, post-id %d',
                     siteid, postid)
    if myid and siteid and postid:
        endpoint = API_NEW_REPLY_URL.format(siteid, postid)
        app.logger.debug('wordpress: POST to endpoint %s', endpoint)
        r = requests.post(endpoint, headers={
            'authorization': 'Bearer ' + get_settings().wordpress_access_token,
        }, data={
            'content': post.content_html,
        })
        r.raise_for_status()
        wp_url = r.json().get('URL')
        if wp_url:
            post.add_syndication_url(wp_url)
            db.session.commit()
            return wp_url

        app.logger.error(
            'failed to post wordpress reply. response: %r: %r', r, r.text)


def find_my_id():
    r = requests.get(API_ME_URL, headers={
        'authorization': 'Bearer ' + get_settings().wordpress_access_token,
    })
    r.raise_for_status()
    return r.json().get('ID')


def find_post_id(url):
    p = urllib.parse.urlparse(url)

    slug = list(filter(None, p.path.split('/')))[-1]

    r = requests.get(API_POST_URL.format(p.netloc, 'slug:' + slug))
    r.raise_for_status()
    blob = r.json()

    return blob.get('site_ID'), blob.get('ID')
