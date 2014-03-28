from app import *
from models import *
import json
import os
import os.path
import pytz
import itertools
from sqlalchemy import cast
import datetime

outdir = '_data'


def format_date(date):
    if date:
        if date.tzinfo:
            date = pytz.utc.localize(date)
            date = date.replace(tzinfo=None)
        return date.isoformat('T')


def filter_empty_keys(data):
    if isinstance(data, dict):
        return dict((k, filter_empty_keys(v)) for k, v in data.items() if v)
    return data


def write_mention(f, mention):
    data = {
        'source': mention.source,
        'permalink': mention.permalink,
        'type': mention.mention_type,
        'author': {
            'name': mention.author_name,
            'url': mention.author_url,
            'image': mention.author_image
        },
        'pub_date': format_date(mention.pub_date)
    }

    f.write(json.dumps(filter_empty_keys(data), indent=True))
    if mention.content:
        f.write('\n')
        f.write(dos2unix(mention.content))


def write_ext_post(f, post):
    data = {
        'source': post.source,
        'permalink': post.permalink,
        'title': post.title,
        'format': post.content_format,
        'pub_date': format_date(post.pub_date),
        'author': {
            'name': post.author_name,
            'url': post.author_url,
            'image': post.author_image,
        }
    }
    f.write(json.dumps(filter_empty_keys(data), indent=True))
    if post.content:
        f.write('\n')
        f.write(dos2unix(post.content))


def write_post(f, post):
    data = {
        'pub_date': format_date(post.pub_date),
        'title': post.title,
        'slug': post.slug,
        'type': post.post_type,
        'format': post.content_format,
        'latitude': post.latitude,
        'longitude': post.longitude,
        'location_name': post.location_name,
        'twitter_id': post.twitter_status_id,
        'facebook_id': post.facebook_post_id,
        'tags': [tag.name for tag in post.tags],
        'in_reply_to': post.in_reply_to.split() if post.in_reply_to else None,
        'repost_source': post.repost_source.split() if post.repost_source else None,
        'like_of': post.like_of.split() if post.like_of else None
    }
    f.write(json.dumps(filter_empty_keys(data), indent=True))
    if post.content:
        f.write('\n')
        f.write(dos2unix(post.content))


def dos2unix(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


for post in Post.query.all():
    path = "{}/{:04d}/{:02d}/{:02d}/{}{}".format(
        outdir,
        post.pub_date.year,
        post.pub_date.month,
        post.pub_date.day,
        post.post_type,
        post.date_index)

    if not os.path.exists(path):
        os.makedirs(path)

    print("serializing", post.pub_date)

    with open(os.path.join(path, 'post'), 'w') as f:
        write_post(f, post)

    for idx, mention in enumerate(post.mentions, start=1):
        with open(os.path.join(path, 'mention{}'.format(idx)), 'w') as f:
            write_mention(f, mention)

    for idx, context in enumerate(
            itertools.chain(post.share_contexts, post.like_contexts,
                            post.reply_contexts),
            start=1):
        with open(os.path.join(path, 'context{}'.format(idx)), 'w') as f:
            write_ext_post(f, context)
