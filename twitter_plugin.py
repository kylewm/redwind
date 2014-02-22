from app import app, db
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, make_response

import twitter
import re
import urllib.parse
from datetime import datetime, timedelta


@app.route('/admin/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    key = app.config['TWITTER_CONSUMER_KEY']
    secret = app.config['TWITTER_CONSUMER_SECRET']
    callback_url = app.config.get('SITE_URL') + '/admin/authorize_twitter2'

    try:
        t = twitter.Twitter(auth=twitter.OAuth('', '', key, secret),
                            format='', api_version='')
        r = t.oauth.request_token(oauth_callback=callback_url)
        payload = urllib.parse.parse_qs(r)
        request_token = payload["oauth_token"][-1]
        return redirect(
            'https://api.twitter.com/oauth/authenticate?'
            + urllib.parse.urlencode({"oauth_token": request_token}))
    except twitter.TwitterHTTPError as e:
        return make_response(str(e))


@app.route('/admin/authorize_twitter2')
def authorize_twitter2():
    """Receive the request token from Twitter and convert it to an
       access token"""
    key = app.config['TWITTER_CONSUMER_KEY']
    secret = app.config['TWITTER_CONSUMER_SECRET']

    request_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')

    try:
        t = twitter.Twitter(auth=twitter.OAuth(request_token, '', key, secret),
                            format='', api_version='')
        r = t.oauth.access_token(oauth_verifier=oauth_verifier)
        payload = urllib.parse.parse_qs(r)
        oauth_token = payload["oauth_token"][-1]
        oauth_token_secret = payload["oauth_token_secret"][-1]
        current_user.twitter_oauth_token = oauth_token
        current_user.twitter_oauth_token_secret = oauth_token_secret
        db.session.commit()
        return redirect(url_for('settings'))
    except twitter.TwitterHTTPError as e:
        return make_response(str(e))


class TwitterClient:
    def __init__(self, app):
        self.app = app
        self.cached_api = None
        self.cached_config = None
        self.config_fetch_date = None

    def repost_preview(self, user, url):
        if not self.is_twitter_authorized(user):
            return
        permalink_re = re.compile(
            "https?://(?:www.)?twitter.com/(\w+)/status/(\w+)")
        match = permalink_re.match(url)
        if match:
            api = self.get_api(user)
            tweet_id = match.group(2)
            embed_response = api.statuses.oembed(_id=tweet_id)
            return embed_response.get('html')

    def handle_new_or_edit(self, post):
        if not self.is_twitter_authorized(post.author):
            return

        permalink_re = re.compile(
            "https?://(?:www.)?twitter.com/(\w+)/status/(\w+)")
        api = self.get_api(post.author)
        # check for RT's
        match = permalink_re.match(post.repost_source)
        if match:
            tweet_id = match.group(2)
            api.statuses.retweet(id=tweet_id, trim_user=True)
        else:
            match = permalink_re.match(post.in_reply_to)
            in_reply_to = match.group(2) if match else None
            result = api.statuses.update(status=self.create_status(post),
                                         in_reply_to_status_id=in_reply_to,
                                         trim_user=True)
            if result:
                post.twitter_status_id = result.get('id_str')

    def is_twitter_authorized(self, user):
        return user.twitter_oauth_token and user.twitter_oauth_token_secret

    def get_api(self, user):
        if not self.cached_api:
            consumer_key = self.app.config['TWITTER_CONSUMER_KEY']
            consumer_secret = self.app.config['TWITTER_CONSUMER_SECRET']
            oauth_token = user.twitter_oauth_token
            oauth_secret = user.twitter_oauth_token_secret
            self.cached_api = twitter.Twitter(
                auth=twitter.OAuth(oauth_token, oauth_secret,
                                   consumer_key, consumer_secret))
        return self.cached_api

    def get_help_configuration(self, user): 
        if (not self.cached_config
                or datetime.now() - self.config_fetch_date > timedelta(days=1)):
            api = self.get_api(user)
            self.cached_config = api.help.configuration()
            self.config_fetch_date = datetime.now()
        return self.cached_config

        def __repr__(self):
            return "text({})".format(self.text)

    def estimate_length(self, components):
        return sum(c.length for c in components) + len(components) - 1

    def run_shorten_algorithm(self, components, target_length):
        orig_length = self.estimate_length(components)
        difference = orig_length - target_length

        shortened_comps = []
        for c in reversed(components):

            if difference <= 0 or not (c.can_drop or c.can_shorten):
                shortened_comps.insert(0, c)
            else:
                if c.can_shorten:
                    shortened = c.shorten(c.length - difference)
                    difference -= c.length
                    if shortened:
                        difference += shortened.length
                        shortened_comps.insert(0, shortened)
                else:
                    difference -= c.length

        return ' '.join(c.text for c in shortened_comps)

    def url_to_span(self, user, url, can_drop=True):
        twitter_config = self.get_help_configuration(user)
        if twitter_config:
            url_length = twitter_config.get('short_url_length_https'
                                            if url.startswith('https')
                                            else 'short_url_length')
        else:
            url_length = 30

        return TextSpan(url, url_length, can_shorten=False, can_drop=can_drop)

    def text_to_span(self, text, can_shorten=True, can_drop=True):
        return TextSpan(text, len(text), can_shorten=can_shorten,
                        can_drop=can_drop)

    def split_out_urls(self, user, text):
        components = []
        while text:
            m = re.search(r'https?://[a-zA-Z0-9_\.\-():@#$%&?/=]+', text)
            if m:
                head = text[:m.start()].strip()
                url = m.group(0)

                components.append(self.text_to_span(head))
                components.append(self.url_to_span(user, url))
                text = text[m.end():]
            else:
                tail = text.strip()
                components.append(self.text_to_span(tail))
                text = None
        return components

    def create_status(self, post):
        """Create a <140 status message suitable for twitter
        """
        target_length = 140

        if post.title:
            components = [self.text_to_span(post.title),
                          self.url_to_span(post.author, post.permalink_url,
                                           can_drop=False)]

        else:
            components = self.split_out_urls(post.author, post.content)

            # include the re-shared link
            if post.repost_source:
                components.append(self.url_to_span(post.author,
                                                   post.repost_source,
                                                   can_drop=False))

            # include a link to the original message if the note is longer than
            # 140 characters, and we aren't resharing another URL.
            if self.estimate_length(components) > target_length:
                components.append(self.url_to_span(post.author,
                                                   post.permalink_url,
                                                   can_drop=False))

        status = self.run_shorten_algorithm(components, target_length)
        self.app.logger.info("shortened for twitter '%s'", status)
        return status


class TextSpan:
    def __init__(self, text, length, can_shorten=True, can_drop=True):
        self.text = text
        self.length = length
        self.can_shorten = can_shorten
        self.can_drop = can_drop

    def shorten(self, length):
        if len(self.text) <= length:
            return self
        elif length-3 <= 0:
            return None
        else:
            new_text = self.text[:length-3].strip() + '...'
            return TextSpan(new_text, len(new_text),
                            can_shorten=False, can_drop=self.can_drop)

    def __repr__(self):
        shorten_text = "can shorten" if self.can_shorten else "cannot shorten"
        drop_text = "can drop" if self.can_drop else "cannot drop"
        return "span({}={}, {}, {}".format(self.text, self.length,
                                           shorten_text, drop_text)
