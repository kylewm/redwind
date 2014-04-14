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


from . import app
from . import util

import datetime
import os
import os.path
import itertools
import json
import tempfile
import shutil
import time
import re
import urllib
from operator import attrgetter
from contextlib import contextmanager


def isoparse(s):
    """Parse (UTC) datetimes in ISO8601 format"""
    return s and datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


def format_date(date):
    if date:
        if date.tzinfo:
            date = date.astimezone(datetime.timezone.utc)
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


def format_to_extension(fmt):
    if fmt == 'html':
        return '.html'
    elif fmt == 'markdown':
        return '.md'
    elif fmt == 'plain':
        return '.txt'
    else:
        app.logger.warn("Unknown format type %s, assuming plain text", fmt)
        return '.txt'


def extension_to_format(ext):
    if ext == '.html':
        return 'html'
    elif ext == '.md':
        return 'markdown'
    elif ext == '.txt':
        return 'plain'
    else:
        app.logger.warn("Unknown extension type %s, assuming plain text", ext)
        return 'plain'


class User:

    @classmethod
    def load(cls, path):
        app.logger.debug("loading from path %s", os.path.abspath(path))
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

        filename = os.path.join(app.root_path, '_data/user.json')
        if os.path.exists(filename):
            save_backup(os.path.join(app.root_path, '_data'),
                        os.path.join(app.root_path, '_data/.backup'), 'user.json')
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
            'latitude': self.latitude,
            'longitude': self.longitude,
            'name': self.name
            }


class Post:
    FILE_PATTERN = re.compile('(\w+)_(\d+)(\.html|\.md|\.txt)$')

    @staticmethod
    def parse_json_frontmatter(fp):
        """parse a multipart file that starts with a json blob"""
        depth = 0
        json_lines = []
        for line in fp:
            prev = None
            quoted = False
            for c in line:
                if c == '"' and prev != '\\':
                    quoted = not quoted
                else:
                    if not quoted:
                        if c == '{':
                            depth += 1
                        elif c == '}':
                            depth -= 1
                prev = c
            json_lines.append(line)
            if depth == 0:
                break
        head = json.loads(''.join(json_lines))
        body = '\n'.join(line.strip('\r\n') for line in fp.readlines())
        return head, body

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

        path = next((path for path in (path, path+'.md', path+'.html', path+'.txt')
                     if os.path.exists(path)), None)
        if not path:
            app.logger.warn("No post found at %s", path)
            return None

        basename = os.path.basename(path)
        match = cls.FILE_PATTERN.match(basename)
        if not match:
            raise RuntimeError("trying to load from unrecognized path {}"
                               .format(path))

        post_type = match.group(1)
        date_index = int(match.group(2))
        content_format = extension_to_format(match.group(3))

        with open(path, 'r') as fp:
            head, body = Post.parse_json_frontmatter(fp)

        post = cls(post_type, content_format, date_index)
        post.read_json_blob(head)
        post.content = body
        return post

    @classmethod
    def load_by_path(cls, path):
        return cls.load(cls.relpath_to_fullpath(path))

    @classmethod
    def load_recent(cls, count, post_types, include_drafts=False):
        return list(itertools.islice(
            cls.iterate_all(reverse=True, post_types=post_types,
                            include_drafts=include_drafts),
            0, count))

    @classmethod
    def load_by_month(cls, year, month):
        posts = []
        path = os.path.join(app.root_path,
                            '_data/posts/{}/{:02d}'.format(year, month))
        days = os.listdir(path)
        for day in days:
            daypath = os.path.join(path, day)
            for filename in os.listdir(daypath):
                if Post.FILE_PATTERN.match(filename):
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
    def iterate_all(cls, reverse=False, post_types=None, include_drafts=False):
        path = os.path.join(app.root_path, '_data/posts')
        for root, dirs, files in os.walk(path):
            dirs.sort(reverse=reverse)
            today = []
            for filename in files:

                match = cls.FILE_PATTERN.match(filename)
                if match:
                    post_type = match.group(1)
                    if not post_types or post_type in post_types:
                        post = cls.load(os.path.join(root, filename))
                        if not post.deleted and (not post.draft
                                                 or include_drafts):
                            today.append(post)

            today.sort(key=attrgetter('pub_date'), reverse=reverse)
            yield from today

    @classmethod
    def date_to_path(cls, post_type, year, month, day, index):
        return cls.relpath_to_fullpath("{}/{:02d}/{:02d}/{}_{}"
                                       .format(year, month, day,
                                               post_type, index))

    @classmethod
    def shortid_to_path(cls, shortid):
        post_type = util.parse_type(shortid)
        pub_date = util.parse_date(shortid)
        index = util.parse_index(shortid)
        return cls.relpath_to_fullpath('{}/{:02d}/{:02d}/{}_{}'
                                       .format(pub_date.year, pub_date.month,
                                               pub_date.day, post_type, index))

    @classmethod
    def relpath_to_fullpath(cls, path):
        return os.path.join(app.root_path, '_data/posts', path)

    @classmethod
    def get_archive_months(cls):
        result = []
        path = os.path.join(app.root_path, '_data/posts')
        for year in os.listdir(path):
            yearpath = os.path.join(path, year)
            for month in os.listdir(yearpath):
                first_of_month = datetime.date(int(year), int(month), 1)
                result.append(first_of_month)
        result.sort(reverse=True)
        return result

    @classmethod
    def load_syndication_index(cls):
        path = os.path.join(app.root_path, '_data/syndication_index.json')
        return json.load(open(path, 'r'))

    def update_syndication_index(self, url):
        path = os.path.join(app.root_path, '_data/syndication_index.json')
        with acquire_lock(path, 30):
            obj = json.load(open(path, 'r'))
            obj[url] = self.path
            json.dump(obj, open(path, 'w'), indent=True)
    
    @classmethod
    def load_recent_mentions(cls):
        path = os.path.join(app.root_path, '_data/recent_mentions.json')
        if os.path.exists(path):
            return json.load(open(path, 'r'))
        else:
            return []

    @classmethod
    def update_recent_mentions(self, url):
        path = os.path.join(app.root_path, '_data/recent_mentions.json')
        with acquire_lock(path, 30):
            if os.path.exists(path):
                obj = json.load(open(path, 'r'))
            else:
                obj = []
            obj.insert(0, url)
            json.dump(obj[:10], open(path, 'w'), indent=True)
    
    def __init__(self, post_type, content_format, date_index):
        self.post_type = post_type
        self.content_format = content_format
        self.date_index = date_index
        self.draft = True
        self.deleted = False
        self.in_reply_to = []
        self.repost_of = []
        self.like_of = []
        self.pub_date = None
        self.slug = None
        self.twitter_status_id = None
        self.facebook_post_id = None
        self.location = None
        self._mentions = None  # lazy load mentions
        self._writeable = False

    def read_json_blob(self, data):
        self.pub_date = isoparse(data.get('pub_date'))
        self.slug = data.get('slug')
        self.title = data.get('title')
        self.in_reply_to = data.get('in_reply_to', [])
        self.repost_of = data.get('repost_of', [])
        self.like_of = data.get('like_of', [])
        self.draft = data.get('draft', False)
        self.deleted = data.get('deleted', False)

        if 'location' in data:
            self.location = Location.from_json(data.get('location', {}))

        if 'syndication' in data:
            synd = data.get('syndication', {})
            self.twitter_status_id = synd.get('twitter_id')
            self.facebook_post_id = synd.get('facebook_id')

    def to_json_blob(self):
        data = {
            'pub_date':  format_date(self.pub_date),
            'slug': self.slug,
            'title': self.title,
            'in_reply_to': self.in_reply_to,
            'repost_of': self.repost_of,
            'like_of': self.like_of,
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
            raise RuntimeError("Cannot save post that was not opened "
                               "with the 'writeable' flag")

        basedir = os.path.join(app.root_path, '_data/posts')
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
            json.dump(self.to_json_blob(), f, indent=True)
            f.write('\n')
            f.write(self.content)

        save_backup(basedir,
                    os.path.join(app.root_path, '_data/.backup/posts'),
                    self.path)
        shutil.move(temp, filename)

    @property
    def path(self):
        return "{}/{:02d}/{:02d}/{}_{}{}".format(
            self.pub_date.year, self.pub_date.month, self.pub_date.day,
            self.post_type, self.date_index,
            format_to_extension(self.content_format))

    @property
    def path(self):
        return "{}/{:02d}/{:02d}/{}_{}{}".format(
            self.pub_date.year, self.pub_date.month, self.pub_date.day,
            self.post_type, self.date_index,
            format_to_extension(self.content_format))


    @property
    def permalink(self):
        return self._permalink(include_slug=True)

    @property
    def permalink_without_slug(self):
        return self._permalink(include_slug=False)
        

    def _permalink(self, include_slug):
        site_url = app.config.get('SITE_URL') or 'http://localhost'

        path_components = [site_url,
                           self.post_type,
                           self.pub_date.strftime('%Y/%m/%d'),
                           str(self.date_index)]
        if include_slug and self.slug:
            path_components.append(self.slug)

        return '/'.join(path_components)

    @property
    def shortid(self):
        if not self.pub_date or not self.date_index:
            return None
        tag = util.tag_for_post_type(self.post_type)
        ordinal = util.date_to_ordinal(self.pub_date.date())
        return '{}{}{}'.format(tag, util.base60_encode(ordinal),
                               util.base60_encode(self.date_index))

    @property
    def short_permalink(self):
        return '{}/{}'.format(app.config.get('SHORT_SITE_URL'),
                              self.shortid)

    @property
    def short_cite(self):
        tag = util.tag_for_post_type(self.post_type)
        ordinal = util.date_to_ordinal(self.pub_date.date())
        cite = '{} {}{}{}'.format(app.config.get('SHORT_SITE_CITE'),
                                  tag, util.base60_encode(ordinal),
                                  util.base60_encode(self.date_index))
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

    @property
    def mentions_path(self):
        return self.relpath_to_fullpath(
            "{}/{:02d}/{:02d}/{}_{}.mentions.json".format(
                self.pub_date.year, self.pub_date.month, self.pub_date.day,
                self.post_type, self.date_index))

    @property
    def mentions(self):
        if self._mentions is None:
            path = self.mentions_path
            if os.path.exists(path):
                blob = json.load(open(path, 'r'))
                self._mentions = blob
            else:
                self._mentions = []
            app.logger.debug("loaded mentions from %s: %s",
                             path, self._mentions)
        return self._mentions

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.title)
        else:
            return 'post:{}'.format(self.content[:140])
