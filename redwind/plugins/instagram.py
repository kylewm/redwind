from .. import app
from .. import db
from .. import util
from ..models import Post, Setting, get_settings, Context
from .. import hooks
from .. import queue

from flask.ext.login import login_required
from flask import request, redirect, url_for, render_template, flash,\
    has_request_context

import requests
import urllib
import re
import datetime


PERMALINK_RE = re.compile(r'https?://(?:www\.|mobile\.)?instagram\.com/p/(\w+)/?')


def register():
    hooks.register('create-context', create_context)
    hooks.register('post-saved', send_to_instagram)


@app.route('/authorize_instagram')
@login_required
def authorize_instagram():
    redirect_uri = url_for('authorize_instagram', _external=True)

    code = request.args.get('code')
    if not code:
        # redirect to instagram authorization page
        params = {
            'client_id': get_settings().instagram_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'likes comments',
        }
        return redirect('https://api.instagram.com/oauth/authorize/?'
                        + urllib.parse.urlencode(params))

    params = {
        'client_id': get_settings().instagram_client_id,
        'client_secret': get_settings().instagram_client_secret,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
        'code': code,
    }

    result = requests.post(
        'https://api.instagram.com/oauth/access_token', data=params)
    app.logger.debug('received result %s', result)
    payload = result.json()
    access_token = payload.get('access_token')

    Setting.query.get('instagram_access_token').value = access_token
    db.session.commit()
    return redirect(url_for('edit_settings'))


def create_context(url):
    m = PERMALINK_RE.match(url)
    if not m:
        app.logger.debug('url is not an instagram media url %s', url)
        return

    r = ig_get('https://api.instagram.com/v1/media/shortcode/' + m.group(1))

    if r.status_code // 2 != 100:
        app.logger.warn("failed to fetch instagram media %s %s", r, r.content)
        return

    blob = r.json()
    author = blob.get('data', {}).get('user', {})
    author_name = author.get('full_name')
    author_image = author.get('profile_picture')
    author_url = author.get('website')
    created_time = blob.get('data', {}).get('created_time')
    caption_text = blob.get('data', {}).get('caption', {}).get('text')
    images = blob.get('data', {}).get('images', {})
    image = images.get('standard_resolution').get('url')

    if created_time:
        published = datetime.datetime.fromtimestamp(int(created_time))

    content = ''
    if caption_text:
        content += '<p>' + caption_text + '</p>'
    if image:
        content += '<img src="' + image + '"/>'

    context = Context()
    context.url = context.permalink = url
    context.author_name = author_name
    context.author_image = author_image
    context.author_url = author_url
    context.published = published
    context.title = None
    context.content = content
    context.content_plain = caption_text

    app.logger.debug('created instagram context %s', context)

    return context


def send_to_instagram(post, args):
    """Share a like to Instagram without user-input.
    """
    if 'instagram' in args.getlist('syndicate-to'):
        if not is_instagram_authorized():
            return False, 'Current user is not authorized for instagram'

        app.logger.debug("queueing post to instagram {}".format(post.id))
        queue.enqueue(do_send_to_instagram, post.id)
        return True, 'Success'


def do_send_to_instagram(post_id):
    app.logger.debug('posting to instagram %d', post_id)
    post = Post.load_by_id(post_id)

    in_reply_to, repost_of, like_of \
        = util.posse_post_discovery(post, PERMALINK_RE)

    # likes are the only thing we can POSSE to instagram unfortunately
    if like_of:
        m = PERMALINK_RE.match(like_of)
        shortcode = m.group(1)

        r = ig_get('https://api.instagram.com/v1/media/shortcode/'
                   + m.group(1))

        if r.status_code // 2 != 100:
            app.logger.warn("failed to fetch instagram media %s %s",
                            r, r.content)
            return None

        media_id = r.json().get('data', {}).get('id')
        if not media_id:
            app.logger.warn('could not find media id for shortcode %s',
                            shortcode)
            return None

        r = ig_get('https://api.instagram.com/v1/users/self')
        my_username = r.json().get('data', {}).get('username')

        r = ig_post('https://api.instagram.com/v1/media/'
                    + media_id + '/likes')

        if r.status_code // 2 != 100:
            app.logger.warn("failed to POST like for instagram id %s",
                            media_id)
            return None

        like_url = like_of + '#liked-by-' + my_username
        post.add_syndication_url(like_url)
        db.session.commit()
        return like_url


def ig_get(url):
    return requests.get(url, params={
        'access_token': get_settings().instagram_access_token,
    })


def ig_post(url):
    return requests.post(url, data={
        'access_token': get_settings().instagram_access_token,
    })


def is_instagram_authorized():
    return (hasattr(get_settings(), 'instagram_access_token')
            and get_settings().instagram_access_token)
