from . import app
from . import db
from . import util
from . import archiver

import collections
import mf2util
import os
import os.path
import json
import time
from operator import attrgetter, itemgetter
from contextlib import contextmanager


TWEET_INTENT_URL = 'https://twitter.com/intent/tweet?in_reply_to={}'
RETWEET_INTENT_URL = 'https://twitter.com/intent/retweet?tweet_id={}'
FAVORITE_INTENT_URL = 'https://twitter.com/intent/favorite?tweet_id={}'
OPEN_STREET_MAP_URL = 'http://www.openstreetmap.org/?mlat={0}&mlon={1}#map=17/{0}/{1}'


POST_TYPES = ('article', 'note', 'like', 'share', 'reply',
              'checkin', 'photo', 'bookmark')


def get_fs_path(path):
    """get the filesystem path from a relative path
    e.g., note/2014/04/29/1 -> root/_data/note/2014/04/29/1
    """
    return os.path.join(app.root_path, '_data', path)


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


class JsonType(db.TypeDecorator):
    """Represents an immutable structure as a json-encoded string.
    http://docs.sqlalchemy.org/en/rel_0_9/core/types.html#marshal-json-strings
    """
    impl = db.Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


posts_to_mentions = db.Table(
    'posts_to_mentions', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('mention_id', db.Integer, db.ForeignKey('mention.id')))

posts_to_reply_contexts = db.Table(
    'posts_to_reply_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id')))

posts_to_repost_contexts = db.Table(
    'posts_to_repost_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id')))

posts_to_like_contexts = db.Table(
    'posts_to_like_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id')))

posts_to_bookmark_contexts = db.Table(
    'posts_to_bookmark_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id')))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(120), unique=True)
    twitter_oauth_token = db.Column(db.String(512))
    twitter_oauth_token_secret = db.Column(db.String(512))
    facebook_access_token = db.Column(db.String(512))

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
        self.twitter_oauth_token = None
        self.twitter_oauth_token_secret = None
        self.facebook_access_token = None

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


class Photo(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256))
    caption = db.Column(db.Text)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

    @classmethod
    def from_json(cls, post, data):
        return cls(post, **data)

    def to_json(self):
        return util.filter_empty_keys({
            'filename': self.filename,
            'caption': self.caption,
        })

    def __init__(self, post, **kwargs):
        self.filename = kwargs.get('filename')
        self.caption = kwargs.get('caption')
        self.post = post

    @property
    def url(self):
        return os.path.join(self.post.get_image_path(), self.filename)

    @property
    def thumbnail(self):
        return self.url + '?size=medium'


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    name = db.Column(db.String(256))
    street_address = db.Column(db.String(256))
    extended_address = db.Column(db.String(256))
    locality = db.Column(db.String(128))
    region = db.Column(db.String(128))
    country_name = db.Column(db.String(128))
    postal_code = db.Column(db.String(32))
    country_code = db.Column(db.String(8))

    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))



    @classmethod
    def from_json(cls, data):
        return cls(**data)

    def __init__(self, **kwargs):
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.name = kwargs.get('name')
        self.street_address = kwargs.get('street_address')
        self.extended_address = kwargs.get('extended_address')
        self.locality = kwargs.get('locality')
        self.region = kwargs.get('region')
        self.country_name = kwargs.get('country_name')
        self.postal_code = kwargs.get('postal_code')
        self.country_code = kwargs.get('country_code')

    def to_json(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'name': self.name,
            'street_address': self.street_address,
            'extended_address': self.extended_address,
            'locality': self.locality,
            'region': self.region,
            'country_name': self.country_name,
            'postal_code': self.postal_code,
            'country_code': self.country_code
        }

    @property
    def approximate_latitude(self):
        return self.latitude and '{:.3f}'.format(self.latitude)

    @property
    def approximate_longitude(self):
        return self.longitude and '{:.3f}'.format(self.longitude)

    @property
    def geo_name(self):
        if self.name:
            return self.name
        elif self.locality and self.region:
            return "{}, {}".format(self.locality, self.region)
        elif self.latitude and self.longitude:
            return "{:.2f}, {:.2f}".format(self.latitude, self.longitude)
        else:
            return "Unknown Location"


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    _path = db.Column('path', db.String(256))
    post_type = db.Column(db.String(64))
    date_index = db.Column(db.String(4))
    draft = db.Column(db.Boolean)
    deleted = db.Column(db.Boolean)
    hidden = db.Column(db.Boolean)
    redirect = db.Column(db.String(256))

    in_reply_to = db.Column(JsonType)
    repost_of = db.Column(JsonType)
    like_of = db.Column(JsonType)
    bookmark_of = db.Column(JsonType)

    reply_contexts = db.relationship(
        'Context', secondary=posts_to_reply_contexts)
    like_contexts = db.relationship(
        'Context', secondary=posts_to_like_contexts)
    repost_contexts = db.relationship(
        'Context', secondary=posts_to_repost_contexts)
    bookmark_contexts = db.relationship(
        'Context', secondary=posts_to_bookmark_contexts)

    title = db.Column(db.String(256))
    published = db.Column(db.DateTime)
    slug = db.Column(db.String(256))

    syndication = db.Column(JsonType)

    location = db.relationship('Location', uselist=False, backref='post')
    photos = db.relationship('Photo', backref='post')

    # TODO create Tag table
    tags = db.Column(JsonType)
    audience = db.Column(JsonType)

    mentions = db.relationship(
        'Mention', secondary=posts_to_mentions, backref='posts')

    content = db.Column(db.Text)
    content_html = db.Column(db.Text)

    @classmethod
    @contextmanager
    def writeable(cls, path):
        with acquire_lock(get_fs_path(path), 30):
            post = cls.load(path)
            post._writeable = True
            yield post
            post._writeable = False

    @classmethod
    def load(cls, path):
        # app.logger.debug("loading from path %s", path)
        post_type = path.split('/', 1)[0]
        date_index = os.path.basename(path)

        rootdir = get_fs_path(path)
        data_path = os.path.join(rootdir, 'data.json')

        if not os.path.exists(data_path):
            app.logger.warn("No post found at %s", path)
            return None

        post = cls(post_type, date_index)
        with open(data_path) as fp:
            post.read_json_blob(json.load(fp))

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
        published = util.parse_date(shortid)
        index = util.parse_index(shortid)
        return '{}/{}/{:02d}/{:02d}/{}'.format(
            post_type, published.year, published.month, published.day, index)

    def __init__(self, post_type, date_index=None):
        self.post_type = post_type
        self.date_index = date_index
        self.draft = False
        self.deleted = False
        self.hidden = False
        self.redirect = None
        self.previous_permalinks = []
        self.in_reply_to = []
        self.repost_of = []
        self.like_of = []
        self.bookmark_of = []
        self.title = None
        self.published = None
        self.slug = None
        self.location = None
        self.syndication = []
        self.tags = []
        self.audience = []  # public
        self.mention_urls = []
        self.photos = []
        self._contexts = None
        self._mentions = None
        self._content = None
        self._content_html = None
        self._writeable = False

    def read_json_blob(self, data):
        self.published = util.isoparse(data.get('published')
                                       or data.get('pub_date'))
        self.slug = data.get('slug')
        self.title = data.get('title')
        self.in_reply_to = data.get('in_reply_to', [])
        self.repost_of = data.get('repost_of', [])
        self.like_of = data.get('like_of', [])
        self.bookmark_of = data.get('bookmark_of', [])
        self.tags = data.get('tags', [])
        self.syndication = data.get('syndication', [])
        self.draft = data.get('draft', False)
        self.deleted = data.get('deleted', False)
        self.hidden = data.get('hidden', False)
        self.audience = data.get('audience', [])
        self.mention_urls = data.get('mentions', [])
        self.redirect = data.get('redirect')
        self.previous_permalinks = data.get('previous_permalinks', [])
        if 'location' in data:
            self.location = Location.from_json(data.get('location', {}))
        if 'photos' in data:
            self.photos = [Photo.from_json(self, p)
                           for p in data.get('photos', [])]

    def to_json_blob(self):
        return util.filter_empty_keys({
            'published':  util.isoformat(self.published),
            'slug': self.slug,
            'title': self.title,
            'in_reply_to': self.in_reply_to,
            'repost_of': self.repost_of,
            'like_of': self.like_of,
            'bookmark_of': self.bookmark_of,
            'location': self.location and self.location.to_json(),
            'syndication': self.syndication,
            'tags': self.tags,
            'draft': self.draft,
            'deleted': self.deleted,
            'hidden': self.hidden,
            'audience': self.audience,
            'mentions': self.mention_urls,
            'photos': [p.to_json() for p in self.photos],
            'redirect': self.redirect,
            'previous_permalinks': self.previous_permalinks,
        })

    def reserve_date_index(self):
        """assign a new date index if we don't have one yet"""
        if not self.date_index:
            idx = 1
            while True:
                self.date_index = util.base60_encode(idx)
                if not os.path.exists(get_fs_path(self.path)):
                    break
                idx += 1

    def save(self):
        if not self._writeable:
            raise RuntimeError("Cannot save post that was not opened "
                               "with the 'writeable' flag")

        self.reserve_date_index()
        parentdir = get_fs_path(self.path)
        json_filename = os.path.join(parentdir, 'data.json')
        content_filename = os.path.join(parentdir, 'content.md')

        if not os.path.exists(parentdir):
            os.makedirs(parentdir)

        with open(json_filename, 'w') as f:
            json.dump(self.to_json_blob(), f, indent=True)

        # subtle: have to pre-load the content before opening the
        # file, or else content willb e erased!
        content = self.content
        with open(content_filename, 'w') as f:
            f.write(content)

    @property
    def path(self):
        return "{}/{}/{:02d}/{:02d}/{}".format(
            self.post_type, self.published.year, self.published.month,
            self.published.day, self.date_index)

    def get_image_path(self):
        return '/' + self.path + '/files'

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
                           self.published.strftime('%Y/%m/%d'),
                           str(self.date_index)]
        if include_slug and self.slug:
            path_components.append(self.slug)

        return '/'.join(path_components)

    @property
    def shortid(self):
        if not self.published or not self.date_index:
            return None
        tag = util.tag_for_post_type(self.post_type)
        ordinal = util.date_to_ordinal(self.published.date())
        return '{}{}{}'.format(tag, util.base60_encode(ordinal),
                               self.date_index)

    @property
    def short_permalink(self):
        return '{}/{}'.format(app.config.get('SHORT_SITE_URL'),
                              self.shortid)

    @property
    def short_cite(self):
        tag = util.tag_for_post_type(self.post_type)
        ordinal = util.date_to_ordinal(self.published.date())
        cite = '{} {}{}{}'.format(app.config.get('SHORT_SITE_CITE'),
                                  tag, util.base60_encode(ordinal),
                                  self.date_index)
        return cite

    def get_content(self):
        if self._content is None:
            self._content = ''
            content_path = os.path.join(get_fs_path(self.path), 'content.md')
            if os.path.exists(content_path):
                with open(content_path, 'r') as fp:
                    self._content = fp.read()
        return self._content

    def get_content_html(self):
        if self._content_html is None:
            self._content_html = ''
            md_path = os.path.join(get_fs_path(self.path), 'content.md')
            if os.path.exists(md_path):
                html_path = os.path.join(get_fs_path(self.path), 'content.html')
                if util.is_cached_current(md_path, html_path):
                    with open(html_path, 'r') as f:
                        self._content_html = f.read()
                else:
                    self._content_html = util.markdown_filter(
                        self.content, img_path=self.get_image_path())
                    with open(html_path, 'w') as f:
                        f.write(self._content_html)
        return self._content_html

    def get_mentions(self):
        if self._mentions is None:
            self._mentions = Mention.load_all(self.path)
            self._mentions.sort(key=attrgetter('published'))
        return self._mentions

    def get_contexts(self):
        if self._contexts is None:
            cs = Context.load_all(self.path)
            self._contexts = {c.url: c for c in cs}
        return self._contexts

    def _url_to_context(self, url):
        context = self.get_contexts().get(url)
        if context:
            return context
        else:
            context = Context(self.path)
            context.url = context.permalink = url
            return context

    def get_reply_contexts(self):
        return [self._url_to_context(url) for url in self.in_reply_to]

    def get_repost_contexts(self):
        return [self._url_to_context(url) for url in self.repost_of]

    def get_like_contexts(self):
        return [self._url_to_context(url) for url in self.like_of]

    def get_bookmark_contexts(self):
        return [self._url_to_context(url) for url in self.bookmark_of]

    @property
    def likes(self):
        return [m for m in self.mentions if m.reftype == 'like']

    @property
    def reposts(self):
        return [m for m in self.mentions if m.reftype == 'repost']

    @property
    def replies(self):
        return [m for m in self.mentions if m.reftype == 'reply']

    @property
    def references(self):
        return [m for m in self.mentions if m.reftype == 'reference']

    @property
    def tweet_id(self):
        for url in self.syndication:
            match = util.TWITTER_RE.match(url)
            if match:
                return match.group(2)

    @property
    def reply_url(self):
        tweet_id = self.tweet_id
        if tweet_id:
            return TWEET_INTENT_URL.format(tweet_id)

    @property
    def retweet_url(self):
        tweet_id = self.tweet_id
        if tweet_id:
            return RETWEET_INTENT_URL.format(tweet_id)

    @property
    def favorite_url(self):
        tweet_id = self.tweet_id
        if tweet_id:
            return FAVORITE_INTENT_URL.format(tweet_id)

    @property
    def location_url(self):
        if self.location:
            return OPEN_STREET_MAP_URL.format(self.location.latitude,
                                              self.location.longitude)

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.title)
        else:
            return 'post:{}'.format(
                self.content[:140] if self.content else 'BLANK')


class Context(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512))
    permalink = db.Column(db.String(512))
    author_name = db.Column(db.String(128))
    author_url = db.Column(db.String(512))
    author_image = db.Column(db.String(512))
    content = db.Column(db.Text)
    content_plain = db.Column(db.Text)
    published = db.Column(db.DateTime)
    title = db.Column(db.String(512))
    syndication = db.Column(JsonType)

    def __init__(self, post_path):
        self.index = None
        self.post_path = post_path
        self.url = None
        self.permalink = None
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.content_plain = None
        self.published = None
        self.title = None
        self.syndication = []

    def to_json_blob(self):
        return util.filter_empty_keys({
            'url': self.url,
            'permalink': self.permalink,
            'author_name': self.author_name,
            'author_url': self.author_url,
            'author_image': self.author_image,
            'content': self.content,
            'content_plain': self.content_plain,
            'published': util.isoformat(self.published),
            'title': self.title,
            'syndication': self.syndication,
        })

    def read_json_blob(self, blob):
        self.url = blob.get('url')
        self.permalink = blob.get('permalink')
        self.author_name = blob.get('author_name')
        self.author_url = blob.get('author_url')
        self.author_image = blob.get('author_image')
        self.content = blob.get('content')
        self.content_plain = blob.get('content_plain')
        self.published = util.isoparse(blob.get('published'))
        self.title = blob.get('title')
        self.syndication = blob.get('syndication', {})

    @property
    def path(self):
        return '{}/{}/{}.json'.format(
            self.post_path,
            self.get_folder_name(),
            self.index)

    @property
    def title_or_url(self):
        return self.title or util.prettify_url(self.permalink)

    def reserve_index(self):
        if not self.index:
            idx = 1
            while True:
                self.index = util.base60_encode(idx)
                if not os.path.exists(get_fs_path(self.path)):
                    break
                idx += 1

    def save(self):
        self.reserve_index()
        fullpath = get_fs_path(self.path)
        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))
        app.logger.debug('saving foreign post %s', fullpath)
        with open(fullpath, 'w') as fp:
            json.dump(self.to_json_blob(), fp, indent=True)

    def delete(self):
        fullpath = get_fs_path(self.path)
        app.logger.debug('deleting foreign post %s', fullpath)
        if os.path.exists(fullpath):
            os.remove(fullpath)
            if os.path.exists(fullpath):
                app.logger.debug('path still exists after deleting %s', fullpath)

    @classmethod
    def load_all(cls, post_path):
        result = []
        path = os.path.join(get_fs_path(post_path), cls.get_folder_name())
        if os.path.exists(path):
            for fn in os.listdir(path):
                foreign = cls(post_path)
                index, _ = os.path.splitext(fn)
                foreign.index = index

                with open(os.path.join(path, fn)) as fp:
                    foreign.read_json_blob(json.load(fp))
                result.append(foreign)
        return result

    @classmethod
    def get_folder_name(cls):
        return 'contexts'


class Mention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512))
    permalink = db.Column(db.String(512))
    author_name = db.Column(db.String(128))
    author_url = db.Column(db.String(512))
    author_image = db.Column(db.String(512))
    content = db.Column(db.Text)
    content_plain = db.Column(db.Text)
    published = db.Column(db.DateTime)
    title = db.Column(db.String(512))
    syndication = db.Column(JsonType)
    reftype = db.Column(db.String(32))

    def __init__(self, post_path):
        self.index = None
        self.post_path = post_path
        self.url = None
        self.permalink = None
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.content_plain = None
        self.published = None
        self.title = None
        self.reftype = None
        self.syndication = []
        self._children = []

    def to_json_blob(self):
        return util.filter_empty_keys({
            'url': self.url,
            'permalink': self.permalink,
            'author_name': self.author_name,
            'author_url': self.author_url,
            'author_image': self.author_image,
            'content': self.content,
            'content_plain': self.content_plain,
            'published': util.isoformat(self.published),
            'title': self.title,
            'syndication': self.syndication,
            'reftype': self.reftype,
        })

    def read_json_blob(self, blob):
        self.url = blob.get('url')
        self.permalink = blob.get('permalink')
        self.author_name = blob.get('author_name')
        self.author_url = blob.get('author_url')
        self.author_image = blob.get('author_image')
        self.content = blob.get('content')
        self.content_plain = blob.get('content_plain')
        self.published = util.isoparse(blob.get('published'))
        self.title = blob.get('title')
        self.syndication = blob.get('syndication', {})
        self.reftype = blob.get('reftype')

    @property
    def path(self):
        return '{}/{}/{}.json'.format(
            self.post_path,
            self.get_folder_name(),
            self.index)

    @property
    def title_or_url(self):
        return self.title or util.prettify_url(self.permalink)

    def reserve_index(self):
        if not self.index:
            idx = 1
            while True:
                self.index = util.base60_encode(idx)
                if not os.path.exists(get_fs_path(self.path)):
                    break
                idx += 1

    def save(self):
        self.reserve_index()
        fullpath = get_fs_path(self.path)
        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))
        app.logger.debug('saving foreign post %s', fullpath)
        with open(fullpath, 'w') as fp:
            json.dump(self.to_json_blob(), fp, indent=True)

    def delete(self):
        fullpath = get_fs_path(self.path)
        app.logger.debug('deleting foreign post %s', fullpath)
        if os.path.exists(fullpath):
            os.remove(fullpath)
            if os.path.exists(fullpath):
                app.logger.debug('path still exists after deleting %s', fullpath)

    @classmethod
    def load_all(cls, post_path):
        result = []
        path = os.path.join(get_fs_path(post_path), cls.get_folder_name())
        if os.path.exists(path):
            for fn in os.listdir(path):
                foreign = cls(post_path)
                index, _ = os.path.splitext(fn)
                foreign.index = index

                with open(os.path.join(path, fn)) as fp:
                    foreign.read_json_blob(json.load(fp))
                result.append(foreign)
        return result

    @classmethod
    def get_folder_name(cls):
        return 'mentions'


class AddressBook:
    """Address book contains entries like
    {
      'Kyle Mahan': {
        'url': 'http://kylewm.com',
        'photo': 'http://kylewm.com/static/images/kyle_large.jpg',
        'twitter': 'kyle_wm',
        'facebook': '0123456789'
      }
    }
    """

    PATH = os.path.join(app.root_path, '_data', 'addressbook.json')

    def __init__(self):
        if os.path.exists(self.PATH):
            self.entries = json.load(open(self.PATH, 'r'))
        else:
            self.entries = {}

    def save(self):
        json.dump(self.entries, open(self.PATH, 'w'), indent=True)


class Metadata:
    PATH = os.path.join(app.root_path, '_data', 'metadata.json')

    LoadPostsResult = collections.namedtuple('LoadPostResults', [
        'posts', 'is_first_page', 'is_last_page'])

    @staticmethod
    def post_to_blob(post):
        return {
            'type': post.post_type,
            'published': util.isoformat(post.published),
            'draft': post.draft,
            'deleted': post.deleted,
            'redirect': post.redirect,
            'hidden': post.hidden,
            'path': post.path,
            'tags': post.tags,
        }

    @staticmethod
    def regenerate():
        posts = []
        # mentions = []

        basedir = os.path.join(app.root_path, '_data')
        for post_type in POST_TYPES:
            for root, dirs, files in os.walk(os.path.join(basedir, post_type)):
                for filen in files:
                    if filen != 'data.json':
                        continue
                    postpath = os.path.relpath(root, basedir)
                    print('loading', postpath)
                    post = Post.load(postpath)
                    if not post:
                        continue

                    posts.append(util.filter_empty_keys(
                        Metadata.post_to_blob(post)))

                    # for mention in post.mentions:
                    #     mention_published = post.published
                    #     parsed = archiver.load_json_from_archive(mention)
                    #     if parsed:
                    #         entry = mf2util.interpret_comment(
                    #             parsed, mention, [post.permalink])
                    #         if entry and 'published' in entry:
                    #             mention_published = entry.get('published')

                    #     mentions.append((post.path, mention,
                    #                      util.isoformat(mention_published)
                    #                      or '1970-01-01'))

        # keep the 30 most recent mentions
        # mentions.sort(key=itemgetter(2), reverse=True)
        # recent_mentions = [{
        #     'mention': mention,
        #     'post': post_path,
        # } for post_path, mention, published in mentions[:30]]

        util.filter_empty_keys(posts)
        blob = {
            'posts': posts,
            #'mentions': recent_mentions,
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
            basedir = os.path.join(app.root_path, '_data')
            if not os.path.exists(basedir):
                os.mkdir(basedir)
            self.blob = self.regenerate()

    def save(self):
        if not self._writeable:
            raise RuntimeError("Cannot save metadata that was"
                               "not opened with 'writeable' flag")
        with open(self.PATH, 'w') as fp:
            json.dump(self.blob, fp, indent=True)

    def get_post_blobs(self):
        return self.blob['posts']

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
                 and not post.get('redirect')
                 and (not tag or tag in post.get('tags', []))
                 and (not post.get('hidden') or include_hidden)
                 and (not post.get('draft') or include_drafts)
                 and post.get('type') in post_types]

        app.logger.debug('found %d posts', len(posts))

        posts.sort(reverse=reverse,
                   key=lambda post: post.get('published', '1970-01-01'))

        start = per_page * (page-1)
        end = start + per_page
        is_first_page = start <= 0
        is_last_page = end >= len(posts)

        app.logger.debug('return posts %d through %d', start, end)

        return Metadata.LoadPostsResult(
            posts=[Post.load(post['path']) for post in posts[start:end]],
            is_first_page=is_first_page,
            is_last_page=is_last_page)

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

        posts.sort(key=attrgetter('published'))
        return posts
