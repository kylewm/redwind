from redwind import hooks, util
from redwind.tasks import get_queue, async_app_context
from redwind.models import Post, Context, Setting, get_settings
from redwind.extensions import db

from flask.ext.login import login_required
from flask import (
    request, redirect, url_for, make_response, render_template,
    flash, abort, has_request_context, Blueprint, current_app
)

import brevity
import collections
import requests
import re
import json
import datetime

from tempfile import mkstemp
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests_oauthlib import OAuth1Session, OAuth1

twitter = Blueprint('twitter', __name__)

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
USERMENTION_RE = util.AT_USERNAME_RE


def register(app):
    app.register_blueprint(twitter)
    hooks.register('create-context', create_context)
    hooks.register('post-saved', send_to_twitter)


@twitter.context_processor
def inject_settings_variable():
    return {
        'settings': get_settings()
    }


@twitter.route('/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    callback_url = url_for('.twitter_callback', _external=True)
    try:
        oauth = OAuth1Session(
            client_key=get_settings().twitter_api_key,
            client_secret=get_settings().twitter_api_secret,
            callback_uri=callback_url)

        oauth.fetch_request_token(REQUEST_TOKEN_URL)
        return redirect(oauth.authorization_url(AUTHORIZE_URL))

    except requests.RequestException as e:
        return make_response(str(e))


@twitter.route('/twitter_callback')
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
        Setting.query.get('twitter_oauth_token_secret').value \
            = access_token_secret

        db.session.commit()
        return redirect(url_for('admin.edit_settings'))
    except requests.RequestException as e:
        return make_response(str(e))


def collect_images(post):
    """collect the images (if any) that are in an <img> tag
    in the rendered post"""

    if type(post) == Post and post.attachments:
        for photo in post.attachments:
            yield photo.url

    else:
        if type(post) == Post:
            html = util.markdown_filter(
                post.content, img_path=post.get_image_path())
        else:
            html = post.content

        if html:
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
    if 'twitter' in args.getlist('syndicate-to'):
        if not is_twitter_authorized():
            return False, 'Current user is not authorized to tweets'

        try:
            current_app.logger.debug('auto-posting to twitter %r', post.id)
            get_queue().enqueue(
                do_send_to_twitter, post.id, current_app.config)
            return True, 'Success'

        except Exception as e:
            current_app.logger.exception('auto-posting to twitter')
            return (False, 'Exception while auto-posting to twitter: {}'
                    .format(e))


def do_send_to_twitter(post_id, app_config):
    with async_app_context(app_config):
        current_app.logger.debug('auto-posting to twitter for %s', post_id)
        post = Post.load_by_id(post_id)

        in_reply_to, repost_of, like_of = util.posse_post_discovery(
            post, PERMALINK_RE)

        # cowardly refuse to auto-POSSE a reply/repost/like when the
        # target tweet is not found.
        if post.in_reply_to and not in_reply_to:
            current_app.logger.warn(
                'could not find tweet to reply to for %s', post.in_reply_to)
            return None
        elif post.repost_of and not repost_of:
            current_app.logger.warn(
                'could not find tweet to repost for %s', post.repost_of)
            preview, img_url = guess_raw_share_tweet_content(post)
        elif post.like_of and not like_of:
            current_app.logger.warn(
                'could not find tweet to like for %s', post.like_of)
            return None
        else:
            preview, img_url = guess_tweet_content(post, in_reply_to)

        response = do_tweet(post_id, preview, img_url, in_reply_to, repost_of,
                            like_of)
        return str(response)


@twitter.route('/share_on_twitter', methods=['GET', 'POST'])
@login_required
def share_on_twitter():
    if request.method == 'GET':
        id = request.args.get('id')
        if not id:
            abort(404)

        post = Post.load_by_id(id)
        if not post:
            abort(404)

        current_app.logger.debug('sharing on twitter. post: %s', post)

        in_reply_to, repost_of, like_of \
            = util.posse_post_discovery(post, PERMALINK_RE)

        current_app.logger.debug(
            'discovered in-reply-to: %s, repost-of: %s, like-of: %s',
            in_reply_to, repost_of, like_of)

        if post.repost_of and not repost_of:
            preview, _ = guess_raw_share_tweet_content(post)
            imgs = list(collect_images(post.repost_contexts[0]))
        else:
            preview, _ = guess_tweet_content(post, in_reply_to)
            imgs = list(collect_images(post))

        current_app.logger.debug('twitter post has images: %s', imgs)

        return render_template('admin/share_on_twitter.jinja2',
                               preview=preview,
                               post=post, in_reply_to=in_reply_to,
                               repost_of=repost_of, like_of=like_of, imgs=imgs)

    post_id = request.form.get('post_id')
    preview = request.form.get('preview')
    img_url = request.form.get('img')
    in_reply_to = request.form.get('in_reply_to')
    repost_of = request.form.get('repost_of')
    like_of = request.form.get('like_of')

    return do_tweet(post_id, preview, img_url, in_reply_to, repost_of,
                    like_of)


def format_markdown_as_tweet(data):
    def to_twitter_handle(contact, nick):
        """Attempt to replace friendly @name with the official @twitter
        username
        """
        if contact:
            for url in contact.social:
                m = util.TWITTER_PROFILE_RE.match(url)
                if m:
                    nick = m.group(1)
                    break
        return '@' + nick

    html = util.markdown_filter(data)
    html = util.process_people(to_twitter_handle, html)
    return util.format_as_text(html)


def get_auth():
    return OAuth1(
        client_key=get_settings().twitter_api_key,
        client_secret=get_settings().twitter_api_secret,
        resource_owner_key=get_settings().twitter_oauth_token,
        resource_owner_secret=get_settings().twitter_oauth_token_secret)


def repost_preview(url):
    if not is_twitter_authorized():
        current_app.logger.warn('current user is not authorized for twitter')
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
        current_app.logger.debug('url is not a twitter permalink %s', url)
        return

    current_app.logger.debug('url is a twitter permalink')
    tweet_id = match.group(2)
    status_response = requests.get(
        'https://api.twitter.com/1.1/statuses/show/{}.json'.format(tweet_id),
        auth=get_auth())

    if status_response.status_code // 2 != 100:
        current_app.logger.warn(
            'failed to fetch tweet %s %s', status_response,
            status_response.content)
        return

    status_data = status_response.json()
    current_app.logger.debug('received response from twitter: %s', status_data)
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
    tweet_content = expand_links(status_data)
    tweet_plain = expand_links(status_data, as_html=False)

    # remove `_normal` from author image to get full-size photo
    author_image = re.sub('_normal\.(\w+)$', '.\g<1>', author_image)

    for media in status_data.get('entities', {}).get('media', []):
        if media.get('type') == 'photo':
            media_url = media.get('media_url')
            if media_url:
                tweet_content += '<div><img src="{}"/></div>'.format(media_url)
                tweet_plain += media_url

    context = Context()
    context.url = context.permalink = url
    context.author_name = author_name
    context.author_image = author_image
    context.author_url = author_url
    context.published = pub_date
    context.title = None
    context.content = tweet_content
    context.content_plain = tweet_plain
    return context


def expand_links(status_data, as_html=True):
    text = status_data['text']
    urls = status_data.get('entities', {}).get('urls', [])

    for um in status_data.get('entities', {}).get('user_mentions', []):
        um = um.copy()
        um.update({
            'display_url': '@' + um.get('screen_name'),
            'expanded_url': 'https://twitter.com/{}'.format(
                um.get('screen_name')),
        })
        urls.append(um)

    urls = sorted(
        urls, key=lambda url_data: url_data['indices'][0], reverse=True)
    for url_data in urls:
        current_app.logger.debug('expanding url: %r', url_data)
        start_idx = url_data['indices'][0]
        end_idx = url_data['indices'][1]
        if as_html:
            link_text = '<a href="{}">{}</a>'.format(
                url_data['expanded_url'], url_data['display_url'])
        else:
            link_text = url_data['expanded_url']
        text = text[:start_idx] + link_text + text[end_idx:]
    return text


def expand_link(url):
    current_app.logger.debug('expanding %s', url)
    try:
        r = requests.head(url, allow_redirects=True, timeout=30)
        if r and r.status_code // 100 == 2:
            current_app.logger.debug('expanded to %s', r.url)
            url = r.url
    except Exception as e:
        current_app.logger.debug('request to %s failed: %s', url, e)
    return url


def get_authed_twitter_account():
    """Gets the username of the currently authed twitter user
    """
    if not is_twitter_authorized():
        return None

    user_response = requests.get(
        'https://api.twitter.com/1.1/account/verify_credentials.json',
        auth=get_auth())

    if user_response.status_code // 2 != 100:
        current_app.logger.warn('failed to retrieve user data %s %s',
                                user_response, user_response.content)
        return None

    current_app.logger.debug('retrieved user data for %s', user_response)
    return user_response.json()


def prepend_twitter_name(name, tweet, exclude_me=True):
    my_screen_name = get_authed_twitter_account().get(
        'screen_name', '').lower()
    if ((exclude_me and name.lower() == my_screen_name)
            or (name.lower() in tweet.lower())):
        return tweet
    return '@{} {}'.format(name, tweet)


def guess_tweet_content(post, in_reply_to):
    """Best guess effort to generate tweet content for a post; useful for
    auto-filling the share form.
    """
    preview = ''
    if post.title:
        preview += post.title

    # add location if it's a checkin
    elif post.post_type == 'checkin' and post.venue:
        preview = 'Checked in to ' + post.venue.name

    text_content = format_markdown_as_tweet(post.content)
    if text_content:
        preview += (': ' if preview else '') + text_content

    # add an in-reply-to if one isn't there already
    if in_reply_to:
        reply_match = PERMALINK_RE.match(in_reply_to)
        if reply_match:
            # get the status we're responding to
            status_response = requests.get(
                'https://api.twitter.com/1.1/statuses/show/{}.json'.format(
                    reply_match.group(2)),
                auth=get_auth())

            if status_response.status_code // 2 != 100:
                current_app.logger.warn(
                    'failed to fetch tweet %s %s while finding participants',
                    status_response, status_response.content)
                status_data = {}
            else:
                status_data = status_response.json()

            # get the list of people to respond to
            mentioned_users = []
            my_screen_name = get_authed_twitter_account().get(
                'screen_name', '')
            for user in status_data.get('entities', {}).get('user_mentions', []):
                screen_name = user.get('screen_name', '')

                if screen_name and screen_name.lower() != my_screen_name.lower():
                    mentioned_users.append(screen_name)
            mentioned_users.append(reply_match.group(1))  # the status author
            current_app.logger.debug('got mentioned users %s', mentioned_users)

            # check to see if anybody is already mentioned by the preview
            mention_match = USERMENTION_RE.findall(preview)
            for match in mention_match:
                if match[0] in mentioned_users:
                    break
            else:
                # nobody was mentioned, prepend all the names!
                for user in mentioned_users:
                    preview = prepend_twitter_name(user, preview)

    target_length = TWEET_CHAR_LENGTH

    img_url = None
    if post.post_type == 'photo' and post.attachments:
        img_url = post.attachments[0].url
        target_length -= MEDIA_CHAR_LENGTH

    preview = brevity.shorten(preview, permalink=post.permalink,
                              target_length=target_length)
    return preview, img_url


def guess_raw_share_tweet_content(post):
    preview = ''
    if not post.repost_contexts:
        current_app.logger.debug(
            'failed to load repost context for %s', post.id)
        return None
    context = post.repost_contexts[0]

    if context.title:
        preview += context.title

        if context.author_name:
            preview += ' by ' + context.author_name
    elif context.content:
        if context.author_name:
            preview += context.author_name + ': '

        preview += context.content_plain

    # if the tweet doesn't get trimmed, put the link on the end anyway
    preview += (' ' if preview else '') + context.permalink

    target_length = TWEET_CHAR_LENGTH

    imgs = list(collect_images(context))
    img_url = imgs[0] if imgs else None

    preview = brevity.shorten(preview, permalink=context.permalink,
                              target_length=target_length)
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
        current_app.logger.exception('posting to twitter')
        if has_request_context():
            flash('Share on Twitter Failed!. Exception: {}'.format(e))
            return redirect(url_for('views.index'))


def handle_new_or_edit(post, preview, img, in_reply_to,
                       repost_of, like_of):
    if not is_twitter_authorized():
        current_app.logger.warn('current user is not authorized for twitter')
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
                raise RuntimeError("{}: {}".format(
                    result, result.content))
    if not is_retweet and not is_favorite:
        data = {}
        data['status'] = preview

        loc = (post.venue and post.venue.location) or post.location
        if loc:
            data['lat'] = str(loc.get('latitude'))
            data['long'] = str(loc.get('longitude'))

        if in_reply_to:
            reply_match = PERMALINK_RE.match(in_reply_to)
            if reply_match:
                data['in_reply_to_status_id'] = reply_match.group(2)

        current_app.logger.debug('publishing with data %r', json.dumps(data))
        if img:
            tempfile = download_image_to_temp(img)
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
    current_app.logger.debug("response from twitter {}".format(
        json.dumps(result_json, indent=True)))
    twitter_url = 'https://twitter.com/{}/status/{}'.format(
        result_json.get('user', {}).get('screen_name'),
        result_json.get('id_str'))

    if not is_favorite:
        post.add_syndication_url(twitter_url)
    return twitter_url


def download_image_to_temp(url):
    _, tempfile = mkstemp()
    util.download_resource(url, tempfile)
    return tempfile


def is_twitter_authorized():
    return (get_settings().twitter_oauth_token
            and get_settings().twitter_oauth_token_secret)
