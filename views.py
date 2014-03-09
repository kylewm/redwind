from app import app, db
from models import Post, Mention, User
from auth import load_user
from twitter_plugin import TwitterClient
from webmention_plugin import MentionClient
from push_plugin import PushClient
from facebook_plugin import FacebookClient

import webmention_receiver

from datetime import datetime
import time
import os
import re
import urllib

from flask import request, redirect, url_for, render_template,\
    flash, abort, make_response, jsonify, Markup
from flask.ext.login import login_required, login_user,\
    logout_user, current_user
from flask_wtf import Form
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired
from bs4 import BeautifulSoup, Comment

from werkzeug import secure_filename


twitter_client = TwitterClient(app)
facebook_client = FacebookClient(app)
mention_client = MentionClient(app)
push_client = PushClient(app)


class DisplayPost:

    @classmethod
    def get_posts(cls, post_type, page, per_page):
        query = Post.query
        if post_type:
            query = query.filter_by(post_type=post_type)
        query = query.order_by(Post.pub_date.desc())
        pagination = query.paginate(page, per_page)
        return pagination, [cls(post) for post in pagination.items]

    @classmethod
    def get_post(cls, post_id):
        post = Post.query.filter_by(id=post_id).first()
        return cls(post) if post else None

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    def markdown_filter(self, data):
        from markdown import markdown
        from smartypants import smartypants
        return smartypants(markdown(data, extensions=['codehilite']))

    def plain_text_filter(self, plain):
        plain = re.sub(r'\b(?<!href=.)https?://([a-zA-Z0-9/\.\-_:%?@$#&=]+)',
                       r'<a href="\g<0>">\g<1></a>', plain)
        plain = re.sub(r'(?<!\w)@([a-zA-Z0-9_]+)',
                       r'<a href="http://twitter.com/\g<1>">\g<0></a>', plain)
        plain = plain.replace('\n', '<br/>')
        return plain

    def repost_preview_filter(self, url):
        #youtube embeds
        m = re.match(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)', url)
        if m:
            preview = """<iframe width="560" height="315" """
            """src="//www.youtube.com/embed/{}" frameborder="0" """
            """allowfullscreen></iframe>"""\
                .format(m.group(1))
            return preview, True

        #instagram embeds
        m = re.match(r'https?://instagram\.com/p/(\w+)/?#?', url)
        if m:
            preview = """<iframe src="//instagram.com/p/{}/embed/" """
            """width="400" height="500" frameborder="0" scrolling="no" """
            """allowtransparency="true"></iframe>"""\
                .format(m.group(1))
            return preview, True

        preview = twitter_client.repost_preview(self.author, url)
        if preview:
            return preview, True

        #fallback
        m = re.match(r'https?://(.*)', url)
        if m:
            preview = """<a href="{}">{}</a>""".format(url, m.group(1))
            return preview, False

        # TODO when the post is first created, we should fetch the
        # reposted URL and save some information about it (i.e.,
        # information we can't get from the page title, whether it is an
        # image, etc.)

    def format_text(self, text):
        if self.content_format == 'markdown':
            return self.markdown_filter(text)
        elif self.content_format == 'plain':
            return self.plain_text_filter(text)
        else:
            return text

    def add_preview(self, text):
        preview = self.repost_preview

        if not preview and self.repost_source:
            preview, cache = self.repost_preview_filter(self.repost_source)
            if preview and cache:
                self.wrapped.repost_preview = preview
                db.session.commit()

        if preview:
            text += '<div>' + preview + '</div>'

        return text

    @property
    def html_content(self):
        text = self.format_text(self.content)
        text = self.add_preview(text)
        markup = Markup(text)
        return markup

    @property
    def html_excerpt(self):
        text = self.format_text(self.content)
        split = text.split('<!-- more -->', 1)
        text = self.add_preview(split[0])
        if len(split) > 1:
            text += "<br/><a href={}>Keep Reading...</a>"\
                . format(self.permalink_url)
        return Markup(text)

    @property
    def permalink_url(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'
        path_components = [site_url, self.post_type, str(self.pub_date.year),
                           str(self.id)]
        if self.slug:
            path_components.append(self.slug)
        return '/'.join(path_components)

    @property
    def permalink_short_url(self):
        site_url = app.config.get('SITE_URL') or 'http://localhost'
        path_components = [site_url, self.post_type, str(self.pub_date.year),
                           str(self.id)]
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


def render_posts(title, post_type, page, per_page):
    _, articles = DisplayPost.get_posts('article', 1, 5)
    pagination, posts = DisplayPost.get_posts(post_type, page, per_page)
    return render_template('posts.html', pagination=pagination,
                           posts=posts, articles=articles,
                           post_type=post_type, title=title,
                           authenticated=current_user.is_authenticated())


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    return render_posts(None, None, page, 30)


@app.route('/articles', defaults={'page': 1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', 'article', page, 10)


@app.route('/notes', defaults={'page': 1})
@app.route('/notes/page/<int:page>')
def notes(page):
    return render_posts('All Notes', 'note', page, 30)


def render_posts_atom(title, post_type, count):
    _, posts = DisplayPost.get_posts(post_type, 1, count)
    return make_response(render_template('posts.atom', title=title,
                                         posts=posts), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route("/all.atom")
def all_atom():
    return render_posts_atom('All Posts', None, 30)


@app.route("/notes.atom")
def notes_atom():
    return render_posts_atom('Notes', 'note', 30)


@app.route("/articles.atom")
def articles_atom():
    return render_posts_atom('Articles', 'article', 10)


@app.route('/<post_type>/<int:year>/<post_id>', defaults={'slug': None})
@app.route('/<post_type>/<int:year>/<post_id>/<slug>')
def post_by_id(post_type, year, post_id, slug):
    post = DisplayPost.get_post(post_id)
    if not post:
        abort(404)
    _, articles = DisplayPost.get_posts('article', 1, 5)
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

        next_enc = request.args.get("next")
        next_url = (urllib.parse.unquote(next_enc)
                    if next_enc else url_for("index"))
        return redirect(next_url)

    return render_template("login.html", form=form)


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin/settings')
@login_required
def settings():
    return render_template("settings.html", user=current_user,
                           authenticated=current_user.is_authenticated())


@app.route('/admin/delete/<post_type>/<post_id>')
@login_required
def delete_by_id(post_type, post_id):

    if post_type == 'mention':
        post = Mention.query.filter_by(id=post_id).first()
    else:
        post = Post.query.filter_by(id=post_id).first()

    if not post:
        abort(404)

    db.session.delete(post)
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


def handle_new_or_edit(request, post):
    if request.method == 'POST':
        # populate the Post object and save it to the database,
        # redirect to the view
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
        send_to_facebook = request.form.get("send_to_facebook")

        twitter_status_id = request.form.get("twitter_status_id")
        if not send_to_twitter and twitter_status_id:
            post.twitter_status_id = twitter_status_id

        facebook_post_id = request.form.get("facebook_post_id")
        if not send_to_facebook and facebook_post_id:
            post.facebook_post_id = facebook_post_id

        if not post.id:
            db.session.add(post)
        db.session.commit()

        # TODO everything else could be asynchronous
        # post or update this post on twitter
        if send_to_twitter:
            try:
                twitter_client.handle_new_or_edit(post)
                db.session.commit()
            except:
                app.logger.exception('posting to twitter')

        if send_to_facebook:
            try:
                facebook_client.handle_new_or_edit(post)
                db.session.commit()
            except:
                app.logger.exception('posting to facebook')

        try:
            push_client.handle_new_or_edit(post)
        except:
            app.logger.exception('posting to PuSH')

        try:
            mention_client.handle_new_or_edit(post)
            db.session.commit()
        except:
            app.logger.exception('sending webmentions')

        return redirect(post.permalink_url)

    return render_template('edit_post.html', post=post,
                           authenticated=current_user.is_authenticated())


@app.route('/admin/new/<post_type>', methods=['GET', 'POST'])
@login_required
def new_post(post_type):
    author = User.query.first()
    content_format = 'plain' if post_type == 'note' else 'markdown'
    post = Post('', '', '', post_type, content_format, author, None)
    return handle_new_or_edit(request, post)


@app.route('/admin/edit/<post_type>/<post_id>', methods=['GET', 'POST'])
@login_required
def edit_by_id(post_type, post_id):
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        abort(404)
    return handle_new_or_edit(request, post)


@app.template_filter('strftime')
def strftime_filter(date, fmt='%Y %b %d'):
    if not date:
        return "????"
    return date.strftime(fmt)


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page


@app.template_filter('html_to_plain')
def html_to_plain(content):
    soup = BeautifulSoup(str(content))
    text = soup.get_text()
    return Markup.escape(text)


@app.template_filter('atom_sanitize')
def atom_sanitize(content):
    soup = BeautifulSoup(str(content))
    for tag in soup.find_all('script'):
        tag.replace_with(soup.new_string('removed script tag', Comment))
    result = Markup(soup)
    return result


@app.route('/admin/upload', methods=['POST'])
@login_required
def receive_upload():
    file = request.files['file']
    filename = secure_filename(file.filename)
    now = datetime.now()
    directory = os.path.join('static', 'uploads',
                             str(now.year), str(now.month).zfill(2))
    path = os.path.join(directory, filename)
    if not os.path.exists(directory):
        os.makedirs(directory)
    file.save(path)
    return jsonify({'path': '/' + path})


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    source = request.form.get('source')
    target = request.form.get('target')

    app.logger.debug("Webmention from %s to %s received", source, target)

    result = webmention_receiver.process_webmention(source, target)
    if not result:
        abort(404)
    return result
