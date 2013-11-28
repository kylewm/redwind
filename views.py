
from flask import request, redirect, url_for, render_template, flash, abort, Response
from functools import wraps

from app import *
from models import *
from auth import requires_auth

import twitter_plugin

def get_posts(post_type, page, per_page):
    pagination = Post.query\
                     .filter_by(post_type=post_type)\
                     .order_by(Post.pub_date.desc())\
                     .paginate(page, per_page)
    return pagination, pagination.items

@app.route('/')
def index():
    note_pagination, notes = get_posts('note', 1, 10)
    article_pagination, articles = get_posts('article', 1, 10)
    return render_template('index.html', notes=notes, articles=articles)

@app.route('/articles', defaults={'page':1})
@app.route('/articles/page/<int:page>')
def articles(page):
    pagination, articles = get_posts('article', page, 10)
    return render_template('articles.html', pagination=pagination, articles=articles, title="All Articles")


@app.route('/notes', defaults={'page':1})
@app.route('/notes/page/<int:page>')
def notes(page):
    pagination, notes = get_posts('note', page, 30)
    return render_template('notes.html', pagination=pagination, notes=notes, title="All Notes")


@app.route('/<post_type>/<int:year>/<post_id>', defaults={'slug':None})
@app.route('/<post_type>/<int:year>/<post_id>/<slug>')
def post_by_id(post_type, year, post_id, slug):
    post = Post.query\
           .filter(Post.post_type == post_type, Post.id == post_id)\
           .first()
    if not post:
        abort(404)
    return render_template('article.html', post=post, title=post.title)

@app.route('/admin/delete/<post_type>/<post_id>')
@requires_auth
def delete_by_id(post_type, post_id):
    post = Post.query.filter(Post.id == post_id).first()
    if not post:
        abort(404)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))

def handle_new_or_edit(request, post):    
    if request.method == 'POST':
        # populate the Post object and save it to the database, redirect to the view
        post.title = request.form.get('title', '')
        post.content = request.form.get('content')
        post.slug = request.form.get('slug')
        post.in_reply_to = request.form.get('in_reply_to', '')
        post.repost_source = request.form.get('repost_source', '')
        send_to_twitter = request.form.get("send_to_twitter")
        
        if not post.id:
            db.session.add(post)

        # post or update this post on twitter
        if send_to_twitter:
            twitter_plugin.handle_new_or_edit(post)
            
        db.session.commit()
        return redirect(post.permalink_url)

    return render_template('edit_post.html', post=post)
      
@app.route('/admin/new/<post_type>', methods = ['GET','POST'])
@requires_auth
def new_post(post_type):
    author = User.query.first()
    content_format = 'plain' if post_type == 'note' else 'markdown'
    post = Post('', '', '', post_type, content_format, author, None)   
    return handle_new_or_edit(request, post)

@app.route('/admin/edit/<post_type>/<post_id>', methods=['GET', 'POST'])
@requires_auth
def edit_by_id(post_type, post_id):
    post = Post.query.filter(Post.id == post_id).first()
    if not post:
        abort(404)
    return handle_new_or_edit(request, post)

@app.route("/css/pygments.css")
def pygments_css():
    import pygments.formatters
    pygments_css = (pygments.formatters.HtmlFormatter(style=app.config['PYGMENTS_STYLE'])
                    .get_style_defs('.codehilite'))
    return app.response_class(pygments_css, mimetype='text/css')
    
@app.template_filter('strftime')
def strftime_filter(date, fmt='%Y %b %d'):
    return date.strftime(fmt)
