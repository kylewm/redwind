
from flask import request, redirect, url_for, render_template, flash

from app import *
from models import *

@app.route('/')
def index():
    notes = Post.query\
            .filter_by(post_type = 'note')\
            .order_by(Post.pub_date.desc())\
            .limit(30)\
            .all()

    articles = Post.query\
               .filter_by(post_type = 'article')\
               .order_by(Post.pub_date.desc())\
               .limit(5)\
               .all()

    return render_template('index.html', notes=notes, articles=articles)

@app.route('/articles')
def articles():
    pass

@app.route('/notes')
def notes():
    pass

@app.route('/<post_type>/<post_id>')
def post_by_id(post_type, post_id):
    post = Post.query\
           .filter(Post.post_type == post_type, Post.id == post_id)\
           .first()
    if not post:
        abort(404)
    return render_template('article.html', post=post)
      
@app.route('/<post_type>/<int:year>/<int:month>/<int:day>/<slug>')
def post_by_slug(post_type, year, month, day, slug):
    post = Post.query\
           .filter(Post.post_type == post_type, Post.slug == slug)\
           .first()
    if not post:
        abort(404)
    return render_template('article.html', post=post)

@app.route('/edit/<post_id>')
def edit_by_id(post_id):
    post = Post.query\
           .filter(Post.id == post_id)\
           .first()
    return render_template('edit_post.html', post=post)


@app.route("/css/pygments.css")
def pygments_css():
    import pygments.formatters
    pygments_css = (pygments.formatters.HtmlFormatter(style=app.config['PYGMENTS_STYLE'])
                    .get_style_defs('.codehilite'))
    return app.response_class(pygments_css, mimetype='text/css')
    
@app.template_filter('strftime')
def strftime_filter(date, fmt='%Y %b %d'):
    return date.strftime(fmt)
