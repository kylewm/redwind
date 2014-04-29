# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.

from . import app, util, push, webmention_sender, webmention_receiver,\
    contexts, twitter, facebook
from .models import Post, Location, POST_TYPES
from .archive import load_json_from_archive
from .auth import load_user
from . import hentry_parser

from bs4 import BeautifulSoup
from flask import request, redirect, url_for, render_template, flash,\
    abort, make_response, jsonify, Markup
from flask.ext.login import login_required, login_user, logout_user,\
    current_user
from contextlib import contextmanager
from urllib.parse import urlparse, urljoin

from werkzeug import secure_filename

import datetime
import bleach
import os
import pytz
import re
import requests
import unicodedata

bleach.ALLOWED_TAGS += ['img', 'p', 'br']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})

TIMEZONE = pytz.timezone('US/Pacific')

POST_TYPE_RULE = '<any(' + ','.join(POST_TYPES) + '):post_type>'
DATE_RULE = '<int:year>/<int(fixed_digits=2):month>/'\
            '<int(fixed_digits=2):day>/<index>'


def reraise_attribute_errors(func):
    """@property and my override of getattr don't mix — they swallow up
    AttributeErrors with no log messages, so I need this ugly hack to
    turn them into RuntimeErrors
    """
    def go(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AttributeError as e:
            raise RuntimeError(e)
    return go


class DisplayPost:

    YOUTUBE_RE = re.compile(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)')
    INSTAGRAM_RE = re.compile(r'https?://instagram\.com/p/(\w+)/?#?')

    def __init__(self, wrapped):
        self.wrapped = wrapped
        self._mentions = None

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    def repost_preview_filter(self, url):
        #youtube embeds
        m = self.YOUTUBE_RE.match(url)
        if m:
            preview = """<iframe width="560" height="315" """\
                """src="//www.youtube.com/embed/{}" frameborder="0" """\
                """allowfullscreen></iframe>"""\
                .format(m.group(1))
            return preview, False

        #instagram embeds
        m = self.INSTAGRAM_RE.match(url)
        if m:
            preview = """<iframe src="//instagram.com/p/{}/embed/" """\
                """width="400" height="500" frameborder="0" scrolling="no" """\
                """allowtransparency="true"></iframe>"""\
                .format(m.group(1))
            return preview, False
        return None, False

    def get_share_preview(self):
        text = ''
        for repost_of in self.repost_of:
            preview, _ = self.repost_preview_filter(repost_of)
            if preview:
                text += '<div>' + preview + '</div>'
        return text

    @property
    @reraise_attribute_errors
    def reply_contexts(self):
        if not self.in_reply_to:
            return []
        return [ContextProxy(url) for url in self.in_reply_to]

    @property
    @reraise_attribute_errors
    def share_contexts(self):
        try:
            if not self.repost_of:
                return []
            return [ContextProxy(url) for url in self.repost_of]
        except AttributeError:
            # FIXME if we fail to catch this attribute error, it gets swallowed up
            # by the @property handler
            app.logger.exception("getting share contexts")
            return []

    @property
    @reraise_attribute_errors
    def like_contexts(self):
        if not self.like_of:
            return []
        return [ContextProxy(url) for url in self.like_of]

    @property
    @reraise_attribute_errors
    def html_content(self):
        return Markup(self.get_html_content(True))

    def get_html_content(self, include_preview=True):
        text = markdown_filter(self.content)
        if include_preview and self.post_type == 'share':
            preview = self.get_share_preview()
            text += preview
        return text

    @property
    @reraise_attribute_errors
    def html_excerpt(self):
        text = markdown_filter(self.content)
        split = text.split('<!-- more -->', 1)
        if self.post_type == 'share':
            text += self.get_share_preview(split[0])
        if len(split) > 1:
            text += "<br/><a href={}>Keep Reading...</a>"\
                . format(self.permalink)
        return Markup(text)

    @property
    @reraise_attribute_errors
    def first_image(self):
        """find the first image (if any) that is in an <img> tag
        in the rendered post"""
        html = self.html_content
        soup = BeautifulSoup(html)
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                return urljoin(app.config['SITE_URL'], src)

    @property
    @reraise_attribute_errors
    def mentions(self):
        if self._mentions is None:
            self._mentions = [MentionProxy(self, m) for m
                              in self.wrapped.mentions]
        return self._mentions

    def _mentions_sorted_by_date(self, mtype):
        def by_date(m):
            result = m.pub_date or\
                datetime.datetime(datetime.MINYEAR, 1, 1)
            if result and hasattr(result, 'tzinfo') and not result.tzinfo:
                result = pytz.utc.localize(result)
            return result
        filtered = [m for m in self.mentions
                    if not m.deleted
                    and (not mtype or m.reftype == mtype)]
        filtered.sort(key=by_date)
        return filtered

    def _mention_count(self, mtype):
        count = len([m for m in self.mentions
                     if not m.deleted
                     and (not mtype or m.reftype == mtype)])
        return count

    @property
    @reraise_attribute_errors
    def mention_count(self):
        return self._mention_count(None)

    @property
    @reraise_attribute_errors
    def likes(self):
        try:
            return self._mentions_sorted_by_date('like')
        except:
            app.logger.exception("fetching likes")

    @property
    @reraise_attribute_errors
    def like_count(self):
        return self._mention_count('like')

    @property
    @reraise_attribute_errors
    def reposts(self):
        return self._mentions_sorted_by_date('repost')

    @property
    @reraise_attribute_errors
    def repost_count(self):
        return self._mention_count('repost')

    @property
    @reraise_attribute_errors
    def replies(self):
        return self._mentions_sorted_by_date('reply')

    @property
    @reraise_attribute_errors
    def reply_count(self):
        return self._mention_count('reply')

    @property
    @reraise_attribute_errors
    def references(self):
        return self._mentions_sorted_by_date('reference')

    @property
    @reraise_attribute_errors
    def reference_count(self):
        return self._mention_count('reference')


class ContextProxy:
    def __init__(self, url):
        self.permalink = url
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.pub_date = None
        self.title = None
        self.deleted = False

        blob = load_json_from_archive(url)
        if not blob:
            return
        self.entry = hentry_parser.parse_json(blob, url)
        if not self.entry:
            return

        self.permalink = self.entry.permalink
        self.author_name = self.entry.author.name if self.entry.author else ""
        self.author_url = self.entry.author.url if self.entry.author else ""
        self.author_image = self.entry.author.photo if self.entry.author else ""
        self.content = self.entry.content
        self.pub_date = self.entry.pub_date
        self.title = self.entry.title
        self.deleted = False


class MentionProxy:
    def __init__(self, post, url):
        self.permalink = url
        self.reftype = 'reference'
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.pub_date = None
        self.title = None
        self.deleted = False

        blob = load_json_from_archive(url)
        if not blob:
            return

        self.entry = hentry_parser.parse_json(blob, url)
        if not self.entry:
            return

        self.permalink = self.entry.permalink
        self.author_name = self.entry.author.name if self.entry.author else ""
        self.author_url = self.entry.author.url if self.entry.author else ""
        self.author_image = self.entry.author.photo if self.entry.author else ""
        self.content = self.entry.content
        self.pub_date = self.entry.pub_date
        self.title = self.entry.title

        target_urls = (
            post.permalink,
            post.permalink_without_slug,
            post.short_permalink,
            post.permalink.replace(app.config['SITE_URL'], 'http://kylewm.com')
        )

        for ref in self.entry.references:
            if ref.url in target_urls:
                self.reftype = ref.reftype


    def __repr__(self):
        return """Mention(permalink={}, pub_date={} reftype={})""".format(
            self.permalink, self.pub_date, self.reftype)


def render_posts(title, post_types, page, per_page,
                 include_hidden=False, include_drafts=False):
    posts = [DisplayPost(post) for post in Post.load_recent(
        per_page, post_types, include_hidden, include_drafts)]
    return render_template('posts.html', posts=posts, title=title)


@app.context_processor
def inject_user_authenticated():
    with open(os.path.join(app.root_path, 'static/css/style.css')) as f:
        inline_style = f.read()
    # minify
    # inline_style = re.sub('\s+', ' ', inline_style)
    twitterbot = 'Twitterbot' in request.headers.get('User-Agent', '')
    return {
        'authenticated': current_user.is_authenticated(),
        'inline_style': Markup(inline_style),
        'is_twitter_user_agent': twitterbot,
    }


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    # leave out hidden posts
    return render_posts(None, POST_TYPES, page, 30,
                        include_hidden=False,
                        include_drafts=current_user.is_authenticated())


@app.route('/articles', defaults={'page': 1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', ('article',), page, 10,
                        include_hidden=False,
                        include_drafts=current_user.is_authenticated())


@app.route('/everything', defaults={'page': 1})
@app.route('/everything/page/<int:page>')
def everything(page):
    return render_posts('Everything', POST_TYPES, page, 30,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


def render_posts_atom(title, feed_id, post_types, count):
    posts = [DisplayPost(post) for post in Post.load_recent(count, post_types)]
    return make_response(render_template('posts.atom', title=title,
                                         feed_id=feed_id,
                                         posts=posts), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route("/all.atom")
def all_atom():
    return render_posts_atom('All', 'all.atom', None, 30)


@app.route("/updates.atom")
def updates_atom():
    return render_posts_atom('Updates', 'updates.atom',
                             ('article', 'note', 'share'), 30)


@app.route("/articles.atom")
def articles_atom():
    return render_posts_atom('Articles', 'articles.atom', ('article',), 10)


@app.route("/mentions.atom")
def mentions_atom():
    mention_urls = Post.load_recent_mentions()
    mentions = [MentionProxy(None, u) for u in mention_urls]
    return make_response(render_template('mentions.atom',
                                         title='kylewm.com: Mentions',
                                         feed_id='mentions.atom',
                                         mentions=mentions), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route('/archive', defaults={'year': None, 'month': None})
@app.route('/archive/<int:year>/<int(fixed_digits=2):month>')
def archive(year, month):
    # give the template the posts from this month,
    # and the list of all years/month

    if year and month:
        posts = [DisplayPost(post) for post in Post.load_by_month(year, month)]
        first_of_month = year and month and datetime.date(year, month, 1)
    else:
        posts = []
        first_of_month = None

    years = {}
    for m in Post.get_archive_months():
        years.setdefault(m.year, []).append(m)

    return render_template(
        'archive.html', years=years,
        expanded_month=first_of_month, posts=posts)


@app.route('/' + POST_TYPE_RULE + '/' + DATE_RULE, defaults={'slug': None})
@app.route('/' + POST_TYPE_RULE + '/' + DATE_RULE + '/<slug>')
def post_by_date(post_type, year, month, day, index, slug):
    post = Post.load_by_date(post_type, year, month, day, index)
    if not post:
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not slug and post.slug:
        return redirect(
            url_for('post_by_date', post_type=post_type,
                    year=year, month=month, day=day, index=index,
                    slug=post.slug))

    dpost = DisplayPost(post)
    title = dpost.title
    if not title:
        title = "A {} from {}".format(dpost.post_type,
                                      dpost.pub_date.strftime('%Y-%m-%d'))
    return render_template('post.html', post=dpost, title=title)


@app.route('/short/<string(minlength=5,maxlength=6):tag>')
def shortlink(tag):
    post_type = util.parse_type(tag)
    pub_date = util.parse_date(tag)
    index = util.parse_index(tag)

    if not post_type or not pub_date or not index:
        abort(404)

    return redirect(url_for('post_by_date', post_type=post_type,
                            year=pub_date.year, month=pub_date.month,
                            day=pub_date.day, index=index))


# disable this experimental feature
# @app.route('/original_post_discovery')
# def original_post_discovery():
#     url = request.args.get('syndication')
#     if not url:
#         abort(404)
#
#     index = Post.load_syndication_index()
#     path = index.get(url)
#     if not path:
#         r = requests.get(url)
#         if r.status_code // 100 == 2 and r.url != url:
#             path = index.get(r.url)
#
#     if not path:
#         abort(404)
#
#     post = Post.load_by_path(path)
#     return redirect(post.permalink)


@app.route("/indieauth")
def indie_auth():
    token = request.args.get('token')
    response = requests.get('http://indieauth.com/verify',
                            params={'token': token})

    if response.status_code == 200:
        domain = response.json().get('me')
        user = load_user(domain)
        if user:
            login_user(user, remember=True)
            flash('Logged in with domain {}'.format(domain))
        else:
            flash('No user for domain {}'.format(domain))

    else:
        respjson = response.json()
        flash('Login failed {}: {}'.format(respjson.get('error'),
                                           respjson.get('error_description')))

    return redirect(url_for('index'))


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin/settings')
@login_required
def settings():
    return render_template("settings.html", user=current_user)


@app.route('/admin/delete')
@login_required
def delete_by_id():
    shortid = request.args.get('id')
    with Post.writeable(Post.shortid_to_path(shortid)) as post:
        if not post:
            abort(404)
        post.deleted = True
        post.save()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


@app.route('/admin/new')
@login_required
def new_post():
    post_type = request.args.get('type', 'note')
    post = Post(post_type, None)
    post.content = ''

    if post_type == 'reply':
        in_reply_to = request.args.get('in_reply_to')
        if in_reply_to:
            post.in_reply_to = [in_reply_to]

    if post_type == 'share':
        repost_source = request.args.get('repost_source')
        if repost_source:
            post.repost_of = [repost_source]

    if post_type == 'like':
        post.hidden = True
        like_of = request.args.get('like_of')
        if like_of:
            post.like_of = [like_of]

    content = request.args.get('content')
    if content:
        post.content = content

    return render_template('edit_post.html', post=post,
                           advanced=request.args.get('advanced'))


@app.route('/admin/edit')
@login_required
def edit_by_id():
    shortid = request.args.get('id')
    post = Post.load_by_shortid(shortid)

    if not post:
        abort(404)
    return render_template('edit_post.html', post=post,
                           advanced=request.args.get('advanced'))


@app.route('/admin/uploads')
def uploads_popup():
    return render_template('uploads_popup.html')


@app.template_filter('strftime')
def strftime_filter(thedate, fmt='%Y %b %d'):
    if not thedate:
        thedate = datetime.date(1982, 11, 24)
    if hasattr(thedate, 'tzinfo'):
        if not thedate.tzinfo:
            thedate = pytz.utc.localize(thedate)
        thedate = thedate.astimezone(TIMEZONE)
    return thedate.strftime(fmt)


@app.template_filter('isotime')
def isotime_filter(thedate):
    if not thedate:
        thedate = datetime.date(1982, 11, 24)

    if hasattr(thedate, 'tzinfo'):
        if thedate.tzinfo:
            thedate = thedate.astimezone(pytz.utc)
        else:
            thedate = pytz.utc.localize(thedate)

    return thedate.isoformat()


@app.template_filter('human_time')
def human_time(thedate):
    if not thedate:
        return None

    now = datetime.datetime.utcnow()

    # if the date being formatted has a timezone, make
    # sure utc now does too
    if hasattr(thedate, 'tzinfo') and thedate.tzinfo:
        now = pytz.utc.localize(now)
    delta = now - thedate

    if delta.days < 1:
        # resolve seconds into hours/minutes
        minutes = delta.seconds // 60
        if minutes < 1:
            return "Just now"
        if minutes < 60:
            return "{} minute{} ago".format(minutes, pluralize(minutes))
        else:
            hours = round(minutes/60)
            return "About {} hour{} ago".format(hours, pluralize(hours))

    if delta.days == 1:
        return "Yesterday"

    if delta.days < 30:
        return "{} days ago".format(delta.days)

    if delta.days < 365:
        months = round(delta.days / 30)
        return "About {} month{} ago".format(months, pluralize(months))

    years = round(delta.days / 365)
    return "{} year{} ago".format(years, pluralize(years))


@app.template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    if number == 1:
        return singular
    else:
        return plural


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page


@app.template_filter('html_to_plain')
def html_to_plain(content):
    soup = BeautifulSoup(str(content), 'html5lib')
    text = soup.get_text()
    return Markup.escape(text)


@app.template_filter('atom_sanitize')
def atom_sanitize(content):
    return Markup.escape(str(content))


@app.template_filter('bleach')
def bleach_html(html):
    return bleach.clean(html, strip=True)


@app.template_filter('format_markdown_as_text')
def format_markdown_as_text(content, remove_imgs=True):
    html = markdown_filter(content)
    return format_as_text(html, remove_imgs)


@app.template_filter('format_as_text')
def format_as_text(html, remove_imgs=True):
    soup = BeautifulSoup(html)

    # replace links with the URL
    for a in soup.find_all('a'):
        a.replace_with(a.get('href') or 'link')
    # and images with their alt text
    for i in soup.find_all('img'):
        if remove_imgs:
            i.hidden = True
        else:
            i.replace_with('[{}]'.format(i.get('title')
                                         or i.get('alt')
                                         or 'image'))
    return soup.get_text().strip()


@app.template_filter('markdown')
def markdown_filter(data):
    from markdown import markdown
    from smartypants import smartypants
    return smartypants(
        markdown(data, extensions=['codehilite']))


@app.template_filter('autolink')
def plain_text_filter(plain):
    plain = util.autolink(plain)
    for endl in ('\r\n', '\n', '\r'):
        plain = plain.replace(endl, '<br />')
    return plain


@app.template_filter('prettify_url')
def prettify_url(url):
    split = url.split('//', 1)
    if len(split) == 2:
        schema, path = split
    else:
        path = url
    return path.strip('/')


@app.template_filter('local_mirror')
def local_mirror_resource(url):
    site_netloc = urlparse(app.config['SITE_URL']).netloc

    o = urlparse(url)
    if o.netloc and o.netloc != site_netloc:
        mirror_url_path = os.path.join("_mirror", o.netloc, o.path.strip('/'))
        mirror_file_path = os.path.join(app.root_path, 'static',
                                        mirror_url_path)
        app.logger.debug("checking for existence of mirrored resource %s -> %s",
                         url, mirror_file_path)
        if os.path.exists(mirror_file_path):
            app.logger.debug("%s already mirrored, returning url path %s",
                             mirror_file_path, mirror_url_path)
            return url_for('static', filename=mirror_url_path)

        if util.download_resource(url, mirror_file_path):
            app.logger.debug("%s did not exist, successfully mirrored to %s.",
                             mirror_file_path, mirror_url_path)
            return url_for('static', filename=mirror_url_path)
        else:
            app.logger.warn("failed to download %s to %s for some reason", url,
                            mirror_file_path)

    return url


## API Methods


@app.route('/api/upload_file', methods=['POST'])
@login_required
def upload_file():
    f = request.files['file']
    filename = secure_filename(f.filename)
    now = datetime.datetime.utcnow()

    file_path = 'uploads/{}/{:02d}/{}'.format(now.year, now.month, filename)

    url_path = url_for('static', filename=file_path)
    full_file_path = os.path.join(app.root_path, 'static', file_path)

    if not os.path.exists(os.path.dirname(full_file_path)):
        os.makedirs(os.path.dirname(full_file_path))

    f.save(full_file_path)
    return jsonify({'path': url_path})


@app.route('/api/upload_image', methods=['POST'])
@login_required
def upload_image():
    f = request.files['file']
    filename = secure_filename(f.filename)
    now = datetime.datetime.utcnow()

    file_path = 'uploads/{}/{:02d}/{}'.format(now.year, now.month, filename)

    full_file_path = os.path.join(app.root_path, 'static', file_path)
    if not os.path.exists(os.path.dirname(full_file_path)):
        os.makedirs(os.path.dirname(full_file_path))
    f.save(full_file_path)

    result = {'original': url_for('static', filename=file_path)}

    sizes = [('small', 300), ('medium', 600), ('large', 1024)]
    for tag, side in sizes:
        result[tag] = resize_image(file_path, tag, side)

    return jsonify(result)


def resize_image(path, tag, side):
    from PIL import Image

    dirname, filename = os.path.split(path)
    ext = '.jpg'

    split = filename.rsplit('.', 1)
    if len(split) > 1:
        filename, ext = split

    newpath = os.path.join(dirname, '{}-{}.{}'.format(filename, tag, ext))
    im = Image.open(os.path.join(app.root_path, 'static', path))

    origw, origh = im.size
    ratio = side / max(origw, origh)

    im = im.resize((int(origw * ratio), int(origh * ratio)), Image.ANTIALIAS)
    im.save(os.path.join(app.root_path, 'static', newpath))
    return url_for('static', filename=newpath)


@app.route('/admin/save', methods=['POST'])
@login_required
def save_post():

    @contextmanager
    def new_or_writeable(shortid):
        if shortid == 'new':
            post_type = request.form.get('post_type', 'note')
            post = Post(post_type, None)
            post._writeable = True
            yield post
        else:
            with Post.writeable(Post.shortid_to_path(shortid)) as post:
                yield post

    try:
        post_id_str = request.form.get('post_id')
        app.logger.debug("saving post %s", post_id_str)
        with new_or_writeable(post_id_str) as post:
            app.logger.debug("acquired write lock %s", post)

            # populate the Post object and save it to the database,
            # redirect to the view
            post.title = request.form.get('title', '')
            post.content = request.form.get('content')

            post.draft = request.form.get('draft', 'false') == 'true'
            post.hidden = request.form.get('hidden', 'false') == 'true'

            lat = request.form.get('latitude')
            lon = request.form.get('longitude')
            if lat and lon:
                post.location = Location(float(lat), float(lon),
                                         request.form.get('location_name'))
            else:
                post.location = None

            if not post.pub_date:
                post.pub_date = datetime.datetime.utcnow()

            slug = request.form.get('slug')
            if slug:
                post.slug = slug
            elif post.title and not post.slug:
                post.slug = slugify(post.title)

            post.repost_preview = None

            in_reply_to = request.form.get('in_reply_to')
            if in_reply_to:
                post.in_reply_to = [url.strip() for url
                                    in in_reply_to.split('\n')]

            repost_source = request.form.get('repost_source')
            if repost_source:
                post.repost_of = [url.strip() for url
                                  in repost_source.split('\n')]

            like_of = request.form.get('like_of')
            if like_of:
                post.like_of = [url.strip() for url
                                in like_of.split('\n')]

            twitter_status_id = request.form.get("twitter_status_id")
            if twitter_status_id:
                post.twitter_status_id = twitter_status_id

            facebook_post_id = request.form.get("facebook_post_id")
            if facebook_post_id:
                post.facebook_post_id = facebook_post_id

            app.logger.debug("attempting to save post %s", post)

            post.save()

            app.logger.debug("saved post %s %s", post.shortid, post.permalink)
            redirect_url = post.permalink

            contexts.fetch_post_contexts(post)
            if request.form.get('send_push') == 'true':
                push.send_notifications(post)

            if request.form.get('send_webmentions') == 'true':
                webmention_sender.send_webmentions(post)

        return redirect(redirect_url)

    except Exception as e:
        app.logger.exception("Failed to save post")
        flash('failed to save post {}'.format(e))

        return redirect(url_for('index'))


@app.route('/api/mf2')
def convert_mf2():
    from mf2py.parser import Parser
    url = request.args.get('url')
    p = Parser(url=url)
    json = p.to_dict()
    return jsonify(json)


def slugify(s):
    slug = unicodedata.normalize('NFKD', s).lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    slug = re.sub(r'[-]+', '-', slug)
    return slug[:256]


@app.route('/test/encoding')
def test_encoding():
    return make_response("<html><head></head><body>Tantek Çelik 😼 </body></html>",
                         200,
                         { 'Content-Type': 'text/html; charset=UTF-8' })
