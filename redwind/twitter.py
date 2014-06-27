from . import app
from .models import Post
from . import util

from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, make_response,\
    render_template

import requests
import re
import json
import datetime
from . import hentry_template
from . import archiver

from tempfile import mkstemp
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from mf2py.parser import Parser as Mf2Parser

from requests_oauthlib import OAuth1Session, OAuth1
from requests.exceptions import HTTPError

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
AUTHORIZE_URL = 'https://api.twitter.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'


@app.route('/admin/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    callback_url = url_for('authorize_twitter2', _external=True)
    try:
        oauth = OAuth1Session(
            client_key=app.config['TWITTER_CONSUMER_KEY'],
            client_secret=app.config['TWITTER_CONSUMER_SECRET'],
            callback_uri=callback_url)

        oauth.fetch_request_token(REQUEST_TOKEN_URL)
        return redirect(oauth.authorization_url(AUTHORIZE_URL))

    except requests.RequestException as e:
        return make_response(str(e))


@app.route('/admin/authorize_twitter2')
def authorize_twitter2():
    """Receive the request token from Twitter and convert it to an
       access token"""
    try:
        oauth = OAuth1Session(
            client_key=app.config['TWITTER_CONSUMER_KEY'],
            client_secret=app.config['TWITTER_CONSUMER_SECRET'])
        oauth.parse_authorization_response(request.url)

        response = oauth.fetch_access_token(ACCESS_TOKEN_URL)
        access_token = response.get('oauth_token')
        access_token_secret = response.get('oauth_token_secret')

        current_user.twitter_oauth_token = access_token
        current_user.twitter_oauth_token_secret = access_token_secret

        current_user.save()
        return redirect(url_for('settings'))
    except requests.RequestException as e:
        return make_response(str(e))


def collect_images(post):
    """find the first image (if any) that is in an <img> tag
    in the rendered post"""
    from .views import markdown_filter
    html = markdown_filter(post.content, img_path=post.get_image_path(),
                           link_twitter_names=False,
                           person_processor=None)
    soup = BeautifulSoup(html)
    for img in soup.find_all('img'):
        if not img.find_parent(class_='h-card'):
            src = img.get('src')
            if src:
                yield urljoin(app.config['SITE_URL'], src)


@app.route('/admin/share_on_twitter', methods=['GET', 'POST'])
@login_required
def share_on_twitter():
    if request.method == 'GET':
        post = Post.load_by_shortid(request.args.get('id'))

        in_reply_to, repost_of, like_of \
            = twitter_client.posse_post_discovery(post)

        return render_template('share_on_twitter.html', post=post,
                               in_reply_to=in_reply_to,
                               repost_of=repost_of, like_of=like_of,
                               imgs=list(collect_images(post)))

    try:
        post_id = request.form.get('post_id')
        preview = request.form.get('preview')
        img_url = request.form.get('img')
        in_reply_to = request.form.get('in_reply_to')
        repost_of = request.form.get('repost_of')
        like_of = request.form.get('like_of')

        with Post.writeable(Post.shortid_to_path(post_id)) as post:
            twitter_url = twitter_client.handle_new_or_edit(
                post, preview, img_url, in_reply_to, repost_of, like_of)
            post.save()

            return """Shared on Twitter<br/>
            <a href="{}">Original</a><br/>
            <a href="{}">On Twitter</a><br/>
            """.format(post.permalink, twitter_url)

    except Exception as e:
        app.logger.exception('posting to twitter')
        return """Share on Twitter Failed!<br/>Exception: {}""".format(e)


@app.template_filter('format_markdown_as_tweet')
def format_markdown_as_tweet(data, img_path):
    def person_to_twitter_handle(fullname, displayname, entry, pos):
        handle = entry.get('twitter')
        if handle:
            return '@' + handle
        return displayname

    from .views import format_markdown_as_text
    return format_markdown_as_text(data, img_path, link_twitter_names=False,
                                   person_processor=person_to_twitter_handle)


class TwitterClient:
    PERMALINK_RE = re.compile(
        "https?://(?:www\.)?twitter\.com/(\w+)/status(?:es)?/(\w+)")

    def get_auth(self):
        return OAuth1(
            client_key=app.config['TWITTER_CONSUMER_KEY'],
            client_secret=app.config['TWITTER_CONSUMER_SECRET'],
            resource_owner_key=current_user.twitter_oauth_token,
            resource_owner_secret=current_user.twitter_oauth_token_secret)

    def repost_preview(self, url):
        if not self.is_twitter_authorized(current_user):
            return

        match = self.PERMALINK_RE.match(url)
        if match:
            tweet_id = match.group(2)
            embed_response = requests.get(
                'https://api.twitter.com/1.1/statuses/oembed.json',
                params={'id': tweet_id},
                auth=self.get_auth())

            if embed_response.status_code // 2 == 100:
                return embed_response.json().get('html')

    def fetch_external_post(self, url):
        from .views import local_mirror_resource
        
        match = self.PERMALINK_RE.match(url)
        if not match:
            app.logger.debug('url is not a twitter permalink %s', url)
            return False
        app.logger.debug('url is a twitter permalink')
        tweet_id = match.group(2)
        status_response = requests.get(
            'https://api.twitter.com/1.1/statuses/show/{}.json'.format(tweet_id),
            auth=self.get_auth())

        if status_response.status_code // 2 != 100:
            app.logger.warn("failed to fetch tweet %s %s", status_response,
                            status_response.content)
            return None

        status_data = status_response.json()
        app.logger.debug('received response from twitter: %s', status_data)
        pub_date = datetime.datetime.strptime(status_data['created_at'],
                                     '%a %b %d %H:%M:%S %z %Y')
        #if pub_date and pub_date.tzinfo:
        #    pub_date = pub_date.astimezone(datetime.timezone.utc)
        real_name = status_data['user']['name']
        screen_name = status_data['user']['screen_name']
        author_name = real_name
        author_url = status_data['user']['url']
        if author_url:
            author_url = self.expand_link(author_url)
        else:
            author_url = 'https://twitter.com/{}'.format(screen_name)
        author_image = status_data['user']['profile_image_url']
        tweet_text = self.expand_links(status_data['text'])

        for media in status_data.get('entities', {}).get('media', []):
            if media.get('type') == 'photo':
                media_url = media.get('media_url')
                if media_url:
                    tweet_text += '<div><img src="{}"/></div>'.format(local_mirror_resource(media_url))

        html = hentry_template.fill(author_name=author_name,
                                    author_url=author_url,
                                    author_image=author_image,
                                    pub_date=pub_date,
                                    content=tweet_text,
                                    permalink=url)
        archiver.archive_html(url, html)
        return True

    # TODO use twitter API entities to expand links without fetch requests
    def expand_links(self, text):
        return re.sub(util.LINK_REGEX,
                      lambda match: self.expand_link(match.group(0)),
                      text)

    def expand_link(self, url):
        app.logger.debug('expanding %s', url)
        try:
            r = requests.head(url, allow_redirects=True, timeout=30)
            if r and r.status_code // 100 == 2:
                app.logger.debug('expanded to %s', r.url)
                url = r.url
        except requests.exceptions.Timeout:
            app.logger.debug('request to %s timed out', url)
        return url

    def posse_post_discovery(self, post):
        def find_syndicated(original):
            if self.PERMALINK_RE.match(original):
                return original
            try:
                d = Mf2Parser(url=original).to_dict()
                urls = d['rels'].get('syndication', [])
                for item in d['items']:
                    if 'h-entry' in item['type']:
                        urls += item['properties'].get('syndication', [])
                for url in urls:
                    if self.PERMALINK_RE.match(url):
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

    def handle_new_or_edit(self, post, preview, img, in_reply_to,
                           repost_of, like_of):
        if not self.is_twitter_authorized():
            return
        # check for RT's
        is_retweet = False
        if repost_of:
            repost_match = self.PERMALINK_RE.match(repost_of)
            if repost_match:
                is_retweet = True
                tweet_id = repost_match.group(2)
                result = requests.post(
                    'https://api.twitter.com/1.1/statuses/retweet/{}.json'
                    .format(tweet_id),
                    auth=self.get_auth())
                if result.status_code // 2 != 100:
                    raise RuntimeError("{}: {}".format(result,
                                                       result.content))

        is_favorite = False
        if like_of:
            like_match = self.PERMALINK_RE.match(like_of)
            if like_match:
                is_favorite = True
                tweet_id = like_match.group(2)
                result = requests.post(
                    'https://api.twitter.com/1.1/favorites/create.json',
                    data={'id': tweet_id},
                    auth=self.get_auth())
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
                reply_match = self.PERMALINK_RE.match(in_reply_to)
                if reply_match:
                    data['in_reply_to_status_id'] = reply_match.group(2)

            if img:
                tempfile = self.download_image_to_temp(img)
                app.logger.debug(json.dumps(data, indent=True))

                result = requests.post(
                    'https://api.twitter.com/1.1/statuses/update_with_media.json',
                    data=data,
                    files={'media[]': open(tempfile, 'rb')},
                    auth=self.get_auth())

            else:
                result = requests.post(
                    'https://api.twitter.com/1.1/statuses/update.json',
                    data=data, auth=self.get_auth())

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
        post.syndication.append(twitter_url)
        return twitter_url

    def download_image_to_temp(self, url):
        _, tempfile = mkstemp()
        util.download_resource(url, tempfile)
        return tempfile

    def is_twitter_authorized(self):
        return current_user and current_user.twitter_oauth_token \
            and current_user.twitter_oauth_token_secret


twitter_client = TwitterClient()
