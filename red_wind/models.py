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
from .util import shortlinks, base60

import datetime
from collections import defaultdict
import os
import os.path
import json
import pytz
import tempfile
import shutil
import time
from operator import attrgetter
from contextlib import contextmanager


datadir = '_data'
backupdir = os.path.join(datadir, '.backup')


def isoparse(s):
    if s:
        try:
            return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f')
        except:
            return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


def format_date(date):
    if date:
        if date.tzinfo:
            date = date.astimezone(pytz.utc)
            date = date.replace(tzinfo=None)
        date = date.replace(microsecond=0)
        return date.isoformat('T')


def filter_empty_keys(data):
    if isinstance(data, list):
        return list(filter_empty_keys(v) for v in data if filter_empty_keys(v))
    if isinstance(data, dict):
        return dict((k, filter_empty_keys(v)) for k, v in data.items()
                    if filter_empty_keys(v))
    return data


def save_backup(sourcedir, destdir, relpath):
    source = os.path.join(sourcedir, relpath)
    if os.path.exists(source):
        now = datetime.datetime.now()
        target = os.path.join(destdir, relpath
                              + "-" + format_date(now))
        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        shutil.copy(source, target)


@contextmanager
def acquire_lock(path, retries):
    lockfile = path+'.lock'
    if not os.path.exists(os.path.dirname(lockfile)):
        os.makedirs(os.path.dirname(lockfile))
    while os.path.exists(lockfile) and retries > 0:
        time.sleep(1)
        retries -= 1
    if os.path.exists(lockfile):
        raise RuntimeError("Timed out waiting for lock to become available {}"
                           .format(lockfile))
    try:
        with open(lockfile, 'w') as f:
            f.write("1")
        yield
    finally:
        os.remove(lockfile)


class User:

    @classmethod
    def load(cls, path):
        app.logger.debug("loading from path %s", path)
        if os.path.exists(path):
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

    def to_json(self):
        data = {
            'domain': self.domain,
            'twitter_oauth_token': self.twitter_oauth_token,
            'twitter_oauth_token_secret': self.twitter_oauth_token_secret,
            'facebook_access_token': self.facebook_access_token
        }
        return filter_empty_keys(data)

    def save(self):
        _, temp = tempfile.mkstemp()
        with open(temp, 'w') as f:
            json.dump(self.to_json(), f, indent=True)

        filename = os.path.join(datadir, 'user')
        if os.path.exists(filename):
            save_backup(datadir, backupdir, 'user')
        shutil.move(temp, filename)

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

    def to_json(self):
        return {
            'latitude' : self.latitude,
            'longitude': self.longitude,
            'name': self.name
            }


class Post:

    @classmethod
    @contextmanager
    def writeable(cls, path):
        with acquire_lock(path, 30):
            post = cls.load(path)
            post._writeable = True
            yield post
            post._writeable = False

    @classmethod
    def load(cls, path):
        app.logger.debug("loading from path %s", path)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            post = cls.from_json(data)
            return post

    @classmethod
    def load_recent(cls, count, post_types, include_drafts=False):
        def walk(path, posts):
            if len(posts) >= count:
                return

            ls = sorted(os.listdir(path), reverse=True)
            for filename in ls:
                newpath = os.path.join(path, filename)
                if os.path.isdir(newpath):
                    walk(newpath, posts)
                else:
                    filename = os.path.basename(newpath)
                    post_type, date_index = filename.split('_')
                    if not post_types or post_type in post_types:
                        post = cls.load(newpath)
                        if not post.deleted and (not post.draft
                                                 or include_drafts):
                            posts.append(post)

        posts = []
        walk(os.path.join(datadir, 'posts'), posts)
        posts.sort(key=attrgetter('pub_date'), reverse=True)
        return posts[:count]

    @classmethod
    def load_by_month(cls, year, month):
        posts = []
        path = os.path.join(datadir, 'posts', "{}/{:02d}".format(year, month))
        days = os.listdir(path)
        for day in days:
            daypath = os.path.join(path, day)
            for filename in os.listdir(daypath):
                filepath = os.path.join(daypath, filename)
                post = cls.load(filepath)
                if not post.deleted:
                    posts.append(post)
        posts.sort(key=attrgetter('pub_date'), reverse=True)
        return posts

    @classmethod
    def load_by_date(cls, post_type, year, month, day, index):
        return cls.load(
            cls.date_to_path(post_type, year, month, day, index))

    @classmethod
    def load_by_shortid(cls, shortid):
        return cls.load(cls.shortid_to_path(shortid))

    @classmethod
    def date_to_path(cls, post_type, year, month, day, index):
        return cls.relpath_to_fullpath("{}/{:02d}/{:02d}/{}_{}"
                                       .format(year, month, day,
                                               post_type, index))

    @classmethod
    def shortid_to_path(cls, shortid):
        post_type = shortlinks.parse_type(shortid)
        pub_date = shortlinks.parse_date(shortid)
        index = shortlinks.parse_index(shortid)
        return cls.relpath_to_fullpath('{}/{:02d}/{:02d}/{}_{}'
                                       .format(pub_date.year, pub_date.month,
                                               pub_date.day, post_type, index))

    @classmethod
    def relpath_to_fullpath(cls, path):
        return os.path.join(datadir, 'posts', path)

    @classmethod
    def get_archive_months(cls):
        result = []
        path = os.path.join(datadir, 'posts')
        for year in os.listdir(path):
            yearpath = os.path.join(path, year)
            for month in os.listdir(yearpath):
                first_of_month = datetime.date(int(year), int(month), 1)
                result.append(first_of_month)
        result.sort(reverse=True)
        return result

    @classmethod
    def from_json(cls, data):
        post = cls(post_type=data.get('type', 'note'),
                   content_format=data.get('format', 'plain'))
        post.pub_date = isoparse(data.get('pub_date'))
        post.date_index = data.get('date_index', 1)
        post.slug = data.get('slug')
        post.title = data.get('title')
        post.content = data.get('content', '')
        post.content_format = data.get('format')

        # FIXME these are redundant with contexts
        post.in_reply_to = '\n'.join(data.get('in_reply_to', []))
        post.repost_source = '\n'.join(data.get('repost_source', []))
        post.like_of = '\n'.join(data.get('like_of', []))

        contexts = data.get('context', {})
        post.reply_contexts = [Context.from_json(ctx) for ctx
                               in contexts.get('reply', [])]
        post.share_contexts = [Context.from_json(ctx) for ctx
                               in contexts.get('share', [])]
        post.like_contexts = [Context.from_json(ctx) for ctx
                              in contexts.get('like', [])]

        post.mentions = [Mention.from_json(mnt) for mnt
                         in data.get('mentions', [])]
        post.draft = data.get('draft', False)
        post.deleted = data.get('deleted', False)

        if 'location' in data:
            post.location = Location.from_json(data.get('location', {}))

        if 'syndication' in data:
            synd = data.get('syndication', {})
            post.twitter_status_id = synd.get('twitter_id')
            post.facebook_post_id = synd.get('facebook_id')
        return post

    def __init__(self, post_type, content_format):
        self.post_type = post_type
        self.content_format = content_format
        self.draft = True
        self.deleted = False
        self.reply_contexts = []
        self.share_contexts = []
        self.like_contexts = []
        self.mentions = []

        self.pub_date = None
        self.date_index = None
        self.slug = None
        self.twitter_status_id = None
        self.facebook_post_id = None
        self.location = None
        self._writeable = False

    def to_json(self):
        data = {
            'type': self.post_type,
            'pub_date':  format_date(self.pub_date),
            'date_index': self.date_index,
            'slug': self.slug,
            'title': self.title,
            'content': self.content,
            'format': self.content_format,
            'in_reply_to': self.in_reply_to.split() if self.in_reply_to else None,
            'repost_source': self.repost_source.split() if self.repost_source else None,
            'like_of': self.like_of.split() if self.like_of else None,
            'context': {
                'reply': [ctx.to_json() for ctx in self.reply_contexts],
                'share': [ctx.to_json() for ctx in self.share_contexts],
                'like': [ctx.to_json() for ctx in self.like_contexts]
            },
            'mentions': [mnt.to_json() for mnt in self.mentions],
            'location': self.location and self.location.to_json(),
            'syndication': {
                'twitter_id': self.twitter_status_id,
                'facebook_id': self.facebook_post_id
            },
            'draft': self.draft,
            'deleted': self.deleted
        }
        return filter_empty_keys(data)

    def save(self):
        if not self._writeable:
            raise RuntimeError("Cannot save post that was not opened with the 'writeable' flag")

        basedir = os.path.join(datadir, 'posts')

        # assign a new date index if we don't have one yet
        if not self.date_index:
            self.date_index = 1
            while os.path.exists(os.path.join(basedir, self.path)):
                self.date_index += 1

        filename = os.path.join(basedir, self.path)
        parentdir = os.path.dirname(filename)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir)

        _, temp = tempfile.mkstemp()
        with open(temp, 'w') as f:
            json.dump(self.to_json(), f, indent=True)

        save_backup(basedir, os.path.join(backupdir, 'posts'), self.path)
        shutil.move(temp, filename)

    @property
    def path(self):
        return "{}/{:02d}/{:02d}/{}_{}".format(
            self.pub_date.year, self.pub_date.month, self.pub_date.day,
            self.post_type, self.date_index)

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
    def shortid(self):
        if not self.pub_date or not self.date_index:
            return None
        tag = shortlinks.tag_for_post_type(self.post_type)
        ordinal = shortlinks.date_to_ordinal(self.pub_date.date())
        return '{}{}{}'.format(tag, base60.encode(ordinal),
                               base60.encode(self.date_index))

    @property
    def short_permalink(self):
        return '{}/{}'.format(app.config.get('SHORT_SITE_URL'),
                              self.shortid)

    @property
    def short_cite(self):
        tag = shortlinks.tag_for_post_type(self.post_type)
        ordinal = shortlinks.date_to_ordinal(self.pub_date.date())
        cite = '{} {}{}{}'.format(app.config.get('SHORT_SITE_CITE'),
                                  tag, base60.encode(ordinal),
                                  base60.encode(self.date_index))
        return cite

    @property
    def twitter_url(self):
        if self.twitter_status_id:
            return "https://twitter.com/{}/status/{}".format(
                'kyle_wm',  # FIXME
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

    def to_json(self):
        data = {
            'source': self.source,
            'permalink': self.permalink,
            'title': self.title,
            'content': self.content,
            'format': self.content_format,
            'author': {
                'name': self.author_name,
                'url': self.author_url,
                'image': self.author_image
            },
            'pub_date': format_date(self.pub_date)
        }
        return filter_empty_keys(data)

    def __repr__(self):
        return "<{}: source={}, permalink={}, content={}, date={}, "\
            "author=({}, {}, {})>"\
            .format(self.__class__.__name__,
                    self.source, self.permalink, self.content, self.pub_date,
                    self.author_name, self.author_url,
                    self.author_image)


class Mention:

    @classmethod
    def update_recent(cls, post_id):
        """post received a comment, add it to the front of the list of
           recently commented posts"""
        filename = os.path.join(datadir, 'recent_mentions')
        with acquire_lock(filename, 30):
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    recent = json.load(f)
            else:
                recent = []

            if post_id in recent:
                recent.remove(post_id)
            recent.insert(0, post_id)
            with open(filename, 'w') as f:
                json.dump(recent[:30], f)

    @classmethod
    def from_json(cls, data):
        return cls(data.get('source'),
                   data.get('permalink'),
                   data.get('content'),
                   data.get('type'),
                   data.get('author', {}).get('name'),
                   data.get('author', {}).get('url'),
                   data.get('author', {}).get('image'),
                   isoparse(data.get('pub_date')),
                   data.get('deleted', False))

    def __init__(self, source, permalink, content, mention_type,
                 author_name, author_url, author_image,
                 pub_date=None, deleted=False):
        self.source = source
        self.permalink = permalink
        self.content = content
        self.mention_type = mention_type
        self.author_name = author_name
        self.author_url = author_url
        self.author_image = author_image
        self.pub_date = pub_date or datetime.datetime.utcnow()
        self.deleted = deleted

    def to_json(self):
        data = {
            'source': self.source,
            'permalink': self.permalink,
            'type': self.mention_type,
            'content': self.content,
            'author': {
                'name': self.author_name,
                'url': self.author_url,
                'image': self.author_image
            },
            'pub_date': format_date(self.pub_date),
            'deleted': self.deleted
        }
        return filter_empty_keys(data)

    def __repr__(self):
        return "<Mention: type={}, source={}, permalink={}, author=({}, {}, {})>"\
            .format(self.mention_type, self.source, self.permalink,
                    self.author_name, self.author_url, self.author_image)
