from app import app, db
from models import User, Post, Mention
import twitter
from twitter import TwitterHTTPError
import time
from datetime import datetime
from sqlalchemy.sql import exists

ID_FILE_NAME = '.twitter_monitor_ids'
DATE_FORMAT = '%a %b %d %H:%M:%S %z %Y'
oldest = None
most_recent = None

try:
    with open(ID_FILE_NAME) as idfile:
        oldest = idfile.readline()
        most_recent = idfile.readline()
except FileExistsError:
    pass
except FileNotFoundError:
    pass

def get_user():
    user = User.query.filter_by(twitter_username='kyle_wm').first()
    return user


def get_api():
    user = get_user()
    consumer_key = app.config['TWITTER_CONSUMER_KEY']
    consumer_secret = app.config['TWITTER_CONSUMER_SECRET']
    oauth_token = user.twitter_oauth_token
    oauth_secret = user.twitter_oauth_token_secret
    return twitter.Twitter(auth=twitter.OAuth(oauth_token, oauth_secret,
                                              consumer_key, consumer_secret))

def max_id(s1, s2):
    if not s1:
        return s2
    if not s2:
        return s1

    s1pad = s1.zfill(len(s2))
    s2pad = s2.zfill(len(s1))
    return s1 if s1 > s2 else s2


def min_id(s1, s2):
    if not s1:
        return s2
    if not s2:
        return s1

    s1pad = s1.zfill(len(s2))
    s2pad = s2.zfill(len(s1))
    return s1 if s1pad < s2pad else s2


def check_for_replies(t):
    global most_recent
    global oldest

    print("Checking for replies since {}".format(most_recent))
    attrs = {}
    attrs['count'] = 200
    if most_recent:
        attrs['since_id'] = most_recent

    mentions = t.statuses.mentions_timeline(**attrs)

    print("Got: {}".format(len(mentions)))

    for mention in mentions:
        status_id = mention['id_str']
        reply_to_id = mention['in_reply_to_status_id_str']
        text = mention['text']
        user_name = mention['user']['name']
        screen_name = mention['user']['screen_name']
        created_at = mention['created_at']
        created_date = datetime.strptime(created_at, DATE_FORMAT)

        most_recent = max_id(most_recent, status_id)
        oldest = min_id(oldest, status_id)

        if reply_to_id:
            target = Post.query.filter_by(twitter_status_id=reply_to_id).first()
            mention = Mention(
                'https://twitter.com/{}/status/{}'.format(screen_name,
                                                          status_id),
                target, text, True,
                '{} (@{})'.format(user_name, screen_name),
                'https://twitter.com/{}'.format(screen_name),
                created_date)

            prev=Mention.query.filter_by(source=mention.source).first()
            if prev:
                db.session.delete(prev)
            db.session.add(mention)

    db.session.commit()

    with open(ID_FILE_NAME, 'w') as idfile:
          idfile.write('\n'.join((oldest, most_recent)))


def poll():
    wait_min = 60
    wait_max = 15*60
    wait = 60

    t = get_api()
    while True:
        try:
            check_for_replies(t)
            wait = max(wait / 2, wait_min)
        except TwitterHTTPError as e:
            print("got an error, waiting longer", e)
            wait = min(wait * 2, wait_max)
        print("waiting for {} seconds".format(wait))
        time.sleep(wait)



if __name__ == '__main__':
    poll()
