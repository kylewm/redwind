# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


from . import app
from .models import Post
from . import util

from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, make_response,\
    jsonify, render_template
from rauth import OAuth1Service

import requests
import re
import json
import pytz
import types

from tempfile import mkstemp
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from rauth.oauth import HmacSha1Signature

@app.route('/admin/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    callback_url = url_for('authorize_twitter2', _external=True)
    try:
        twitter = twitter_client.get_auth_service()
        request_token, request_token_secret = twitter.get_request_token(
            params={'oauth_callback': callback_url})

        return redirect(twitter.get_authorize_url(request_token))
    except requests.RequestException as e:
        return make_response(str(e))


@app.route('/admin/authorize_twitter2')
def authorize_twitter2():
    """Receive the request token from Twitter and convert it to an
       access token"""
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')

    try:
        twitter = twitter_client.get_auth_service()
        access_token, access_token_secret = twitter.get_access_token(
            oauth_token, '', method='POST',
            params={'oauth_verifier': oauth_verifier})

        current_user.twitter_oauth_token = access_token
        current_user.twitter_oauth_token_secret = access_token_secret

        current_user.save()
        return redirect(url_for('settings'))
    except requests.RequestException as e:
        return make_response(str(e))


def collect_images(post):
    """find the first image (if any) that is in an <img> tag
    in the rendered post"""
    from .views import format_as_html
    html = format_as_html(post.content, post.content_format)
    soup = BeautifulSoup(html)
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            yield urljoin(app.config['SITE_URL'], src)


@app.route('/admin/share_on_twitter', methods=['GET', 'POST'])
@login_required
def share_on_twitter():
    if request.method == 'GET':
        post = Post.load_by_shortid(request.args.get('id'))
        return render_template('share_on_twitter.html', post=post,
                               imgs=list(collect_images(post)))

    try:
        post_id = request.form.get('post_id')
        preview = request.form.get('preview')
        img_url = request.form.get('img')

        with Post.writeable(Post.shortid_to_path(post_id)) as post:
            twitter_client.handle_new_or_edit(post, preview, img_url)
            post.save()

            return """Shared on Twitter<br/>
            <a href="{}">Original</a><br/>
            <a href="{}">On Twitter</a><br/>
            """.format(post.permalink, post.twitter_url)

    except Exception as e:
        app.logger.exception('posting to twitter')
        return """Share on Twitter Failed!<br/>Exception: {}""".format(e)


class UpdateWithMediaSignature(HmacSha1Signature):

    def sign(self, consumer_secret, access_token_secret, method, url,
             oauth_params, req_kwargs):
        sig_wo = super(UpdateWithMediaSignature, self).sign(
            consumer_secret, access_token_secret, method, url,
            oauth_params, {})
        return sig_wo


class TwitterClient:

    PERMALINK_RE = re.compile(
        "https?://(?:www.)?twitter.com/(\w+)/status(?:es)?/(\w+)")

    def get_auth_service(self):
        key = app.config['TWITTER_CONSUMER_KEY']
        secret = app.config['TWITTER_CONSUMER_SECRET']
        service = OAuth1Service(
            name='twitter',
            consumer_key=key,
            consumer_secret=secret,
            request_token_url=
            'https://api.twitter.com/oauth/request_token',
            access_token_url='https://api.twitter.com/oauth/access_token',
            authorize_url='https://api.twitter.com/oauth/authorize',
            base_url='https://api.twitter.com/1.1/')
        return service

    def get_auth_session(self, signature=None):
        service = self.get_auth_service()
        session = service.get_session(
            token=(current_user.twitter_oauth_token,
                   current_user.twitter_oauth_token_secret),
            signature=signature)
        return session

    def repost_preview(self, url):
        if not self.is_twitter_authorized(current_user):
            return

        match = self.PERMALINK_RE.match(url)
        if match:
            api = self.get_auth_session()
            tweet_id = match.group(2)
            embed_response = api.get('statuses/oembed.json',
                                     params={'id': tweet_id})

            if embed_response.status_code // 2 == 100:
                return embed_response.json().get('html')

    def fetch_external_post(self, ctx):
        match = self.PERMALINK_RE.match(ctx.source)
        if match:
            api = self.get_auth_session()
            tweet_id = match.group(2)
            status_response = api.get('statuses/show/{}.json'.format(tweet_id))

            if status_response.status_code // 2 != 100:
                app.logger.warn("failed to fetch tweet %s %s", status_response,
                                status_response.content)
                return None

            status_data = status_response.json()

            pub_date = datetime.strptime(status_data['created_at'],
                                         '%a %b %d %H:%M:%S %z %Y')
            if pub_date and pub_date.tzinfo:
                pub_date = pub_date.astimezone(pytz.utc)
            real_name = status_data['user']['name']
            screen_name = status_data['user']['screen_name']
            author_name = real_name
            author_url = status_data['user']['url']
            if author_url:
                author_url = self.expand_link(author_url)
            else:
                author_url = 'http://twitter.com/{}'.format(screen_name)
            author_image = status_data['user']['profile_image_url']
            tweet_text = self.expand_links(status_data['text'])

            ctx.permalink = ctx.source
            ctx.title = None
            ctx.content = tweet_text
            ctx.content_format = 'plain'
            ctx.author_name = author_name
            ctx.author_url = author_url
            ctx.author_image = author_image
            ctx.pub_date = pub_date
            return True

    def expand_links(self, text):
        return re.sub(util.LINK_REGEX,
                      lambda match: self.expand_link(match.group(0)),
                      text)

    def expand_link(self, url, depth_limit=5):
        if depth_limit > 0:
            app.logger.debug("expanding %s", url)
            r = requests.head(url)
            if r and r.status_code == 301 and 'location' in r.headers:
                url = r.headers['location']
                app.logger.debug("redirected to %s", url)
                url = self.expand_link(url, depth_limit-1)
        return url

    def handle_new_or_edit(self, post, preview, img):
        if not self.is_twitter_authorized():
            return
        api = self.get_auth_session()

        # check for RT's
        is_retweet = False
        for share_context in post.share_contexts:
            repost_match = self.PERMALINK_RE.match(share_context.source)
            if repost_match:
                is_retweet = True
                tweet_id = repost_match.group(2)
                result = api.post('statuses/retweet/{}.json'.format(tweet_id),
                                  data={'trim_user': True})
                if result.status_code // 2 != 100:
                    raise RuntimeError("{}: {}".format(result,
                                                       result.content))

        is_favorite = False
        for like_context in post.like_contexts:
            like_match = self.PERMALINK_RE.match(post.like_of)
            if like_match:
                is_favorite = True
                tweet_id = like_match.group(2)
                result = api.post('favorites/create.json',
                                  data={'id': tweet_id, 'trim_user': True})
                if result.status_code // 2 != 100:
                    raise RuntimeError("{}: {}".format(result,
                                                       result.content))

        if not is_retweet and not is_favorite:
            data = {}
            data['status'] = preview
            data['trim_user'] = True

            if post.location:
                data['lat'] = str(post.location.latitude)
                data['long'] = str(post.location.longitude)

            for reply_context in post.reply_contexts:
                reply_match = self.PERMALINK_RE.match(reply_context.source)
                if reply_match:
                    data['in_reply_to_status_id'] = reply_match.group(2)
                    break

            if img:
                tempfile = self.download_image_to_temp(img)
                app.logger.debug(json.dumps(data, indent=True))
                media_api = self.get_auth_session(
                    signature=UpdateWithMediaSignature)

                filebuf = open(tempfile, 'rb')
                filebuf.__deepcopy__ = types.MethodType(lambda x, memo: x, filebuf)
                result = media_api.post('statuses/update_with_media.json',
                                        header_auth=True,
                                        data=data,
                                        files={
                                            'media[]': filebuf
                                        })

            else:
                result = api.post('statuses/update.json', data=data)

            if result.status_code // 2 != 100:
                raise RuntimeError("status code: {}, headers: {}, body: {}"
                                   .format(result.status_code, result.headers,
                                           result.content))

        post.twitter_status_id = result.json().get('id_str')

    def download_image_to_temp(self, url):
        _, tempfile = mkstemp()
        util.download_resource(url, tempfile)
        return tempfile

    def is_twitter_authorized(self):
        return current_user and current_user.twitter_oauth_token \
            and current_user.twitter_oauth_token_secret


twitter_client = TwitterClient()
