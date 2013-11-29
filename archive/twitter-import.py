
import os
import os.path
import re
import yaml
from api import slugify
import datetime
import json
import csv 

from app import db
from models import *

import twitter

kyle = User.query.filter(User.login=='kyle').first()


Post.query.filter(Post.post_type == 'note').delete()
db.session.commit()


id_to_name = None
with open('user-id-to-name.json') as f:
    id_to_name = json.load(f)

with open('tweets.csv') as f:
    reader = csv.reader(f)
    for row in reader:
        if reader.line_num <= 1: 
            continue

        tweet_id = row[0]
        in_reply_to_status = row[1]
        in_reply_to_user_id = row[2]
        in_reply_to_user = id_to_name.get(in_reply_to_user_id)
        in_reply_to = "http://twitter.com/{}/status/{}".format(in_reply_to_user, in_reply_to_status) if in_reply_to_status else ""
        timestamp = row[3]
        content = row[5]
        retweet_status = row[6]
        retweet_user_id = row[7]
        retweet_user = id_to_name.get(retweet_user_id)
        repost_source = "http://twitter.com/{}/status/{}".format(retweet_user, retweet_status) if retweet_status else ""
        date = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
            
        post = Post("", "", content, 'note', 'plain', kyle, date)
        post.twitter_status_id = tweet_id
        if in_reply_to:
            post.in_reply_to = in_reply_to
        if repost_source:
            post.repost_source = repost_source


        db.session.add(post)

db.session.commit()



#CONSUMER_KEY = "Cm9wmVhNTgES6xm2mUwRtg"
#CONSUMER_SECRET = "CvtRQR9LzP2QF0JhNGmb9ZHKi6PwQrf2uz7ghbplCFo"
#MY_TWITTER_CREDS = os.path.expanduser('~/.groomsman/twitter_credentials')
#if not os.path.exists(MY_TWITTER_CREDS):
#    twitter.oauth_dance("groomsman-kylewm.com", CONSUMER_KEY, CONSUMER_SECRET,
#                        MY_TWITTER_CREDS)
#
#oauth_token, oauth_secret = twitter.read_token_file(MY_TWITTER_CREDS)
#    
#t = twitter.Twitter(auth=twitter.OAuth(
#    oauth_token, oauth_secret, CONSUMER_KEY, CONSUMER_SECRET))
#
#user_ids = list(user_ids)
#for i in range(0, len(user_ids), 75):
#    chunk = user_ids[i:i+75]
#    result = t.users.lookup(user_id=",".join(chunk))
#    for entry in result:
#        userid = entry['id']
#        username = entry['screen_name']
#        id_to_name[userid] = username
#    
#with open('user-id-to-name.json', 'w') as f:
#    json.dump(id_to_name, f)




tweets = None
with open("twitter-archive-2009-2011.json") as f:
   tweets = json.load(f)

for tweet in tweets:
   content = tweet.get('content')
   content_type = 'note'
   content_format = 'plain'
   date = datetime.datetime.strptime(tweet.get('created at'), "%Y-%m-%dT%H:%MZ")
   post = Post("", "", content, content_type, content_format, kyle, date)


   if 'in reply to' in tweet:
       reply_to = "http://twitter.com/{}/statuses/{}".format(
           tweet['in reply to']['screenname'],
           tweet['in reply to']['status id'])
       post.in_reply_to = reply_to
  
   db.session.add(post)


db.session.commit()
