import twitter
import re
import os

TWITTER_PERMALINK_RE = re.compile("https?://(?:www.)?twitter.com/(\w+)/status/(\w+)")

_api = None
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

def handle_new_or_edit(post):
    api = get_api()
    args = {
        'status' : create_status(post),
        'trim_user' : True
    }
    
    match = TWITTER_PERMALINK_RE.match(post.in_reply_to)
    if match:
        args['in_reply_to_status_id'] = match.group(2)

    api.statuses.update(**args)
        
def create_status(post):
    permalink = post.permalink_short_url

    if post.title:
        text = post.title
    else:
        text = post.content

    allowed_chars = 140 - 1 - len(permalink)
    text = text[:allowed_chars] + " " + permalink
    return text
