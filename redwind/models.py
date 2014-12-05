from . import app
from . import db
from . import util
from . import maps

from flask import g, session

import os
import os.path
import json
import urllib


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
    key = db.Column(db.String(128), primary_key=True)
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

    def __eq__(self, other):
        if type(other) is type(self):
            return self.domain == other.domain
        return False

    def __repr__(self):
        return '<User:{}>'.format(self.domain)


class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))
    location = db.Column(JsonType)
    slug = db.Column(db.String(256))

    def update_slug(self, geocode):
        self.slug = util.slugify(self.name + ' ' + geocode)

    @property
    def path(self):
        return 'venue/{}'.format(self.slug)

    @property
    def permalink(self):
        site_url = get_settings().site_url or 'http://localhost'
        return '/'.join((site_url, self.path))

    def map_image(self, width, height):
        lat = self.location.get('latitude')
        lng = self.location.get('longitude')
        return maps.get_map_image(width, height, 13,
                                  [maps.Marker(lat, lng, 'dot-small-pink')])


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(256))
    historic_path = db.Column(db.String(256))
    post_type = db.Column(db.String(64))
    draft = db.Column(db.Boolean)
    deleted = db.Column(db.Boolean)
    hidden = db.Column(db.Boolean)
    redirect = db.Column(db.String(256))
    tags = db.relationship('Tag', secondary=posts_to_tags)
    audience = db.Column(JsonType)

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

    location = db.Column(JsonType)
    photos = db.Column(JsonType)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'))
    venue = db.relationship('Venue', uselist=False)

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

    def __init__(self, post_type):
        self.post_type = post_type
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
        self.photos = None
        self.content = None
        self.content_html = None

    def get_image_path(self):
        site_url = get_settings().site_url or 'http://localhost'
        return '/'.join((site_url, self.path, 'files'))

    def map_image(self, width, height):
        location = self.location or (self.venue and self.venue.location)
        if location:
            lat = location.get('latitude')
            lng = location.get('longitude')
            return maps.get_map_image(width, height, 13,
                                      [maps.Marker(lat, lng, 'dot-small-blue')])

    def photo_url(self, photo):
        return '/'.join((self.get_image_path(), photo.get('filename')))

    def photo_thumbnail(self, photo):
        return self.photo_url(photo) + '?size=medium'

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

    def _fill_in_action_handler(self, url):
        return url.replace('{url}', urllib.parse.quote_plus(self.permalink))

    @property
    def reply_url(self):
        handlers = session.get('action-handlers', {})
        handler = handlers.get('reply')
        if handler:
            return self._fill_in_action_handler(handler)

        tweet_id = self.tweet_id
        if tweet_id:
            return TWEET_INTENT_URL.format(tweet_id)

    @property
    def retweet_url(self):
        handlers = session.get('action-handlers', {})
        handler = handlers.get('repost')
        if handler:
            return self._fill_in_action_handler(handler)

        tweet_id = self.tweet_id
        if tweet_id:
            return RETWEET_INTENT_URL.format(tweet_id)

    @property
    def favorite_url(self):
        handlers = session.get('action-handlers', {})
        handler = handlers.get('favorite') or handlers.get('like')
        if handler:
            return self._fill_in_action_handler(handler)

        tweet_id = self.tweet_id
        if tweet_id:
            return FAVORITE_INTENT_URL.format(tweet_id)

    @property
    def location_url(self):
        if (self.location and 'latitude' in self.location
                and 'longitude' in self.location):
            return OPEN_STREET_MAP_URL.format(self.location['latitude'],
                                              self.location['longitude'])

    def generate_slug(self):
        if self.title:
            return util.slugify(self.title)

        if self.content:
            return util.slugify(self.content, 48)

        if self.post_type == 'checkin' and self.venue:
            return util.slugify('checked into ' + self.venue.name + ' '
                                + self.content, 48)

        for ctxs, prefix in ((self.bookmark_contexts, 'bookmark-of-'),
                             (self.like_contexts, 'like-of-'),
                             (self.repost_contexts, 'repost-of-'),
                             (self.reply_contexts, 'reply-to-')):
            if ctxs:
                return util.slugify(prefix + ctxs[0].get_slugify_target(), 48)

        return 'untitled'

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.path)
        else:
            return 'post:{}'.format(self.path)


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

    def __init__(self):
        self.index = None
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
    name = db.Column(db.String(128), unique=True)

    def __init__(self, name):
        self.name = name


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
