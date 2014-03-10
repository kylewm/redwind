from app import app, db

import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict


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
    # date_str and date_index together make up a unique
    # (algorithmic) identifier
    date_str = db.Column(db.String(8))
    date_index = db.Column(db.Integer)
    slug = db.Column(db.String(256))
    pub_date = db.Column(db.DateTime)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User',
                             backref=db.backref('posts', lazy='dynamic'))
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    post_type = db.Column(db.String(64))  # note/article/etc.
    content_format = db.Column(db.String(64))  # markdown/html/plain
    in_reply_to = db.Column(db.String(256))
    repost_source = db.Column(db.String(256))
    repost_preview = db.Column(db.Text)
    twitter_status_id = db.Column(db.String(64))
    facebook_post_id = db.Column(db.String(64))
    tags = db.relationship('Tag', secondary=tags_to_posts,
                           order_by=tags_to_posts.columns.position,
                           backref='posts')
    mentions = db.relationship('Mention', backref='post')

    def __init__(self, title, slug, content, post_type, content_format,
                 author, pub_date):
        self.title = title
        self.slug = slug
        self.content = content
        self.post_type = post_type
        self.content_format = content_format
        self.author = author
        self.pub_date = pub_date

    @property
    def mentions_categorized(self):
        cat = defaultdict(list)
        for mention in self.mentions:
            cat[mention.mention_type].append(mention)
        return cat

    @property
    def permalink_url(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'
        path_components = [site_url, self.post_type,
                           self.date_str, str(self.date_index)]
        if self.slug:
            path_components.append(self.slug)

        return '/'.join(path_components)

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


class ShortLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

    def __init__(self, post):
        self.post = post

    @property
    def url(self):
        import base62
        encoded_id = self.post.post_type[0] + base62.encode(self.id)
        site_url = app.config.get('SHORT_SITE_URL')
        return '/'.join((site_url, encoded_id))


#CREATE TABLE mention (
#	id INTEGER NOT NULL AUTO_INCREMENT,
#	source VARCHAR(256),
#	post_id INTEGER,
#	content TEXT,
#       is_reply BOOL,
#	PRIMARY KEY (id),
#	FOREIGN KEY(post_id) REFERENCES post (id)
#)

class Mention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(256))
    permalink = db.Column(db.String(256))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    content = db.Column(db.Text)
    mention_type = db.Column(db.String(64))
    author_name = db.Column(db.String(256))
    author_url = db.Column(db.String(256))
    author_image = db.Column(db.String(256))
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
        return "<Mention: {} from {}>".format(self.mention_type, self.source)
