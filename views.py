import logging

from flask import request, redirect, url_for, render_template, flash, abort, Response
from functools import wraps

from app import *
from models import *
from auth import login_mgr, load_user

from flask.ext.login import login_required, login_user, logout_user, current_user
from flask_wtf import Form

from wtforms import TextField, StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired

import twitter_plugin
from webmention_plugin import mention_client

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
    return render_template('index.html', notes=notes, articles=articles,
                           authenticated=current_user.is_authenticated())

@app.route('/articles', defaults={'page':1})
@app.route('/articles/page/<int:page>')
def articles(page):
    pagination, articles = get_posts('article', page, 10)
    return render_template('articles.html', pagination=pagination, articles=articles,
                           title="All Articles", authenticated=current_user.is_authenticated())

@app.route('/notes', defaults={'page':1})
@app.route('/notes/page/<int:page>')
def notes(page):
    pagination, notes = get_posts('note', page, 30)
    return render_template('notes.html', pagination=pagination, notes=notes,
                           title="All Notes", authenticated=current_user.is_authenticated())


@app.route('/<post_type>/<int:year>/<post_id>', defaults={'slug':None})
@app.route('/<post_type>/<int:year>/<post_id>/<slug>')
def post_by_id(post_type, year, post_id, slug):
    post = Post.query\
           .filter(Post.post_type == post_type, Post.id == post_id)\
           .first()
    if not post:
        abort(404)
    template = 'article.html' if post_type == 'article' else 'note.html'
    return render_template(template, post=post, title=post.title,
                           authenticated=current_user.is_authenticated())



class LoginForm(Form):
    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    remember = BooleanField('remember')
    
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        # login and validate the user...
        user = load_user(form.username.data)
        login_user(user, remember=form.remember.data)
        flash("Logged in successfully.")
        return redirect(request.args.get("next") or url_for("index"))
        
    return render_template("login.html", form=form)

@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/delete/<post_type>/<post_id>')
@login_required
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
        db.session.commit()

        # TODO everything else could be asynchronous
        # post or update this post on twitter
        try:
            if send_to_twitter:
                twitter_plugin.handle_new_or_edit(post)
                db.session.commit()
        except:
            app.logger.exception('')

        try:
            mention_client.handle_new_or_edit(post)
            db.session.commit()
        except:
            app.logger.exception('')
        
        return redirect(post.permalink_url)

    return render_template('edit_post.html', post=post)
      
@app.route('/admin/new/<post_type>', methods = ['GET','POST'])
@login_required
def new_post(post_type):
    author = User.query.first()
    content_format = 'plain' if post_type == 'note' else 'markdown'
    post = Post('', '', '', post_type, content_format, author, None)   
    return handle_new_or_edit(request, post)

@app.route('/admin/edit/<post_type>/<post_id>', methods=['GET', 'POST'])
@login_required
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
