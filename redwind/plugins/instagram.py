from .. import hooks
from .. import util
from ..extensions import db
from ..models import Post, Setting, get_settings, Context
from ..tasks import get_queue, async_app_context

from flask.ext.login import login_required
from flask import (
    request, redirect, url_for, Blueprint, current_app,
)

import requests
import urllib
import datetime

PERMALINK_RE = util.INSTAGRAM_RE


instagram = Blueprint('instagram', __name__)


def register(app):
    app.register_blueprint(instagram)
    hooks.register('create-context', create_context)
    hooks.register('post-saved', send_to_instagram)


@instagram.route('/authorize_instagram')
@login_required
def authorize_instagram():
    redirect_uri = url_for('.authorize_instagram', _external=True)

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
    current_app.logger.debug('received result %s', result)
    payload = result.json()
    access_token = payload.get('access_token')

    Setting.query.get('instagram_access_token').value = access_token
    db.session.commit()
    return redirect(url_for('admin.edit_settings'))


def create_context(url):
    m = PERMALINK_RE.match(url)
    if not m:
        current_app.logger.debug('url is not an instagram media url %s', url)
        return

    r = ig_get('https://api.instagram.com/v1/media/shortcode/' + m.group(1))

    if r.status_code // 2 != 100:
        current_app.logger.warn(
            "failed to fetch instagram media with shortcode %s %s %s",
            m.group(1), r, r.content)
        return

    blob = r.json()
    author = blob.get('data', {}).get('user', {})
    author_name = author.get('full_name')
    author_image = author.get('profile_picture')
    author_url = author.get('website')
    created_time = blob.get('data', {}).get('created_time')
    caption_text = (blob.get('data', {}).get('caption') or {}).get('text')
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

    current_app.logger.debug('created instagram context %s', context)

    return context


def send_to_instagram(post, args):
    """Share a like or comment to Instagram without user-input.
    """
    if 'instagram' in args.getlist('syndicate-to'):
        if not is_instagram_authorized():
            return False, 'Current user is not authorized for instagram'

        current_app.logger.debug(
            "queueing post to instagram {}".format(post.id))
        get_queue().enqueue(do_send_to_instagram, post.id, current_app.config['CONFIG_FILE'])
        return True, 'Success'


def do_send_to_instagram(post_id, app_config):
    with async_app_context(app_config):
        current_app.logger.debug('posting to instagram %d', post_id)
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
                current_app.logger.warn(
                    "failed to fetch instagram media %s %s", r, r.content)
                return None

            media_id = r.json().get('data', {}).get('id')
            if not media_id:
                current_app.logger.warn(
                    'could not find media id for shortcode %s', shortcode)
                return None

            r = ig_get('https://api.instagram.com/v1/users/self')
            my_username = r.json().get('data', {}).get('username')

            r = ig_post('https://api.instagram.com/v1/media/'
                        + media_id + '/likes')

            if r.status_code // 2 != 100:
                current_app.logger.warn(
                    "failed to POST like for instagram id %s", media_id)
                return None

            like_url = like_of + '#liked-by-' + my_username
            post.add_syndication_url(like_url)
            db.session.commit()
            return like_url

        if in_reply_to:
            comment_text = format_markdown_for_instagram(post.content)
            comment_url = post_comment(in_reply_to, comment_text)
            if comment_url:
                post.add_syndication_url(comment_url)
                db.session.commit()
                return comment_url


def format_markdown_for_instagram(data):
    return util.format_as_text(util.markdown_filter(data))


def post_comment(permalink, comment_text):
    if ('INSTAGRAM_USERNAME' not in current_app.config
            or 'INSTAGRAM_PASSWORD' not in current_app.config):
        return

    from selenium import webdriver
    from selenium.webdriver.common.keys import Keys
    import selenium.webdriver.support.ui as ui
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

    dc = dict(DesiredCapabilities.PHANTOMJS)
    dc['ssl-protocol'] = 'any'

    browser = webdriver.PhantomJS(desired_capabilities=dc)
    wait = ui.WebDriverWait(browser, 10)  # timeout after 10 seconds

    browser.get('https://instagram.com/accounts/login/')

    un = browser.find_element_by_id('lfFieldInputUsername')
    un.send_keys(current_app.config['INSTAGRAM_USERNAME']
                 + Keys.TAB
                 + current_app.config['INSTAGRAM_PASSWORD'])
    un.submit()

    wait.until(lambda b: b.current_url == 'https://instagram.com/')

    browser.get(permalink)

    inp = browser.find_element_by_tag_name('input')
    inp.send_keys(comment_text)
    inp.submit()

    # workaround for https://github.com/SeleniumHQ/selenium/issues/767
    browser.service.process.terminate()
    browser.quit()

    return (permalink + '#comment-by-'
            + current_app.config['INSTAGRAM_USERNAME']
            + '-' + datetime.datetime.now().isoformat())


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
