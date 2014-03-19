from app import *
from models import *
import hentry_parser
from twitter_plugin import twitter_client
import requests
import json
import re
import datetime
from dateutil.parser import parse as parsedate
from bs4 import BeautifulSoup

twitter_permalink_re = re.compile(
    "https?://(?:www.)?twitter.com/(\w+)/status(?:es)?/(\w+)")

# for each post with a reply_to,a repost_source, or a like_of,
# generate contexts for it

def scrape_twitter(source, ExtPostClass):
        # user = User.query.first()
        # api = twitter_client.get_auth_session(user)
        # tweet_id = match.group(2)
        # status_response = api.get('statuses/show/{}.json'.format(tweet_id))

        # if status_response.status_code // 2 != 100:
        #     print("failed to fetch tweet", status_response,
        #           status_response.content)
        #     return None

        # status_data = status_response.json()

        # #pub_date = datetime.datetime.strptime(status_data['created_at'],
        # #                                      '%a %b %d %H:%M:%S %z %Y')
        # pub_date = parsedate(status_data['created_at'])
        # real_name = status_data['user']['name']
        # screen_name = status_data['user']['screen_name']
        # author_name = ("{} (@{})".format(real_name, screen_name)
        #                if real_name else screen_name)
        # author_url = (status_data['user']['url']
        #               or 'http://twitter.com/{}'.format(screen_name))
        # author_image = status_data['user']['profile_image_url']

        #content = status_data['text']

    response = requests.get(source)
    if response.status_code // 100 == 2:
        soup = BeautifulSoup(response.content)

        #jsondata = soup.find(class_='json-data').get('value')
        #print(json.dumps(json.loads(jsondata), indent=True))

        tweet = soup.find(class_='permalink-tweet')

        if not tweet:
            print("could not find tweet", source)
            return None

        fullname = next(tweet.find(class_='fullname').strings)
        username = tweet.find(class_='username').get_text()
        author_name = fullname  # "{} ({})".format(fullname, username)
        author_image = tweet.find(class_='avatar').get('src')
        author_url = 'https://twitter.com/{}'.format(username[1:])

        tweet_text = tweet.find(class_='tweet-text').get_text()
        metadata = tweet.find(class_='metadata')
        pub_date_str = metadata.find('span').get_text(strip=True)
        print('parsing', pub_date_str)
        pub_date = datetime.datetime.strptime(
            pub_date_str, '%I:%M %p - %d %b %Y')
        return ExtPostClass(source, source, None, tweet_text,
                            author_name, author_url,
                            author_image, pub_date)
    else:
        print("bad response", response)
        return None


def parse_external_post(source, ExtPostClass):
    print("parsing", source)
    match = twitter_permalink_re.match(source)

    if match:
        return scrape_twitter(source, ExtPostClass)

    response = requests.get(source)
    if response.status_code // 2 == 100:
        hentry = hentry_parser.parse(response.content, source)
        if hentry:
            return ExtPostClass(
                source,
                hentry.permalink,
                hentry.title, hentry.content,
                hentry.author.name if hentry.author else '',
                hentry.author.url if hentry.author else '',
                hentry.author.photo if hentry.author else '',
                hentry.pub_date, response.content)

    # get as much as we can without microformats
    soup = BeautifulSoup(response.content)
    title_tag = soup.find('title')
    title = title_tag.text if title_tag else 'no title'
    return ExtPostClass(source, source, title, None, None, None, None)


def fill_in_all_contexts(limit, offset):

    query = Post.query.order_by(Post.pub_date.desc())
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    for post in query:
        if post.repost_source:
            sharectx = parse_external_post(post.repost_source, ShareContext)

            if sharectx:
                print("share of:", sharectx)

                dupes = ShareContext.query.filter(
                    ShareContext.post == post,
                    ShareContext.permalink == sharectx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)

                db.session.add(sharectx)
                post.share_contexts.append(sharectx)

        if post.like_of:
            likectx = parse_external_post(post.like_of, LikeContext)
            if likectx:
                print("like of", likectx)
                dupes = LikeContext.query.filter(
                    LikeContext.post == post,
                    LikeContext.permalink == likectx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)

                db.session.add(likectx)
                post.like_contexts.append(likectx)

        if post.in_reply_to:
            replyctx = parse_external_post(post.in_reply_to, ReplyContext)
            if replyctx:
                print("reply to", replyctx)
                dupes = ReplyContext.query.filter(
                    ReplyContext.post == post,
                    ReplyContext.permalink == replyctx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)

                db.session.add(replyctx)
                post.reply_contexts.append(replyctx)

        post.repost_preview = None
        db.session.commit()
