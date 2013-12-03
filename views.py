import logging
from datetime import datetime
import time

from flask import request, redirect, url_for, render_template, flash, abort, make_response
from functools import wraps

from app import *
from models import *
from auth import login_mgr, load_user

from flask.ext.login import login_required, login_user, logout_user, current_user
from flask_wtf import Form

from wtforms import TextField, StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired

from twitter_plugin import TwitterClient
from webmention_plugin import MentionClient

twitter_client = TwitterClient(app)
mention_client = MentionClient(app)

def get_posts(post_type, page, per_page):
    query = Post.query
    if post_type:
        query = query.filter_by(post_type=post_type)
    query = query.order_by(Post.pub_date.desc())
    pagination  = query.paginate(page, per_page)
    return pagination, pagination.items

def render_posts(title, post_type, page, per_page):
    _, articles = get_posts('article', 1, 5)
    pagination, posts = get_posts(post_type, page, per_page)
    return render_template('posts.html', pagination=pagination,
                           posts=posts, articles=articles,
                           post_type=post_type, title=title,
                           authenticated=current_user.is_authenticated())    

@app.route('/', defaults={'page':1})
@app.route('/page/<int:page>')
def index(page):
    return render_posts(None, None, page, 30)

@app.route('/articles', defaults={'page':1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', 'article', page, 10)

@app.route('/notes', defaults={'page':1})
@app.route('/notes/page/<int:page>')
def notes(page):
    return render_posts('All Notes', 'note', page, 30)

@app.route("/all.atom")
def all_atom():
    pagination, posts = get_posts(None, 1, 30)
    return make_response(render_template('posts.atom', title='All Posts', posts=posts), 200,
                         { 'Content-Type' : 'application/atom+xml' })

@app.route('/<post_type>/<int:year>/<post_id>', defaults={'slug':None})
@app.route('/<post_type>/<int:year>/<post_id>/<slug>')
def post_by_id(post_type, year, post_id, slug):
    post = Post.query\
           .filter(Post.post_type == post_type, Post.id == post_id)\
           .first()
    if not post:
        abort(404)
    _, articles = get_posts('article', 1, 5)
    return render_template('post.html', post=post, title=post.title,
                           articles=articles,
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
        post.content_format = request.form.get('content_format', 'plain')
        pub_date = request.form.get('date', '').strip()
        if pub_date:
            post.pub_date = time.strptime(pub_date, '%Y-%m-%d %H:%M')
        else:
            post.pub_date = datetime.now()
        
        send_to_twitter = request.form.get("send_to_twitter")
        

        if not post.id:
            db.session.add(post)
        db.session.commit()

        # TODO everything else could be asynchronous
        # post or update this post on twitter
        try:
            if send_to_twitter:
                twitter_client.handle_new_or_edit(post)
                db.session.commit()
        except:
            app.logger.exception('')

        try:
            mention_client.handle_new_or_edit(post)
            db.session.commit()
        except:
            app.logger.exception('')
        
        return redirect(post.permalink_url)

    return render_template('edit_post.html', post=post,
                           authenticated=current_user.is_authenticated())
      
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

def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page
