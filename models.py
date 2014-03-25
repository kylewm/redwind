from app import app, db

import datetime
import shortlinks
import base60

from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from sqlalchemy import cast


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True)
    domain = db.Column(db.String(120), unique=True)
    email = db.Column(db.String(120), unique=True)
    pw_hash = db.Column(db.String(256))
    display_name = db.Column(db.String(80))
    twitter_username = db.Column(db.String(80))
    facebook_username = db.Column(db.String(80))
    facebook_access_token = db.Column(db.String(512))
    twitter_oauth_token = db.Column(db.String(512))
    twitter_oauth_token_secret = db.Column(db.String(512))

    def set_password(self, plaintext):
        self.pw_hash = generate_password_hash(plaintext)

    def check_password(self, plaintext):
        return check_password_hash(self.pw_hash, plaintext)

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.domain

    def __init__(self, login, email, password):
        self.login = login
        self.email = email
        self.set_password(password)

    def __repr__(self):
        return '<User:{}>'.format(self.login)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'tag:{}'.format(self.name)

tags_to_posts = db.Table(
    'tags_to_posts', db.Model.metadata,
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
    db.Column('position', db.Integer))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_index = db.Column(db.Integer)
    slug = db.Column(db.String(256))
    pub_date = db.Column(db.DateTime)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User',
                             backref=db.backref('posts'))
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    post_type = db.Column(db.String(64))  # note/article/etc.
    content_format = db.Column(db.String(64))  # markdown/html/plain

    in_reply_to = db.Column(db.String(2048))
    repost_source = db.Column(db.String(2048))
    like_of = db.Column(db.String(2048))

    reply_contexts = db.relationship('ReplyContext', backref='post')
    share_contexts = db.relationship('ShareContext', backref='post')
    like_contexts = db.relationship('LikeContext', backref='post')

    repost_preview = db.Column(db.Text)
    draft = db.Column(db.Boolean())

    latitude = db.Column(db.Float())
    longitude = db.Column(db.Float())
    location_name = db.Column(db.String(512))

    twitter_status_id = db.Column(db.String(64))
    facebook_post_id = db.Column(db.String(64))
    tags = db.relationship('Tag', secondary=tags_to_posts,
                           order_by=tags_to_posts.columns.position,
                           backref='posts')
    mentions = db.relationship('Mention', backref='post')

    @classmethod
    def lookup_post_by_id(cls, dbid):
        post = cls.query.filter_by(id=dbid).first()
        return post

    @classmethod
    def lookup_post_by_date(cls, post_type, year, month, day, index):
        date = datetime.date(year, month, day)
        post = cls.query\
                  .filter(Post.post_type == post_type,
                          cast(Post.pub_date, db.Date) == date,
                          Post.date_index == index)\
                  .first()
        return post

    def __init__(self, post_type, content_format, author):
        self.post_type = post_type
        self.content_format = content_format
        self.author = author
        self.draft = True

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


class ExternalPost(db.Model):
    """mention, reply-context, repost-context, like-context
       all contain nearly the same data"""
    id = db.Column(db.Integer, primary_key=True)

    #the referenced URL
    source = db.Column(db.String(2048))
    #permanent link parsed from html
    permalink = db.Column(db.String(2048))

    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    content_format = db.Column(db.String(64))  # markdown/html/plain

    pub_date = db.Column(db.DateTime)

    author_name = db.Column(db.String(256))
    author_url = db.Column(db.String(2048))
    author_image = db.Column(db.String(2048))

    unparsed_html = db.Column(db.Text)

    def __init__(self, source, permalink, title, content,
                 content_format, author_name, author_url,
                 author_image, pub_date=None, unparsed_html=None):
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


class ReplyContext(ExternalPost):
    id = db.Column(db.Integer, db.ForeignKey('external_post.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))


class ShareContext(ExternalPost):
    id = db.Column(db.Integer, db.ForeignKey('external_post.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))


class LikeContext(ExternalPost):
    id = db.Column(db.Integer, db.ForeignKey('external_post.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))


class Mention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(2048))
    permalink = db.Column(db.String(2048))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    content = db.Column(db.Text)
    mention_type = db.Column(db.String(64))
    author_name = db.Column(db.String(256))
    author_url = db.Column(db.String(2048))
    author_image = db.Column(db.String(2048))
    pub_date = db.Column(db.DateTime)

    def __init__(self, source, permalink, post, content, mention_type,
                 author_name, author_url, author_image, pub_date=None):
        self.source = source
        self.permalink = permalink
        self.post = post
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
