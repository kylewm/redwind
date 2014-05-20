from . import app
from . import util
from . import archiver

import mf2util
import os
import os.path
import json
import time
from operator import attrgetter, itemgetter
from contextlib import contextmanager


POST_TYPES = ('article', 'note', 'like', 'share', 'reply', 'checkin')


@contextmanager
def acquire_lock(path, retries):
    lockfile = path+'.lock'
    if not os.path.exists(os.path.dirname(lockfile)):
        os.makedirs(os.path.dirname(lockfile))
    while os.path.exists(lockfile) and retries > 0:
        app.logger.warn("Waiting for lock to become available %s", lockfile)
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
        # app.logger.debug("loading from path %s", os.path.abspath(path))
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

    def __init__(self, domain):
        self.domain = domain
        self.authenticated = False

    def to_json(self):
        data = {
            'domain': self.domain,
            'twitter_oauth_token': self.twitter_oauth_token,
            'twitter_oauth_token_secret': self.twitter_oauth_token_secret,
            'facebook_access_token': self.facebook_access_token
        }
        return util.filter_empty_keys(data)

    def save(self):
        filename = os.path.join(app.root_path, '_data/user.json')
        with open(filename, 'w') as f:
            json.dump(self.to_json(), f, indent=True)

    # Flask-Login integration

    def is_authenticated(self):
        # user matching user.json is authenticated, all others are guests
        return self.authenticated

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.domain

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
    @staticmethod
    def parse_json_frontmatter(fp):
        """parse a multipart file that starts with a json blob"""
        json_lines = []
        for line in fp:
            json_lines.append(line)
            if line.rstrip() == '}':
                break

        head = json.loads(''.join(json_lines))
        body = '\n'.join(line.strip('\r\n') for line in fp.readlines())
        return head, body

    @staticmethod
    def _get_fs_path(path):
        """get the filesystem path from a relative path
        e.g., note/2014/04/29/1 -> root/_data/note/2014/04/29/1
        """
        return os.path.join(app.root_path, '_data', path)

    @classmethod
    @contextmanager
    def writeable(cls, path):
        with acquire_lock(cls._get_fs_path(path), 30):
            post = cls.load(path)
            post._writeable = True
            yield post
            post._writeable = False

    @classmethod
    def load(cls, path):
        # app.logger.debug("loading from path %s", path)
        post_type = path.split('/', 1)[0]
        date_index, _ = os.path.splitext(os.path.basename(path))
        path = cls._get_fs_path(path)
        if not path.endswith('.md'):
            path += '.md'

        if not os.path.exists(path):
            app.logger.warn("No post found at %s", path)
            return None

        with open(path, 'r') as fp:
            head, body = Post.parse_json_frontmatter(fp)

        post = cls(post_type, date_index)
        post.read_json_blob(head)
        post.content = body
        return post

    @classmethod
    def load_by_date(cls, post_type, year, month, day, index):
        return cls.load(
            cls.date_to_path(post_type, year, month, day, index))

    @classmethod
    def load_by_shortid(cls, shortid):
        return cls.load(cls.shortid_to_path(shortid))

    @classmethod
    def date_to_path(cls, post_type, year, month, day, index):
        return "{}/{}/{:02d}/{:02d}/{}".format(
            post_type, year, month, day, index)

    @classmethod
    def shortid_to_path(cls, shortid):
        post_type = util.parse_type(shortid)
        pub_date = util.parse_date(shortid)
        index = util.parse_index(shortid)
        return '{}/{}/{:02d}/{:02d}/{}'.format(
            post_type, pub_date.year, pub_date.month, pub_date.day, index)

    def __init__(self, post_type, date_index=None):
        self.post_type = post_type
        self.date_index = date_index
        self.draft = False
        self.deleted = False
        self.hidden = False
        self.in_reply_to = []
        self.repost_of = []
        self.like_of = []
        self.title = None
        self.content = None
        self.pub_date = None
        self.slug = None
        self.location = None
        self.syndication = []
        self.tags = []
        self.audience = []  # public
        self._mentions = None  # lazy load mentions
        self._writeable = False

    def read_json_blob(self, data):
        self.pub_date = util.isoparse(data.get('pub_date'))
        self.slug = data.get('slug')
        self.title = data.get('title')
        self.in_reply_to = data.get('in_reply_to', [])
        self.repost_of = data.get('repost_of', [])
        self.like_of = data.get('like_of', [])
        self.tags = data.get('tags', [])
        self.syndication = data.get('syndication', [])

        self.draft = data.get('draft', False)
        self.deleted = data.get('deleted', False)
        self.hidden = data.get('hidden', False)
        self.audience = data.get('audience', [])

        if 'location' in data:
            self.location = Location.from_json(data.get('location', {}))

    def to_json_blob(self):
        data = {
            'pub_date':  util.isoformat(self.pub_date),
            'slug': self.slug,
            'title': self.title,
            'in_reply_to': self.in_reply_to,
            'repost_of': self.repost_of,
            'like_of': self.like_of,
            'location': self.location and self.location.to_json(),
            'syndication': self.syndication,
            'tags': self.tags,
            'draft': self.draft,
            'deleted': self.deleted,
            'hidden': self.hidden,
            'audience': self.audience,
        }
        return util.filter_empty_keys(data)

    def reserve_date_index(self):
        """assign a new date index if we don't have one yet"""
        if not self.date_index:
            idx = 1
            while True:
                self.date_index = util.base60_encode(idx)
                if not os.path.exists(self._get_fs_path(self.path) + '.md'):
                    break
                idx += 1

    def save(self):
        if not self._writeable:
            raise RuntimeError("Cannot save post that was not opened "
                               "with the 'writeable' flag")

        self.reserve_date_index()
        filename = self._get_fs_path(self.path) + '.md'
        parentdir = os.path.dirname(filename)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir)

        with open(filename, 'w') as f:
            json.dump(self.to_json_blob(), f, indent=True)
            f.write('\n')
            if self.content:
                f.write(self.content)

    @property
    def path(self):
        return "{}/{}/{:02d}/{:02d}/{}".format(
            self.post_type, self.pub_date.year, self.pub_date.month,
            self.pub_date.day, self.date_index)

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
                               self.date_index)

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
                                  self.date_index)
        return cite

    @property
    def mentions_path(self):
        return "{}/{}/{:02d}/{:02d}/{}.mentions.json".format(
            self.post_type, self.pub_date.year, self.pub_date.month,
            self.pub_date.day, self.date_index)

    @property
    def mentions(self):
        if self._mentions is None:
            path = self._get_fs_path(self.mentions_path)
            if os.path.exists(path):
                blob = json.load(open(path, 'r'))
                self._mentions = blob
                # app.logger.debug("loaded mentions from %s: %s",
                #                 path, self._mentions)
            else:
                self._mentions = []
                # app.logger.debug("no mentions file found at %s", path)

        return self._mentions

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.title)
        else:
            return 'post:{}'.format(
                self.content[:140] if self.content else 'BLANK')


class Metadata:
    PATH = os.path.join(app.root_path, '_data', 'metadata.json')

    @staticmethod
    def post_to_blob(post):
        return {
            'type': post.post_type,
            'published': util.isoformat(post.pub_date),
            'draft': post.draft,
            'deleted': post.deleted,
            'hidden': post.hidden,
            'path': post.path,
            'tags': post.tags,
        }

    @staticmethod
    def regenerate():
        posts = []
        mentions = []

        basedir = os.path.join(app.root_path, '_data')
        for post_type in POST_TYPES:
            for root, dirs, files in os.walk(os.path.join(basedir, post_type)):
                for filen in files:
                    if filen.endswith('.mentions.json'):
                        continue
                    index, ext = os.path.splitext(filen)
                    postpath = os.path.join(
                        os.path.relpath(root, basedir), index)
                    post = Post.load(postpath)
                    if not post:
                        continue

                    posts.append(util.filter_empty_keys(
                        Metadata.post_to_blob(post)))

                    for mention in post.mentions:
                        mention_pub_date = post.pub_date
                        parsed = archiver.load_json_from_archive(mention)
                        if parsed:
                            entry = mf2util.interpret_comment(
                                parsed, mention, [post.permalink])
                            if entry and 'published' in entry:
                                mention_pub_date = entry.get('published')

                        mentions.append((post.path, mention,
                                         util.isoformat(mention_pub_date)
                                         or '1970-01-01'))

        # keep the 30 most recent mentions
        mentions.sort(key=itemgetter(2), reverse=True)
        recent_mentions = [{
            'mention': mention,
            'post': post_path,
        } for post_path, mention, pub_date in mentions[:30]]

        util.filter_empty_keys(posts)
        blob = {
            'posts': posts,
            'mentions': recent_mentions,
        }

        json.dump(blob,
                  open(os.path.join(basedir, 'metadata.json'), 'w'),
                  indent=True)
        return blob

    @classmethod
    @contextmanager
    def writeable(cls):
        with acquire_lock(cls.PATH, 30):
            mdata = cls()
            mdata._writeable = True
            yield mdata
            mdata._writeable = False

    def __init__(self):
        self._writeable = False
        if os.path.exists(self.PATH):
            self.blob = json.load(open(self.PATH, 'r'))
        else:
            self.blob = self.regenerate()

    def save(self):
        if not self._writeable:
            raise RuntimeError("Cannot save metadata that was"
                               "not opened with 'writeable' flag")
        json.dump(self.blob, open(self.PATH, 'w'), indent=True)

    def get_recent_mentions(self):
        return self.blob['mentions']

    def insert_recent_mention(self, post, url):
        mentions = self.get_recent_mentions()
        mentions.insert(0, {
            'mention': url,
            'post': post and post.path,
        })
        self.blob['mentions'] = mentions[:30]
        self.save()

    def iterate_all_posts(self):
        for post in self.blob['posts']:
            yield Post.load(post['path'])

    def load_posts(self, reverse=False, post_types=None, tag=None,
                   include_hidden=False, include_drafts=False,
                   per_page=30, page=1):
        if not post_types:
            post_types = POST_TYPES

        app.logger.debug('loading post metadata %s, page=%d, per page=%d',
                         post_types, page, per_page)

        posts = [post for post in self.blob['posts']
                 if not post.get('deleted')
                 and (not tag or tag in post.get('tags', []))
                 and (not post.get('hidden') or include_hidden)
                 and (not post.get('draft') or include_drafts)
                 and post.get('type') in post_types]

        app.logger.debug('found %d posts', len(posts))

        posts.sort(reverse=reverse,
                   key=lambda post: post.get('published', '1970-01-01'))

        start = per_page * (page-1)
        end = start + per_page

        app.logger.debug('return posts %d through %d', start, end)

        return [Post.load(post['path']) for post in posts[start:end]]

    def add_or_update_post(self, post):
        post_path = post.path
        posts = [other for other in self.blob['posts']
                 if other.get('path') != post_path]
        posts.append(util.filter_empty_keys(
            Metadata.post_to_blob(post)))
        self.blob['posts'] = posts

    def get_archive_months(self):
        """Find months that have post content, for the archive page

        Returns: a dict of year -> set of months
        """
        result = {}
        for post in self.blob['posts']:
            published = util.isoparse(post.get('published'))
            if not post.get('deleted') and published:
                result.setdefault(published.year, set()).add(published.month)
        return result

    def load_by_month(self, year, month):
        posts = []
        for post in self.blob['posts']:
            published = util.isoparse(post.get('published'))
            if not post.get('deleted') and published \
               and published.year == year and published.month == month:
                loaded = Post.load(post['path'])
                if not loaded:
                    app.logger.error("Could not load post for path %s", post['path'])
                else:
                    posts.append(loaded)

        posts.sort(key=attrgetter('pub_date'))
        return posts
