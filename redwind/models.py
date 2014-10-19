from . import app
from . import db
from . import util

from flask import g

import os
import os.path
import json


TWEET_INTENT_URL = 'https://twitter.com/intent/tweet?in_reply_to={}'
RETWEET_INTENT_URL = 'https://twitter.com/intent/retweet?tweet_id={}'
FAVORITE_INTENT_URL = 'https://twitter.com/intent/favorite?tweet_id={}'
OPEN_STREET_MAP_URL = 'http://www.openstreetmap.org/?mlat={0}&mlon={1}#map=17/{0}/{1}'


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


class Setting(db.Model):
    key = db.Column(db.String(256), primary_key=True)
    name = db.Column(db.String(256))
    value = db.Column(db.Text)


class Settings:
    def __init__(self):
        for s in Setting.query.all():
            setattr(self, s.key, s.value)


def get_settings():
    settings = g.get('rw_settings', None)
    if settings is None:
        g.rw_settings = settings = Settings()
    return settings


posts_to_mentions = db.Table(
    'posts_to_mentions', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('mention_id', db.Integer, db.ForeignKey('mention.id'),
              index=True))

posts_to_reply_contexts = db.Table(
    'posts_to_reply_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'),
              index=True))

posts_to_repost_contexts = db.Table(
    'posts_to_repost_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'),
              index=True))

posts_to_like_contexts = db.Table(
    'posts_to_like_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'),
              index=True))

posts_to_bookmark_contexts = db.Table(
    'posts_to_bookmark_contexts', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('context_id', db.Integer, db.ForeignKey('context.id'),
              index=True))

posts_to_tags = db.Table(
    'posts_to_tags', db.Model.metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), index=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), index=True))


class User:
    def __init__(self, domain):
        self.domain = domain

    # Flask-Login integration

    def is_authenticated(self):
        # user matching user.json is authenticated, all others are guests
        return self.domain == get_settings().author_domain

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
    historic_path = db.Column(db.String(256))
    post_type = db.Column(db.String(64))
    #date_index = db.Column(db.String(4))
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
    #tags = db.Column(JsonType)
    tags = db.relationship('Tag', secondary=posts_to_tags)

    audience = db.Column(JsonType)
    mentions = db.relationship('Mention', secondary=posts_to_mentions,
                               order_by='Mention.published')

    content = db.Column(db.Text)
    content_html = db.Column(db.Text)

    @classmethod
    def load_by_id(cls, dbid):
        return cls.query.get(dbid)

    @classmethod
    def load_by_path(cls, path):
        return cls.query.filter_by(path=path).first()

    @classmethod
    def load_by_historic_path(cls, path):
        return cls.query.filter_by(historic_path=path).first()

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

    def get_image_path(self):
        return '/' + self.path + '/files'

    @property
    def permalink(self):
        site_url = get_settings().site_url or 'http://localhost'
        return '/'.join((site_url, self.path))

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

    def generate_slug(self):
        if self.title:
            return util.slugify(self.title)

        if self.content:
            return util.slugify(self.content, 48)
        for ctxs, prefix in ((self.bookmark_contexts, 'bookmark-of-'),
                             (self.like_contexts, 'like-of-'),
                             (self.repost_contexts, 'repost-of-'),
                             (self.reply_contexts, 'reply-to-')):
            if ctxs:
                return util.slugify(prefix + ctxs[0].get_slugify_target(), 48)

        return 'untitled'

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

    def get_slugify_target(self):
        components = []
        if self.author_name:
            components.append(self.author_name)

        if self.title:
            components.append(self.title)
        elif self.content_plain:
            components.append(self.content_plain)
        else:
            components.append(util.prettify_url(self.permalink or self.url))

        return ' '.join(components)


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
    posts = db.relationship('Post', secondary=posts_to_mentions)

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


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))
    posts = db.relationship('Post', secondary=posts_to_tags)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class Nick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), index=True)
    name = db.Column(db.String(256), unique=True)

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))
    nicks = db.relationship('Nick', backref='contact',
                            cascade='all,delete-orphan')
    image = db.Column(db.String(512))
    url = db.Column(db.String(512))
    social = db.Column(JsonType)

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.url = kwargs.get('url')
        self.image = kwargs.get('image')


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
