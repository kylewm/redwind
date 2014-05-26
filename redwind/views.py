from . import app
from . import api
from . import archiver
from . import auth
from . import contexts
from . import facebook
from . import push
from . import twitter
from . import util
from . import webmention_sender
from . import webmention_receiver
from .models import Post, Location, Metadata, AddressBook, POST_TYPES

from bs4 import BeautifulSoup
from flask import request, redirect, url_for, render_template, flash,\
    abort, make_response, Markup, send_from_directory
from flask.ext.login import login_required, login_user, logout_user,\
    current_user
from contextlib import contextmanager
from urllib.parse import urlparse, urljoin
from werkzeug.routing import BaseConverter

import bleach
import datetime
import mf2util
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

TWITTER_PROFILE_RE = re.compile(r'https?://(?:www\.)?twitter\.com/(\w+)')
TWITTER_RE = twitter.TwitterClient.PERMALINK_RE
FACEBOOK_PROFILE_RE = re.compile(r'https?://(?:www\.)?facebook\.com/(\w+)')
FACEBOOK_RE = re.compile(r'https?://(?:www\.)?facebook\.com/(\w+)/posts/(\w+)')
YOUTUBE_RE = re.compile(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)')
INSTAGRAM_RE = re.compile(r'https?://instagram\.com/p/(\w+)')


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

    def __init__(self, wrapped):
        self.wrapped = wrapped
        self._mentions = None

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    def repost_preview_filter(self, url):
        # youtube embeds
        m = YOUTUBE_RE.match(url)
        if m:
            preview = """<iframe width="560" height="315" """\
                """src="//www.youtube.com/embed/{}" frameborder="0" """\
                """allowfullscreen></iframe>"""\
                .format(m.group(1))
            return preview, False

        # instagram embeds
        m = INSTAGRAM_RE.match(url)
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
    def tweet_id(self):
        for url in self.syndication:
            match = TWITTER_RE.match(url)
            if match:
                return match.group(2)

    @property
    @reraise_attribute_errors
    def reply_contexts(self):
        if not self.in_reply_to:
            return []
        return [ContextProxy(url) for url in self.in_reply_to]

    @property
    @reraise_attribute_errors
    def share_contexts(self):
        if not self.repost_of:
            return []
        return [ContextProxy(url) for url in self.repost_of]

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
        text = markdown_filter(self.content, img_path=self.get_image_path())
        if include_preview and self.post_type == 'share':
            preview = self.get_share_preview()
            text += preview
        return text

    @property
    @reraise_attribute_errors
    def html_excerpt(self):
        text = markdown_filter(self.content, img_path=self.get_image_path())
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
        self.url = url
        self.permalink = url
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.pub_date = None
        self.title = None
        self.deleted = False

        blob = archiver.load_json_from_archive(url)
        if not blob:
            return

        try:
            self.entry = mf2util.interpret(blob, url)
        except:
            app.logger.exception('error interpreting {}', url)
            return

        if not self.entry:
            return

        self.permalink = self.entry.get('url')
        self.author_name = self.entry.get('author', {}).get('name', '')
        self.author_url = self.entry.get('author', {}).get('url', '')
        self.author_image = self.entry.get('author', {}).get('photo', '')
        self.content = self.entry.get('content', '')
        self.pub_date = self.entry.get('published')
        self.title = self.entry.get('name')
        self.deleted = False


class MentionProxy:
    def __init__(self, post, url):
        self.permalink = url
        self.target = None
        self.reftype = 'reference'
        self.author_name = None
        self.author_url = None
        self.author_image = None
        self.content = None
        self.pub_date = None
        self.title = None
        self.deleted = False

        blob = archiver.load_json_from_archive(url)
        if not blob:
            return

        if post:
            target_urls = [
                post.permalink,
                post.permalink_without_slug,
                post.short_permalink,
                # for localhost testing
                post.permalink.replace(app.config['SITE_URL'], 'http://kylewm.com')
            ]
        else:
            target_urls = []

        try:
            self.entry = mf2util.interpret_comment(blob, url, target_urls)
        except:
            app.logger.exception('error interpreting {}', url)
            return

        if not self.entry:
            return

        self.permalink = self.entry.get('url', '')
        self.author_name = self.entry.get('author', {}).get('name', '')
        self.author_url = self.entry.get('author', {}).get('url', '')
        self.author_image = self.entry.get('author', {}).get('photo', '')
        self.content = self.entry.get('content', '')
        self.pub_date = self.entry.get('published')
        self.title = self.entry.get('name')

        comment_type = self.entry.get('comment_type')
        self.reftype = comment_type and comment_type[0]

    def __repr__(self):
        return """Mention(permalink={}, pub_date={} reftype={})""".format(
            self.permalink, self.pub_date, self.reftype)


def render_posts(title, post_types, page, per_page, tag=None,
                 include_hidden=False, include_drafts=False):
    mdata = Metadata()
    posts = mdata.load_posts(reverse=True, post_types=post_types, tag=tag,
                             include_hidden=include_hidden,
                             include_drafts=include_drafts,
                             page=page, per_page=per_page)

    dposts = [DisplayPost(post) for post in posts if check_audience(post)]
    return render_template('posts.html', posts=dposts, title=title,
                           prev_page=page-1,
                           next_page=page+1)


@app.context_processor
def inject_user_authenticated():
    twitterbot = 'Twitterbot' in request.headers.get('User-Agent', '')
    return {
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


@app.route('/tag/<tag>', defaults={'page': 1})
@app.route('/tag/<tag>/page/<int:page>')
def posts_by_tag(tag, page):
    return render_posts('All posts tagged ' + tag, POST_TYPES, page, 30, tag=tag,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


def render_posts_atom(title, feed_id, post_types, count):
    mdata = Metadata()
    posts = mdata.load_posts(reverse=True, post_types=post_types,
                             page=1, per_page=10)
    dposts = [DisplayPost(post) for post in posts if check_audience(post)]
    return make_response(render_template('posts.atom', title=title,
                                         feed_id=feed_id,
                                         posts=dposts), 200,
                         {'Content-Type': 'application/atom+xml; charset=utf-8'})


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
    mdata = Metadata()
    mentions = mdata.get_recent_mentions()
    proxies = []
    for mention in mentions:
        post_path = mention.get('post')
        post = Post.load(post_path) if post_path else None
        mention_url = mention.get('mention')
        proxies.append(MentionProxy(post, mention_url))
    return make_response(render_template('mentions.atom',
                                         title='kylewm.com: Mentions',
                                         feed_id='mentions.atom',
                                         mentions=proxies), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route('/archive', defaults={'year': None, 'month': None})
@app.route('/archive/<int:year>/<int(fixed_digits=2):month>')
def archive(year, month):
    # give the template the posts from this month,
    # and the list of all years/month
    posts = []
    if year and month:
        posts = [DisplayPost(post) for post
                 in Metadata().load_by_month(year, month)
                 if check_audience(post)]

    years = Metadata().get_archive_months()
    return render_template(
        'archive.html', years=years,
        expanded_year=year, expanded_month=month,
        posts=posts)


def check_audience(post):
    if not post.audience:
        # all posts public by default
        return True

    if current_user.is_authenticated():
        # admin user can see everything
        return True

    if current_user.is_anonymous():
        # anonymous users can't see stuff
        return False

    # check that their username is listed in the post's audience
    app.logger.debug('checking that logged in user %s is in post audience %s',
                     current_user.get_id(), post.audience)
    return current_user.get_id() in post.audience


@app.route('/{}/{}/files/<filename>'.format(POST_TYPE_RULE, DATE_RULE))
def post_associated_file(post_type, year, month, day, index, filename):
    post = Post.load_by_date(post_type, year, month, day, index)
    if not post:
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not check_audience(post):
        abort(401)  # not authorized TODO a nicer page

    resourcedir = os.path.join(app.root_path, '_data', post.path, 'files')

    size = request.args.get('size')
    if size == 'small':
        resourcedir, filename = util.resize_image(resourcedir, filename, 300)
    elif size == 'medium':
        resourcedir, filename = util.resize_image(resourcedir, filename, 800)
    elif size == 'large':
        resourcedir, filename = util.resize_image(resourcedir, filename, 1024)

    _, ext = os.path.splitext(filename)
    return send_from_directory(resourcedir, filename,
                               mimetype='text/plain' if ext == '.md' else None)


@app.route('/' + POST_TYPE_RULE + '/' + DATE_RULE, defaults={'slug': None})
@app.route('/' + POST_TYPE_RULE + '/' + DATE_RULE + '/<slug>')
def post_by_date(post_type, year, month, day, index, slug):
    post = Post.load_by_date(post_type, year, month, day, index)
    if not post or (post.draft and not current_user.is_authenticated()):
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not check_audience(post):
        abort(401)  # not authorized TODO a nicer page

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


# for testing -- allows arbitrary logins as any user
# @app.route('/fakeauth')
# def fakeauth():
#     domain = request.args.get('url')
#     user = auth.load_user(domain)
#     login_user(user, remember=True)
#     return redirect(url_for('index'))


@app.route("/indieauth")
def indieauth():
    token = request.args.get('token')
    response = requests.get('http://indieauth.com/verify',
                            params={'token': token})

    if response.status_code == 200:
        domain = response.json().get('me')
        user = auth.load_user(domain)
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

    with Metadata.writeable() as mdata:
        mdata.add_or_update_post(post)
        mdata.save()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


@app.route('/admin/new')
def new_post():
    post_type = request.args.get('type', 'note')
    post = Post(post_type)
    post.content = ''

    if post_type == 'reply':
        in_reply_to = request.args.get('in_reply_to')
        if in_reply_to:
            post.in_reply_to = [in_reply_to]

    if post_type == 'share':
        repost_of = request.args.get('repost_of')
        if repost_of:
            post.repost_of = [repost_of]

    if post_type == 'like':
        post.hidden = True
        like_of = request.args.get('like_of')
        if like_of:
            post.like_of = [like_of]

    content = request.args.get('content')
    if content:
        post.content = content

    return render_template('edit_post.html', edit_type='new', post=post,
                           advanced=request.args.get('advanced'))


@app.route('/admin/edit')
def edit_by_id():
    shortid = request.args.get('id')
    post = Post.load_by_shortid(shortid)

    if not post:
        abort(404)
    return render_template('edit_post.html', edit_type='edit', post=post,
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

    if isinstance(thedate, datetime.datetime):
        now = datetime.datetime.utcnow()
    else:
        now = datetime.date.today()

    # if the date being formatted has a timezone, make
    # sure utc now does too
    if hasattr(now, 'tzinfo') and hasattr(thedate, 'tzinfo') \
       and thedate.tzinfo:
        now = pytz.utc.localize(now)

    delta = now - thedate

    if delta.days < 1:
        # resolve seconds into hours/minutes
        minutes = delta.seconds // 60
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return "{} minute{} ago".format(minutes, pluralize(minutes))
        else:
            hours = round(minutes/60)
            return "about {} hour{} ago".format(hours, pluralize(hours))

    if delta.days == 1:
        return "yesterday"

    if delta.days < 30:
        return "{} days ago".format(delta.days)

    if delta.days < 365:
        months = round(delta.days / 30)
        return "about {} month{} ago".format(months, pluralize(months))

    years = round(delta.days / 365)
    return "{} year{} ago".format(years, pluralize(years))


@app.template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    if number == 1:
        return singular
    else:
        return plural


@app.template_filter('month_shortname')
def month_shortname(month):
    return datetime.date(1990, month, 1).strftime('%b')


@app.template_filter('month_name')
def month_name(month):
    return datetime.date(1990, month, 1).strftime('%B')


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

app.jinja_env.globals['url_for_other_page'] = url_for_other_page


@app.template_filter('html_to_plain')
def html_to_plain(content):
    soup = BeautifulSoup(content)
    text = soup.get_text()
    return Markup.escape(text)


@app.template_filter('atom_sanitize')
def atom_sanitize(content):
    return Markup.escape(str(content))


@app.template_filter('bleach')
def bleach_html(html):
    return bleach.clean(html, strip=True)


def person_to_microcard(fullname, displayname, entry, pos):
    url = entry.get('url')
    photo = entry.get('photo')
    if url and photo:
        return '<a class="microcard h-card" href="{}">'\
            '<img src="{}" />{}</a>'.format(url, photo, displayname)
    return displayname


def process_people(data, person_processor):
    # substitute from address book
    book = process_people._book
    if not book:
        book = AddressBook()
        process_people._book = book

    regex = re.compile(r"\[\[([\w ]+)(?:\|([\w\-'. ]+))?\]\]")
    start = 0
    while True:
        print(repr(data))
        m = regex.search(data, start)
        if not m:
            break
        fullname = m.group(1)
        displayname = m.group(2) or fullname
        replacement = person_processor(fullname, displayname,
                                       book.entries.get(fullname, {}),
                                       m.start())
        data = data[:m.start()] + replacement + data[m.end():]
        start = m.start() + len(replacement)
    return data

process_people._book = None


@app.template_filter('markdown')
def markdown_filter(data, img_path=None, link_twitter_names=True,
                    person_processor=person_to_microcard):
    from markdown import markdown
    from smartypants import smartypants

    if img_path:
        # replace relative paths to images with absolute
        data = re.sub(
            '(?<!\\\)!\[([^\]]*)\]\(([^/)]+)\)',
            '![\g<1>](' + img_path + '/\g<2>)', data)

    if person_processor:
        data = process_people(data, person_processor)

    result = markdown(data, extensions=['codehilite', 'fenced_code'])
    result = util.autolink(result, twitter_names=link_twitter_names)
    result = smartypants(result)
    return result


@app.template_filter('format_markdown_as_text')
def format_markdown_as_text(
        content, remove_imgs=True,
        link_twitter_names=True,
        person_processor=lambda full, display, entry, pos: display):
    html = markdown_filter(content, link_twitter_names=link_twitter_names,
                           person_processor=person_processor)
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


@app.template_filter('autolink')
def autolink(plain, twitter_names=True):
    return util.autolink(plain, twitter_names)


@app.template_filter('prettify_url')
def prettify_url(url):
    split = url.split('//', 1)
    if len(split) == 2:
        schema, path = split
    else:
        path = url
    return path.strip('/')


@app.template_filter('format_syndication_url')
def format_syndication_url(url):
    if TWITTER_RE.match(url):
        return """<i class="fa fa-twitter"></i> Twitter"""
    if FACEBOOK_RE.match(url):
        return """<i class="fa fa-facebook"></i> Facebook"""
    if INSTAGRAM_RE.match(url):
        return """<i class="fa fa-instagram"></i> Instagram"""
    return prettify_url(url)


@app.template_filter('local_mirror')
def local_mirror_resource(url):
    site_netloc = urlparse(app.config['SITE_URL']).netloc

    o = urlparse(url)
    if o.netloc and o.netloc != site_netloc:
        mirror_url_path = os.path.join("_mirror", o.netloc, o.path.strip('/'))
        mirror_file_path = os.path.join(app.root_path, 'static',
                                        mirror_url_path)
        #app.logger.debug("checking for existence of mirrored resource %s -> %s",
        #                 url, mirror_file_path)
        if os.path.exists(mirror_file_path):
            #app.logger.debug("%s already mirrored, returning url path %s",
            #                 mirror_file_path, mirror_url_path)
            return url_for('static', filename=mirror_url_path)

        if util.download_resource(url, mirror_file_path):
            app.logger.debug("%s did not exist, successfully mirrored to %s.",
                             mirror_file_path, mirror_url_path)
            return url_for('static', filename=mirror_url_path)
        else:
            app.logger.warn("failed to download %s to %s for some reason", url,
                            mirror_file_path)

    return url


@app.route('/admin/save_edit', methods=['POST'])
@login_required
def save_edit():
    shortid = request.form.get('post_id')
    app.logger.debug("saving post %s", shortid)
    with Post.writeable(Post.shortid_to_path(shortid)) as post:
        return save_post(post)


@app.route('/admin/save_new', methods=['POST'])
@login_required
def save_new():
    post_type = request.form.get('post_type', 'note')
    app.logger.debug("saving new post of type %s", post_type)
    post = Post(post_type)
    try:
        post._writeable = True
        return save_post(post)
    finally:
        post._writeable = False


def save_post(post):
    def slugify(s):
        slug = unicodedata.normalize('NFKD', s).lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
        slug = re.sub(r'[-]+', '-', slug)
        return slug[:256]

    try:
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
        post.reserve_date_index()

        slug = request.form.get('slug')
        if slug:
            post.slug = slug
        elif post.title and not post.slug:
            post.slug = slugify(post.title)

        post.repost_preview = None

        in_reply_to = request.form.get('in_reply_to', '')
        post.in_reply_to = [url.strip() for url
                            in in_reply_to.split('\n')
                            if url.strip()]

        repost_of = request.form.get('repost_of', '')
        post.repost_of = [url.strip() for url
                          in repost_of.split('\n')
                          if url.strip()]

        like_of = request.form.get('like_of', '')
        post.like_of = [url.strip() for url
                        in like_of.split('\n')
                        if url.strip()]

        syndication = request.form.get('syndication', '')
        post.syndication = [url.strip() for url in
                            syndication.split('\n')
                            if url.strip()]

        audience = request.form.get('audience', '')
        post.audience = [url.strip() for url in
                         audience.split('\n')
                         if url.strip()]

        post.tags = request.form.get('tags', '').split()

        file_to_url = {}
        infiles = request.files.getlist('files')
        app.logger.debug('infiles: %s', infiles)
        for infile in infiles:
            if infile and infile.filename:
                app.logger.debug('receiving uploaded file %s', infile)
                relpath, photo_url, fullpath \
                    = api.generate_upload_path(post, infile)
                if not os.path.exists(os.path.dirname(fullpath)):
                    os.makedirs(os.path.dirname(fullpath))
                infile.save(fullpath)
                file_to_url[infile] = photo_url

        app.logger.debug('uploaded files map %s', file_to_url)

        post.save()

        with Metadata.writeable() as mdata:
            mdata.add_or_update_post(post)
            mdata.save()

        app.logger.debug("saved post %s %s", post.shortid, post.permalink)
        redirect_url = post.permalink

        contexts.fetch_post_contexts(post)
        if request.form.get('send_push') == 'true' and not post.draft:
            push.send_notifications(post)

        if request.form.get('send_webmentions') == 'true' and not post.draft:
            webmention_sender.send_webmentions(post)

        return redirect(redirect_url)

    except Exception as e:
        app.logger.exception("Failed to save post")
        flash('failed to save post {}'.format(e))

        return redirect(url_for('index'))


@app.route('/admin/addressbook', methods=['GET', 'POST'])
@login_required
def addressbook():
    book = AddressBook()

    if request.method == 'POST':
        person = request.form.get('person').strip()
        url = request.form.get('url').strip()
        photo = request.form.get('photo').strip()
        twitter_name = request.form.get('twitter').strip()
        facebook_id = request.form.get('facebook').strip()

        book.entries[person] = {
            'url': url,
            'photo': photo,
            'twitter': twitter_name,
            'facebook': facebook_id,
        }

        book.save()
        return redirect(url_for('addressbook'))

    return render_template('addressbook.html', entries=book.entries)
