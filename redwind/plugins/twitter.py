from .. import app
from .. import db
from .. import hooks
from .. import queue
from .. import util
from ..models import Post, Context, Setting, get_settings

from flask.ext.login import login_required
from flask import request, redirect, url_for, make_response,\
    render_template, flash, abort, has_request_context

import collections
import requests
import re
import json
import datetime

from tempfile import mkstemp
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from mf2py.parser import Parser as Mf2Parser

from requests_oauthlib import OAuth1Session, OAuth1
from requests.exceptions import HTTPError

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
AUTHORIZE_URL = 'https://api.twitter.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'

URL_CHAR_LENGTH = 23
MEDIA_CHAR_LENGTH = 23
TWEET_CHAR_LENGTH = 140

TweetComponent = collections.namedtuple('TweetComponent', [
    'length',
    'can_shorten',
    'can_drop',
    'text',
])

PERMALINK_RE = util.TWITTER_RE


def register():
    hooks.register('create-context', create_context)
    hooks.register('post-saved', send_to_twitter)


@app.route('/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    callback_url = url_for('twitter_callback', _external=True)
    try:
        oauth = OAuth1Session(
            client_key=get_settings().twitter_api_key,
            client_secret=get_settings().twitter_api_secret,
            callback_uri=callback_url)

        oauth.fetch_request_token(REQUEST_TOKEN_URL)
        return redirect(oauth.authorization_url(AUTHORIZE_URL))

    except requests.RequestException as e:
        return make_response(str(e))


@app.route('/twitter_callback')
def twitter_callback():
    """Receive the request token from Twitter and convert it to an
       access token"""
    try:
        oauth = OAuth1Session(
            client_key=get_settings().twitter_api_key,
            client_secret=get_settings().twitter_api_secret)
        oauth.parse_authorization_response(request.url)

        response = oauth.fetch_access_token(ACCESS_TOKEN_URL)
        access_token = response.get('oauth_token')
        access_token_secret = response.get('oauth_token_secret')

        Setting.query.get('twitter_oauth_token').value = access_token
        Setting.query.get('twitter_oauth_token_secret').value = access_token_secret

        db.session.commit()
        return redirect(url_for('edit_settings'))
    except requests.RequestException as e:
        return make_response(str(e))


def collect_images(post):
    """collect the images (if any) that are in an <img> tag
    in the rendered post"""

    if post.photos:
        for photo in post.photos:
            yield post.photo_url(photo)

    else:
        html = util.markdown_filter(
            post.content, img_path=post.get_image_path(),
            url_processor=None, person_processor=None)
        soup = BeautifulSoup(html)
        for img in soup.find_all('img'):
            if not img.find_parent(class_='h-card'):
                src = img.get('src')
                if src:
                    yield urljoin(get_settings().site_url, src)


def send_to_twitter(post, args):
    """Share a note to twitter without user-input. Makes a best-effort
    attempt to guess the appropriate parameters and content
    """
    if args.get('action') == 'publish+tweet':
        if not is_twitter_authorized():
            return False, 'Current user is not authorized to tweets'

        try:
            app.logger.debug("auto-posting to twitter {}".format(post.id))
            queue.enqueue(do_send_to_twitter, post.id)
            return True, 'Success'

        except Exception as e:
            app.logger.exception('auto-posting to twitter')
            return False, 'Exception while auto-posting to twitter: {}'.format(e)


def do_send_to_twitter(post_id):
    with app.app_context():
        app.logger.debug('auto-posting to twitter for %s', post_id)
        post = Post.load_by_id(post_id)

        in_reply_to, repost_of, like_of = posse_post_discovery(post)

        # cowardly refuse to auto-POSSE a reply/repost/like when the
        # target tweet is not found.
        if post.in_reply_to and not in_reply_to:
            app.logger.warn('could not find tweet to reply to for %s',
                            post.in_reply_to)
            return None
        if post.repost_of and not repost_of:
            app.logger.warn('could not find tweet to repost for %s',
                            post.repost_of)
            return None
        if post.like_of and not like_of:
            app.logger.warn('could not find tweet to like for %s',
                            post.like_of)
            return None

        preview, img_url = guess_tweet_content(post, in_reply_to)
        response = do_tweet(
            post_id, preview, img_url, in_reply_to, repost_of, like_of)
        return str(response)


@app.route('/share_on_twitter', methods=['GET', 'POST'])
@login_required
def share_on_twitter():
    if request.method == 'GET':
        id = request.args.get('id')
        if not id:
            abort(404)

        post = Post.load_by_id(id)
        if not post:
            abort(404)

        app.logger.debug('sharing on twitter. post: %s', post)

        in_reply_to, repost_of, like_of \
            = posse_post_discovery(post)

        app.logger.debug(
            'discovered in-reply-to: %s, repost-of: %s, like-of: %s',
            in_reply_to, repost_of, like_of)

        preview, _ = guess_tweet_content(post, in_reply_to)

        imgs = list(collect_images(post))
        app.logger.debug('twitter post has images: %s', imgs)

        return render_template('share_on_twitter.html', preview=preview,
                               post=post, in_reply_to=in_reply_to,
                               repost_of=repost_of, like_of=like_of, imgs=imgs)

    post_id = request.form.get('post_id')
    preview = request.form.get('preview')
    img_url = request.form.get('img')
    in_reply_to = request.form.get('in_reply_to')
    repost_of = request.form.get('repost_of')
    like_of = request.form.get('like_of')

    return do_tweet(post_id, preview, img_url, in_reply_to,
                    repost_of, like_of)


def format_markdown_as_tweet(data):
    def person_to_twitter_handle(contact, nick, soup):
        """Attempt to replace friendly @name with the official @twitter username
        """
        if contact and contact.social:
            nick = contact.social.get('twitter') or nick
        return '@' + nick
    return util.format_as_text(
        util.markdown_filter(
            data, url_processor=None,
            person_processor=person_to_twitter_handle))


def get_auth():
    return OAuth1(
        client_key=get_settings().twitter_api_key,
        client_secret=get_settings().twitter_api_secret,
        resource_owner_key=get_settings().twitter_oauth_token,
        resource_owner_secret=get_settings().twitter_oauth_token_secret)


def repost_preview(url):
    if not is_twitter_authorized():
        app.logger.warn('current user is not authorized for twitter')
        return

    match = PERMALINK_RE.match(url)
    if match:
        tweet_id = match.group(2)
        embed_response = requests.get(
            'https://api.twitter.com/1.1/statuses/oembed.json',
            params={'id': tweet_id},
            auth=get_auth())

        if embed_response.status_code // 2 == 100:
            return embed_response.json().get('html')


def create_context(url):
    match = PERMALINK_RE.match(url)
    if not match:
        app.logger.debug('url is not a twitter permalink %s', url)
        return

    app.logger.debug('url is a twitter permalink')
    tweet_id = match.group(2)
    status_response = requests.get(
        'https://api.twitter.com/1.1/statuses/show/{}.json'.format(tweet_id),
        auth=get_auth())

    if status_response.status_code // 2 != 100:
        app.logger.warn("failed to fetch tweet %s %s", status_response,
                        status_response.content)
        return

    status_data = status_response.json()
    app.logger.debug('received response from twitter: %s', status_data)
    pub_date = datetime.datetime.strptime(status_data['created_at'],
                                          '%a %b %d %H:%M:%S %z %Y')
    # if pub_date and pub_date.tzinfo:
    #     pub_date = pub_date.astimezone(datetime.timezone.utc)
    real_name = status_data['user']['name']
    screen_name = status_data['user']['screen_name']
    author_name = real_name
    author_url = status_data['user']['url']
    if author_url:
        author_url = expand_link(author_url)
    else:
        author_url = 'https://twitter.com/{}'.format(screen_name)
    author_image = status_data['user']['profile_image_url']
    tweet_text = expand_links(status_data)

    # remove `_normal` from author image to get full-size photo
    author_image = re.sub('_normal\.(\w+)$', '.\g<1>', author_image)

    for media in status_data.get('entities', {}).get('media', []):
        if media.get('type') == 'photo':
            media_url = media.get('media_url')
            if media_url:
                tweet_text += '<div><img src="{}"/></div>'.format(media_url)

    context = Context()
    context.url = context.permalink = url
    context.author_name = author_name
    context.author_image = author_image
    context.author_url = author_url
    context.published = pub_date
    context.title = None
    context.content = tweet_text
    return context


def expand_links(status_data):
    text = status_data['text']
    urls = status_data.get('entities', {}).get('urls', [])
    urls = sorted(
        urls, key=lambda url_data: url_data['indices'][0], reverse=True)
    for url_data in urls:
        app.logger.debug('expanding url: %r', url_data)
        start_idx = url_data['indices'][0]
        end_idx = url_data['indices'][1]
        text = (text[:start_idx]
                + '<a href="{}">{}</a>'.format(url_data['expanded_url'],
                                               url_data['display_url'])
                + text[end_idx:])
    return text


def expand_link(url):
    app.logger.debug('expanding %s', url)
    try:
        r = requests.head(url, allow_redirects=True, timeout=30)
        if r and r.status_code // 100 == 2:
            app.logger.debug('expanded to %s', r.url)
            url = r.url
    except Exception as e:
        app.logger.debug('request to %s failed: %s', url, e)
    return url


def posse_post_discovery(post):
    def find_syndicated(original):
        if PERMALINK_RE.match(original):
            return original
        try:
            d = Mf2Parser(url=original).to_dict()
            urls = d['rels'].get('syndication', [])
            for item in d['items']:
                if 'h-entry' in item['type']:
                    urls += item['properties'].get('syndication', [])
            for url in urls:
                if PERMALINK_RE.match(url):
                    return url
        except HTTPError:
            app.logger.exception('Could not fetch original')

    def find_first_syndicated(originals):
        for original in originals:
            syndicated = find_syndicated(original)
            if syndicated:
                return syndicated

    return (
        find_first_syndicated(post.in_reply_to),
        find_first_syndicated(post.repost_of),
        find_first_syndicated(post.like_of),
    )


def guess_tweet_content(post, in_reply_to):
    """Best guess effort to generate tweet content for a post; useful for
    auto-filling the share form.
    """
    if post.title:
        preview = post.title
    else:
        preview = format_markdown_as_tweet(post.content)

    # add an in-reply-to if one isn't there already
    if in_reply_to:
        reply_match = PERMALINK_RE.match(in_reply_to)
        if reply_match:
            reply_name = '@' + reply_match.group(1)
            if reply_name not in preview:
                preview = reply_name + ' ' + preview

    # add location url if it's a checkin
    if post.post_type == 'checkin' and post.location:
        preview = preview + ' ' + post.location_url

    components = []
    prev_end = 0
    for match in util.LINK_RE.finditer(preview):
        text = preview[prev_end:match.start()].strip(' ')
        components.append(TweetComponent(
            length=len(text), can_shorten=True, can_drop=True, text=text))
        link = match.group(0)
        components.append(TweetComponent(
            length=URL_CHAR_LENGTH, can_shorten=False,
            can_drop=True, text=link))
        prev_end = match.end()

    text = preview[prev_end:].strip()
    components.append(TweetComponent(
        length=len(text), can_shorten=True, can_drop=True, text=text))

    target_length = TWEET_CHAR_LENGTH

    img_url = None
    if post.photos:
        photo = post.photos[0]
        img_url = post.photo_url(photo)
        target_length -= MEDIA_CHAR_LENGTH
        caption = photo.get('caption')
        if caption:
            components.append(TweetComponent(
                length=len(caption), can_shorten=True,
                can_drop=True, text=caption))

    if post.title or sum(c.length for c in components) > target_length:
        components.append(TweetComponent(
            length=URL_CHAR_LENGTH, can_shorten=False,
            can_drop=False, text=post.permalink))

    # iteratively shorten
    nspaces = len(components) - 1
    delta = sum(c.length for c in components) + nspaces - target_length
    shortened = []

    for c in reversed(components):
        if delta <= 0 or not c.can_drop:
            shortened.append(c)
        elif c.can_shorten and c.length >= delta + 1:
            text = c.text[:len(c.text) - (delta + 1)] + '…'
            delta -= (c.length - len(text))
            shortened.append(TweetComponent(
                length=len(text), text=text, can_shorten=False, can_drop=True))
        elif c.can_drop:
            delta -= c.length

    preview = ' '.join(reversed([s.text for s in shortened]))
    return preview, img_url


def do_tweet(post_id, preview, img_url, in_reply_to,
             repost_of, like_of):
    try:
        post = Post.load_by_id(post_id)
        twitter_url = handle_new_or_edit(
            post, preview, img_url, in_reply_to, repost_of, like_of)
        db.session.commit()

        if has_request_context():
            flash('Shared on Twitter: <a href="{}">Original</a>, '
                  '<a href="{}">On Twitter</a>'
                  .format(post.permalink, twitter_url))
            return redirect(post.permalink)

    except Exception as e:
        app.logger.exception('posting to twitter')
        if has_request_context():
            flash('Share on Twitter Failed!. Exception: {}'.format(e))
            return redirect(url_for('index'))


def handle_new_or_edit(post, preview, img, in_reply_to,
                       repost_of, like_of):

    if not is_twitter_authorized():
        app.logger.warn('current user is not authorized for twitter')
        return

    # check for RT's
    is_retweet = False
    if repost_of:
        repost_match = PERMALINK_RE.match(repost_of)
        if repost_match:
            is_retweet = True
            tweet_id = repost_match.group(2)
            result = requests.post(
                'https://api.twitter.com/1.1/statuses/retweet/{}.json'
                .format(tweet_id),
                auth=get_auth())
            if result.status_code // 2 != 100:
                raise RuntimeError("{}: {}".format(result,
                                                   result.content))
    is_favorite = False
    if like_of:
        like_match = PERMALINK_RE.match(like_of)
        if like_match:
            is_favorite = True
            tweet_id = like_match.group(2)
            result = requests.post(
                'https://api.twitter.com/1.1/favorites/create.json',
                data={'id': tweet_id},
                auth=get_auth())
            if result.status_code // 2 != 100:
                raise RuntimeError("{}: {}".format(result,
                                                   result.content))
    if not is_retweet and not is_favorite:
        data = {}
        data['status'] = preview

        if post.location:
            data['lat'] = str(post.location.latitude)
            data['long'] = str(post.location.longitude)

        if in_reply_to:
            reply_match = PERMALINK_RE.match(in_reply_to)
            if reply_match:
                data['in_reply_to_status_id'] = reply_match.group(2)

        if img:
            tempfile = download_image_to_temp(img)
            app.logger.debug(json.dumps(data, indent=True))

            result = requests.post(
                'https://api.twitter.com/1.1/statuses/update_with_media.json',
                data=data,
                files={'media[]': open(tempfile, 'rb')},
                auth=get_auth())

        else:
            result = requests.post(
                'https://api.twitter.com/1.1/statuses/update.json',
                data=data, auth=get_auth())

        if result.status_code // 2 != 100:
            raise RuntimeError("status code: {}, headers: {}, body: {}"
                               .format(result.status_code, result.headers,
                                       result.content))

    result_json = result.json()
    app.logger.debug("response from twitter {}".format(
        json.dumps(result_json, indent=True)))
    twitter_url = 'https://twitter.com/{}/status/{}'.format(
        result_json.get('user', {}).get('screen_name'),
        result_json.get('id_str'))

    #FIXME json objects aren't yet mutable
    new_syndication = list(post.syndication)
    new_syndication.append(twitter_url)
    post.syndication = new_syndication

    return twitter_url


def download_image_to_temp(url):
    _, tempfile = mkstemp()
    util.download_resource(url, tempfile)
    return tempfile


def is_twitter_authorized():
    return (get_settings().twitter_oauth_token
            and get_settings().twitter_oauth_token_secret)
