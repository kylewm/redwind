import re
from unicodedata import normalize

from app import app, db
from models import Post, User, Tag
from flask import jsonify, abort, make_response, request, url_for


class ApiException(Exception):
    def __init__(self, desc, status_code):
        Exception.__init__(self)
        self.status_code = status_code
        self.desc = desc

@app.errorhandler(ApiException)
def not_found(error):
    return make_response(jsonify( { 'error': error.desc } ), error.status_code)

@app.route("/api/v1.0/posts", methods=["GET"])
def get_posts():
    post_list = []
    for post in db.session.query(Post).all():
        post_obj = {
            'id' : post.id,
            'title' : post.title,
            'slug' : post.slug,
            'pub_date' : post.pub_date,
            'tags' : [ tag.name for tag in post.tags ],
            'uri' : url_for("get_post", post_id=post.id, _external=True)
        }
        post_list.append(post_obj)
    return jsonify({ 'posts' : post_list })

@app.route("/api/v1.0/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    post = db.session.query(Post).filter_by(id=post_id).first()
    if post is None:
        raise ApiException("Could not find post with id {}".format(post_id), 404)
    post_obj = {
        'id' : post.id,
        'title' : post.title,
        'slug' : post.slug,
        'pub_date' : post.pub_date,
        'tags' : [ tag.name for tag in post.tags ],
        'body' : post.body
    }
    return jsonify({ 'post' : post_obj })

@app.route("/api/v1.0/posts", methods=["POST"])
def create_post():
    if not request.json or not 'post' in request.json:
        raise ApiException("Invalid create post", 400)
    post_obj = request.json['post']
    
    title = post_obj.get('title')
    slug = post_obj.get('slug') or slugify(title)
    body = post_obj.get('body')
    author = db.session.query(User).first()
    post = Post(title, slug, body, author)
    
    db.session.add(post)
    db.session.commit()
    
    return jsonify({
        'id' : post.id,
        'title' : post.title,
        'slug' : post.slug,
        'author' : post.author.login,
        'uri' : url_for('get_post', post_id=post.id, _external=True),
    }), 201


@app.route("/api/v1.0/posts/<int:post_id>", methods=["PUT"])
def update_post(post_id):
    if not request.json or not 'post' in request.json:
        raise ApiException("Invalid create post", 400)
    post_obj = request.json['post']
    
    title = post_obj.get('title')
    slug = post_obj.get('slug')
    body = post_obj.get('body')

    post = db.session.query(Post)\
                     .filter_by(id=post_id)\
                     .first()
    if not post:
        raise ApiException("Could not find post with id {}".format(post_id))

    if title:
        post.title = title
    if slug:
        post.slug = slug
    if body:
        post.body = body

    db.session.commit()

    return jsonify({
        'id' : post.id,
        'title' : post.title,
        'slug' : post.slug,
        'author' : post.author.login,
        'uri' : url_for('get_post', post_id=post.id, _external=True),
    }), 201


@app.route("/api/v1.0/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):
    post = db.session.query(Post)\
                     .filter_by(id=post_id)\
                     .first()
    if not post:
        raise ApiException("Could not find post with id {}".format(post_id))

    db.session.delete(post)
    db.session.commit()

    return jsonify({ "result" : True })
    
    

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an slightly worse ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', word).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))
