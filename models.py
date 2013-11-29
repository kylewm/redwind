from app import app, db
import datetime
from flask import Markup

from werkzeug.security import generate_password_hash, \
     check_password_hash

def markdown_filter(data):
    from markdown import markdown
    from smartypants import smartypants
    return Markup(smartypants(markdown(data, extensions=['codehilite'])))

def plain_text_filter(plain):
    from flask import Markup
    return Markup(plain.replace('\n', '<br/>'))

def get_md5_hash(inp):
    result = get_md5_hash.cache.get(inp)
    if not result:
        import hashlib
        result = hashlib.md5(inp.encode()).hexdigest()
        get_md5_hash.cache[inp] = result
    return result    

get_md5_hash.cache = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    pw_hash = db.Column(db.String(256))
    display_name = db.Column(db.String(80))
    twitter_username = db.Column(db.String(80))

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
        return self.login
            
    @property
    def image_url(self):
        return "http://gravatar.com/avatar/{}?s=64".format(get_md5_hash(self.email))

    def __init__(self, login, email, password):
        self.login = login
        self.email = email
        self.set_password(password)
        
    def __repr__(self):
        return 'user:{}'.format(self.login)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'tag:{}'.format(self.name)

tags_to_posts = db.Table('tags_to_posts', db.Model.metadata,
                         db.Column('tag_id', db.Integer, db.ForeignKey('tag.id')),
                         db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
                         db.Column('position', db.Integer))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pub_date = db.Column(db.DateTime)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = db.relationship('User',
                             backref=db.backref('posts', lazy='dynamic'))
    title = db.Column(db.String(256))
    content = db.Column(db.Text)
    post_type = db.Column(db.String(64)) # note/article/etc.
    content_format = db.Column(db.String(64)) # markdown/html/plain
    in_reply_to = db.Column(db.String(256))
    repost_source = db.Column(db.String(256))
    twitter_status_id = db.Column(db.String(64))
    slug = db.Column(db.String(256))
    tags = db.relationship('Tag', secondary=tags_to_posts,
                           order_by=tags_to_posts.columns.position, 
                           backref='posts')
    
    def __init__(self, title, slug, content, post_type, content_format, author, pub_date=None):
        self.title = title
        self.slug = slug
        self.content = content
        self.post_type = post_type
        self.content_format = content_format
        self.author = author
        if pub_date is None:
            self.pub_date = datetime.datetime.utcnow()
        else:
            self.pub_date = pub_date

    def format_text(self, text):
        if self.content_format == 'markdown':
            return markdown_filter(text)
        elif self.content_format == 'plain':
            return plain_text_filter(text)
        else:
            return text

    @property
    def html_content(self):
        return self.format_text(self.content)

    @property
    def html_excerpt(self):
        text = self.html_content
        split = text.split('<!-- more -->', 1)
        text = split[0]
        if (len(split) > 1):
            text += Markup("<a href={}>Keep Reading...</a>".format(self.permalink_url))
        return text
            
    @property
    def permalink_url(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'
        path_components = [site_url, self.post_type, str(self.pub_date.year), str(self.id)]
        if self.slug:
            path_components.append(self.slug)
        return '/'.join(path_components)
        
    @property
    def permalink_short_url(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'
        path_components = [site_url, self.post_type, str(self.pub_date.year), str(self.id)]
        return '/'.join(path_components)
        
    @property
    def twitter_url(self):
        if self.twitter_status_id:
            return "http://twitter.com/{}/status/{}".format(
                self.author.twitter_username,
                self.twitter_status_id)

    def __repr__(self):
        if self.title:
            return 'post:{}'.format(self.title)
        else:
            return 'post:{}'.format(self.content[:20])
