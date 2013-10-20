from app import db
from datetime import datetime

from werkzeug.security import generate_password_hash, \
     check_password_hash


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    pw_hash = db.Column(db.String(256))

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
        return self.id
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
    body = db.Column(db.Text)
    slug = db.Column(db.String(256))
    tags = db.relationship('Tag', secondary=tags_to_posts,
                           order_by=tags_to_posts.columns.position, 
                           backref='posts')
    
    def __init__(self, title, slug, body, author, pub_date=None):
        self.title = title
        self.slug = slug
        self.body = body
        self.author = author
        if pub_date is None:
            self.pub_date = datetime.utcnow()
        else:
            self.pub_date = pub_date
        
    def __repr__(self):
        return 'post:{}'.format(self.title)
