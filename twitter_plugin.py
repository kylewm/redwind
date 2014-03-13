from app import app, db
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, make_response
from rauth import OAuth1Service
import requests
import re
from datetime import datetime, timedelta


def get_auth_service():
    if not get_auth_service.cached:
        key = app.config['TWITTER_CONSUMER_KEY']
        secret = app.config['TWITTER_CONSUMER_SECRET']
        get_auth_service.cached = OAuth1Service(
            name='twitter',
            consumer_key=key,
            consumer_secret=secret,
            request_token_url='https://api.twitter.com/oauth/request_token',
            access_token_url='https://api.twitter.com/oauth/access_token',
            authorize_url='https://api.twitter.com/oauth/authorize',
            base_url='https://api.twitter.com/1.1/')
    return get_auth_service.cached

get_auth_service.cached = None


def get_auth_session(user):
    service = get_auth_service()
    session = service.get_session((user.twitter_oauth_token,
                                   user.twitter_oauth_token_secret))
    return session


@app.route('/admin/authorize_twitter')
@login_required
def authorize_twitter():
    """Get an access token from Twitter and redirect to the
       authentication page"""
    callback_url = url_for('authorize_twitter2', _external=True)
    try:
        twitter = get_auth_service()
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
        twitter = get_auth_service()
        access_token, access_token_secret = twitter.get_access_token(
            oauth_token,'', method='POST',
            params={'oauth_verifier': oauth_verifier})

        current_user.twitter_oauth_token = access_token
        current_user.twitter_oauth_token_secret = access_token_secret

        db.session.commit()
        return redirect(url_for('settings'))
    except requests.RequestException as e:
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
            api = get_auth_session(user)
            tweet_id = match.group(2)
            embed_response = api.get('statuses/oembed.json',
                                     params={'id': tweet_id})

            if embed_response.status_code // 2 == 100:
                return embed_response.json().get('html')

    def handle_new_or_edit(self, post):
        if not self.is_twitter_authorized(post.author):
            return

        permalink_re = re.compile(
            "https?://(?:www.)?twitter.com/(\w+)/status/(\w+)")
        api = get_auth_session(post.author)
        # check for RT's
        repost_match = permalink_re.match(post.repost_source)
        like_match = permalink_re.match(post.like_of)

        if repost_match:
            tweet_id = repost_match.group(2)
            result = api.post('statuses/retweet/{}.json'.format(tweet_id),
                              data={'trim_user': True})
            if result.status_code // 2 != 100:
                raise RuntimeError("{}: {}".format(str(result),
                                                   str(result.content)))

        elif like_match:
            tweet_id = like_match.group(2)
            result = api.post('favorites/create.json',
                              data={'id': tweet_id, 'trim_user': True})
            if result.status_code // 2 != 100:
                raise RuntimeError("{}: {}".format(str(result),
                                                   str(result.content)))

        else:
            data = {}
            data['status'] = self.create_status(post)
            data['trim_user'] = True
            reply_match = permalink_re.match(post.in_reply_to)
            if reply_match:
                data['in_reply_to_status_id'] = reply_match.group(2)
            result = api.post('statuses/update.json', data=data)

            if result.status_code // 2 != 100:
                raise RuntimeError("{}: {}".format(str(result),
                                                   str(result.content)))

        post.twitter_status_id = result.json().get('id_str')

    def is_twitter_authorized(self, user):
        return user.twitter_oauth_token and user.twitter_oauth_token_secret

    def get_help_configuration(self, user):
        stale_limit = timedelta(days=1)

        if (not self.cached_config
                or datetime.utcnow() - self.config_fetch_date > stale_limit):
            api = get_auth_session(user)
            response = api.get('help/configuration.json')
            if response.status_code // 2 == 100:
                self.cached_config = response.json()
                self.config_fetch_date = datetime.utcnow()
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

    def url_to_span(self, user, url, prefix='', postfix='', can_drop=True):
        twitter_config = self.get_help_configuration(user)
        if twitter_config:
            url_length = twitter_config.get('short_url_length_https'
                                            if url.startswith('https')
                                            else 'short_url_length')
        else:
            url_length = 30

        app.logger.debug("assuming url length {}".format(url_length))
        return TextSpan(prefix + url + postfix,
                        len(prefix) + url_length + len(postfix),
                        can_shorten=False, can_drop=can_drop)

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
                          self.url_to_span(post.author,
                                           post.permalink_url,
                                           can_drop=False)]

        else:
            components = self.split_out_urls(post.author, post.content)

            # include the re-shared link
            if post.repost_source:
                components.append(self.url_to_span(post.author,
                                                   post.repost_source,
                                                   can_drop=False))

            components.append(self.text_to_span(post.short_cite,
                                                can_drop=False,
                                                can_shorten=False))

            # if that overflows, replace with a permalink
            if self.estimate_length(components) > target_length:
                components.pop()
                components.append(self.url_to_span(post.author,
                                                   post.permalink_url,
                                                   can_drop=False))

        status = self.run_shorten_algorithm(components, target_length)
        self.app.logger.debug("shortened to (%d) for twitter '%s'",
                              len(status), status)
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
