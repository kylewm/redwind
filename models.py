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


from app import app

import datetime
import shortlinks
from util import base60
from collections import defaultdict
import os
import os.path
import json
import re
from operator import attrgetter

datadir = "_data"


def isoparse(s):
    return s and datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


class User:
    @classmethod
    def load(cls, path):
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_json(data)

    @classmethod
    def from_json(cls, data):
        user = cls(data.get('domain'))
        user.twitter_oauth_token = data.get('twitter_oauth_token')
        user.twitter_oauth_token_secret = data.get('twitter_oauth_token_secret')
        user.facebook_access_token = data.get('facebook_access_token')
        return user

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.domain

    def __init__(self, domain):
        self.domain = domain

    def __repr__(self):
        return '<User:{}>'.format(self.domain)


class Location:
    @classmethod
    def from_json(cls, data):
        return cls(data.get('latitude'),
                   data.get('longitude'),
                   data.get('name'))

    def __init__(self, lat, lon, name):
        self.latitude = lat
        self.longitude = lon
        self.name = name


class Post:

    @classmethod
    def load_recent(cls, count):
        def walk(path, files):
            print("walking", path)
            print("collected files", files)
            if len(files) >= count:
                return

            ls = sorted(os.listdir(path), reverse=True)
            for filename in ls:
                if filename == 'user':
                    continue
                newpath = os.path.join(path, filename)
                if os.path.isdir(newpath):
                    walk(newpath, files)
                else:
                    files.append(newpath)

        def load_from_path(path):
            filename = os.path.basename(path)
            match = re.match('([a-z]+)(\d+)', filename)
            post_type = match.group(1)
            date_index = int(match.group(2))
            return cls.load(path, post_type, date_index)

        files = []
        walk(datadir, files)

        posts = [load_from_path(f) for f in files]
        posts.sort(key=attrgetter('pub_date'), reverse=True)
        return posts

    @classmethod
    def load(cls, path, post_type, date_index):
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_json(data, post_type, date_index)

    @classmethod
    def from_json(cls, data, post_type, date_index):
        post = cls(post_type=data.get('post_type', post_type),
                   content_format=data.get('format', 'plain'))
        post.pub_date = isoparse(data.get('pub_date'))
        post.date_index = data.get('date_index', date_index)
        post.slug = data.get('slug')
        post.title = data.get('title')
        post.content = data.get('content', '')
        post.content_format = data.get('format')

        # FIXME these are redundant with contexts
        post.in_reply_to = data.get('in_reply_to')
        post.repost_source = data.get('repost_source')
        post.like_of = data.get('like_of')

        post.contexts = [Context.from_json(ctx) for ctx
                         in data.get('contexts', [])]
        post.mentions = [Mention.from_json(mnt) for mnt
                         in data.get('mentions', [])]
        post.draft = data.get('draft', False)

        if 'location' in data:
            post.location = Location.from_json(data.get('location', {}))

        if 'syndication' in data:
            synd = data.get('syndication', {})
            post.twitter_status_id = synd.get('twitter_id')
            post.facebook_post_id = synd.get('facebook_id')
        return post

    @classmethod
    def lookup_post_by_date(cls, post_type, year, month, day, index):
        path = os.path.join(datadir, year, month, day, post_type + index)
        return Post.load(path, post_type, index)

    def __init__(self, post_type, content_format):
        self.post_type = post_type
        self.content_format = content_format
        self.draft = True
        self.contexts = []
        self.mentions = []

    @property
    def mentions_categorized(self):
        cat = defaultdict(list)
        for mention in self.mentions:
            cat[mention.mention_type].append(mention)
        return cat

    @property
    def permalink(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'

        path_components = [site_url,
                           self.post_type,
                           self.pub_date.strftime('%Y/%m/%d'),
                           str(self.date_index)]
        if self.slug:
            path_components.append(self.slug)

        return '/'.join(path_components)

    @property
    def short_permalink(self):
        tag = shortlinks.tag_for_post_type(self.post_type)
        ordinal = shortlinks.date_to_ordinal(self.pub_date.date())
        return '{}/{}{}{}'.format(app.config.get('SHORT_SITE_URL'),
                                  tag, base60.encode(ordinal),
                                  base60.encode(self.date_index))

    @property
    def short_cite(self):
        tag = shortlinks.tag_for_post_type(self.post_type)
        ordinal = shortlinks.date_to_ordinal(self.pub_date.date())
        cite = '({} {}{}{})'.format(app.config.get('SHORT_SITE_CITE'),
                                    tag, base60.encode(ordinal),
                                    base60.encode(self.date_index))
        return cite

    @property
    def twitter_url(self):
        if self.twitter_status_id:
            return "https://twitter.com/{}/status/{}".format(
                self.author.twitter_username,
                self.twitter_status_id)

    @property
    def facebook_url(self):
        if self.facebook_post_id:
            split = self.facebook_post_id.split('_', 1)
            if split and len(split) == 2:
                user_id, post_id = split
                return "https://facebook.com/{}/posts/{}"\
                    .format(user_id, post_id)

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.title)
        else:
            return 'post:{}'.format(self.content[:140])


class Context:
    """reply-context, repost-context, like-context
       all contain nearly the same data"""

    @classmethod
    def from_json(cls, data):
        return cls(data.get('source'),
                   data.get('permalink'),
                   data.get('title'),
                   data.get('content'),
                   data.get('format'),
                   data.get('author', {}).get('name'),
                   data.get('author', {}).get('url'),
                   data.get('author', {}).get('image'),
                   isoparse(data.get('pub_date')))

    def __init__(self, source, permalink, title, content,
                 content_format, author_name, author_url,
                 author_image, pub_date=None):
        self.source = source
        self.permalink = permalink
        self.title = title
        self.content = content
        self.content_format = content_format
        self.author_name = author_name
        self.author_url = author_url
        self.author_image = author_image
        self.pub_date = pub_date

    def __repr__(self):
        return "<{}: source={}, permalink={}, content={}, date={}, "\
            "author=({}, {}, {})>"\
            .format(self.__class__.__name__,
                    self.source, self.permalink, self.content, self.pub_date,
                    self.author_name, self.author_url,
                    self.author_image)


class Mention:

    @classmethod
    def from_json(cls, data):
        return cls(data.get('source'),
                   data.get('permalink'),
                   data.get('content'),
                   data.get('type'),
                   data.get('author', {}).get('name'),
                   data.get('author', {}).get('url'),
                   data.get('author', {}).get('image'),
                   isoparse(data.get('pub_date')))

    def __init__(self, source, permalink, content, mention_type,
                 author_name, author_url, author_image, pub_date=None):
        self.source = source
        self.permalink = permalink
        self.content = content
        self.mention_type = mention_type
        self.author_name = author_name
        self.author_url = author_url
        self.author_image = author_image
        self.pub_date = pub_date or datetime.datetime.utcnow()

    def __repr__(self):
        return "<Mention: type={}, source={}, permalink={}, author=({}, {}, {})>"\
            .format(self.mention_type, self.source, self.permalink,
                    self.author_name, self.author_url, self.author_image)
