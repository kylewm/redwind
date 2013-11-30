import twitter
import re
import os
from app import app

TWITTER_PERMALINK_RE = re.compile("https?://(?:www.)?twitter.com/(\w+)/status/(\w+)")

def handle_new_or_edit(post):
    api = get_api()
    # check for RT's
    match = TWITTER_PERMALINK_RE.match(post.repost_source)
    if match:
        api.statuses.retweet(id=match.group(2), trim_user=True)
    else:
        match = TWITTER_PERMALINK_RE.match(post.in_reply_to)
        in_reply_to = match.group(2) if match else None
        result = api.statuses.update(status=create_status(post),
                                     in_reply_to_status_id=in_reply_to,
                                     trim_user=True)
        if result:
            post.twitter_status_id = result.get('id_str')
        

def get_api():
    if not get_api.cached: 
        CONSUMER_KEY = "Cm9wmVhNTgES6xm2mUwRtg"
        CONSUMER_SECRET = "CvtRQR9LzP2QF0JhNGmb9ZHKi6PwQrf2uz7ghbplCFo"
        MY_TWITTER_CREDS = os.path.expanduser('~/.groomsman/twitter_credentials')
        if not os.path.exists(MY_TWITTER_CREDS):
            twitter.oauth_dance("groomsman-kylewm.com", CONSUMER_KEY, CONSUMER_SECRET,
                                MY_TWITTER_CREDS)
        oauth_token, oauth_secret = twitter.read_token_file(MY_TWITTER_CREDS)
        get_api.cached = twitter.Twitter(auth=twitter.OAuth(oauth_token, oauth_secret,
                                                  CONSUMER_KEY, CONSUMER_SECRET))
    return get_api.cached

get_api.cached = None

def create_status(post):
    """Create a <140 status message suitable for twitter"""
    permalink = post.permalink_short_url

    if post.title:
        text = post.title
    else:
        text = post.content

    allowed_chars = 140 - 1 - len(permalink)
    text = text[:allowed_chars] + " " + permalink
    return text
