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
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('mention_id', db.Integer, db.ForeignKey('mention.id'), index=True))

posts_to_reply_contexts = db.Table(
    'posts_to_reply_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'), index=True))

posts_to_repost_contexts = db.Table(
    'posts_to_repost_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'), index=True))

posts_to_like_contexts = db.Table(
    'posts_to_like_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'), index=True))

posts_to_bookmark_contexts = db.Table(
    'posts_to_bookmark_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'), index=True))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(120), unique=True)
    twitter_oauth_token = db.Column(db.String(512))
    twitter_oauth_token_secret = db.Column(db.String(512))
    facebook_access_token = db.Column(db.String(512))

    @classmethod
    def load(cls, domain):
        return cls.query.filter(cls.domain==domain).first()

    def __init__(self, domain):
        self.domain = domain
        self.authenticated = False
        self.twitter_oauth_token = None
        self.twitter_oauth_token_secret = None
        self.facebook_access_token = None

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
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), index=True)

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

    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), index=True)

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
    path = db.Column(db.String(256))
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
    published = db.Column(db.DateTime, index=True)
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
    def load_by_date(cls, post_type, year, month, day, index):
        return cls.load_by_path(
            cls.date_to_path(post_type, year, month, day, index))

    @classmethod
    def load_by_shortid(cls, shortid):
        return cls.load_by_path(cls.shortid_to_path(shortid))

    @classmethod
    def load_by_path(cls, path):
        return cls.query.filter_by(path=path).first()

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
        self.content = None
        self.content_html = None

    def reserve_date_index(self):
        """assign a new date index if we don't have one yet"""
        if not self.date_index:
            idx = 1
            while True:
                self.date_index = util.base60_encode(idx)
                self.path = self.date_to_path(
                    self.post_type, self.published.year, self.published.month,
                    self.published.day, self.date_index)
                if Post.query.filter_by(path=self.path).count() == 0:
                    break
                idx += 1

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

    def __init__(self, **kwargs):
        self.url = kwargs.get('url')
        self.permalink = kwargs.get('permalink')
        self.author_name = kwargs.get('author_name')
        self.author_url = kwargs.get('author_url')
        self.author_image = kwargs.get('author_image')
        self.content = kwargs.get('content')
        self.content_plain = kwargs.get('content_plain')
        self.published = kwargs.get('published')
        self.title = kwargs.get('title')
        self.syndication = kwargs.get('syndication', [])

    @property
    def title_or_url(self):
        return self.title or util.prettify_url(self.permalink)


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

    @property
    def title_or_url(self):
        return self.title or util.prettify_url(self.permalink)


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
