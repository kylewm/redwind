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


from app import app
from models import Post, Mention, Context
from auth import load_user

from bs4 import BeautifulSoup, Comment
from datetime import datetime
from flask import request, redirect, url_for, render_template, flash,\
    abort, make_response, jsonify, Markup
from flask.ext.login import login_required, login_user, logout_user,\
    current_user

from werkzeug import secure_filename
from util import autolinker
from util import hentry_parser

import bleach
import os
import pytz
import re
import requests
import unicodedata

bleach.ALLOWED_TAGS += ['img']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})

TIMEZONE = pytz.timezone('US/Pacific')

POST_TYPES = ['article', 'note', 'share', 'like', 'reply', 'checkin']
POST_TYPE_RULE = '<any(' + ','.join(POST_TYPES) + '):post_type>'

FETCH_EXTERNAL_POST_HOOK = []

DATADIR = "_data"


class DisplayPost:

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

    def repost_preview_filter(self, url):
        #youtube embeds
        m = re.match(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)', url)
        if m:
            preview = """<iframe width="560" height="315" """\
                """src="//www.youtube.com/embed/{}" frameborder="0" """\
                """allowfullscreen></iframe>"""\
                .format(m.group(1))
            return preview, False

        #instagram embeds
        m = re.match(r'https?://instagram\.com/p/(\w+)/?#?', url)
        if m:
            preview = """<iframe src="//instagram.com/p/{}/embed/" """\
                """width="400" height="500" frameborder="0" scrolling="no" """\
                """allowtransparency="true"></iframe>"""\
                .format(m.group(1))
            return preview, False

        #FIXME
        #preview = twitter_client.repost_preview(self.author, url)
        #if preview:
        #    return preview, True

        #fallback (this is included in the template now)
        #m = re.match(r'https?://(.*)', url)
        #if m:
        #    preview = """<a href="{}" class="u-repost u-repost-of">{}</a>"""\
        #        .format(url, m.group(1))
        #    return preview, False

        # TODO when the post is first created, we should fetch the
        # reposted URL and save some information about it (i.e.,
        # information we can't get from the page title, whether it is an
        # image, etc.)
        return None, False

    def get_share_preview(self):
        text = ''
        for share_context in self.share_contexts:
            preview, _ = self.repost_preview_filter(share_context.source)
            if preview:
                text += '<div>' + preview + '</div>'
        return text

    @property
    def html_content(self):
        return Markup(self.get_html_content(True))

    def get_html_content(self, include_preview=True):
        text = format_as_html(self.content, self.content_format)
        if include_preview and self.post_type == 'share':
            text += self.get_share_preview()
        return text

    @property
    def html_excerpt(self):
        text = format_as_html(self.content, self.content_format)
        split = text.split('<!-- more -->', 1)
        if self.post_type == 'share':
            text += self.get_share_preview(split[0])
        if len(split) > 1:
            text += "<br/><a href={}>Keep Reading...</a>"\
                . format(self.permalink)
        return Markup(text)

    @property
    def mentions_sorted_by_date(self):
        def by_date(m):
            return m.pub_date or\
                datetime.datetime(datetime.MIN_YEAR, 1, 1)
        return sorted(self.mentions, key=by_date)

    @property
    def likes(self):
        return [mention for mention in self.mentions_sorted_by_date
                if mention.mention_type == 'like']

    @property
    def non_likes(self):
        return [mention for mention in self.mentions_sorted_by_date
                if mention.mention_type != 'like']

    @property
    def reposts(self):
        return [mention for mention in self.mentions_sorted_by_date
                if mention.mention_type == 'repost']

    @property
    def replies(self):
        return [mention for mention in self.mentions_sorted_by_date
                if mention.mention_type == 'reply']

    @property
    def references(self):
        return [mention for mention in self.mentions_sorted_by_date
                if mention.mention_type == 'reference']


def render_posts(title, post_types, page, per_page, include_drafts=False):
    posts = [DisplayPost(post) for post in Post.load_recent(per_page)]
    return render_template('posts.html', posts=posts, title=title,
                           authenticated=current_user.is_authenticated())


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    # leave out replies and likes
    return render_posts(None, ('article', 'note', 'share'), page, 30,
                        include_drafts=current_user.is_authenticated())


@app.route('/articles', defaults={'page': 1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', ('article',), page, 10,
                        include_drafts=current_user.is_authenticated())


@app.route('/everything', defaults={'page': 1})
@app.route('/everything/page/<int:page>')
def everything(page):
    return render_posts('Everything', None, page, 30,
                        include_drafts=current_user.is_authenticated())


def render_posts_atom(title, feed_id, post_types, count):
    posts = [DisplayPost(post) for post in Post.load_recent(count)]
    return make_response(render_template('posts.atom', title=title,
                                         feed_id=feed_id,
                                         posts=posts), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route("/all.atom")
def all_atom():
    return render_posts_atom('All', 'all.atom', ('article', 'note', 'share', 'like', 'reply'), 30)


@app.route("/updates.atom")
def updates_atom():
    return render_posts_atom('Updates', 'updates.atom', ('article', 'note', 'share'), 30)


@app.route("/notes.atom")
def notes_atom():
    return render_posts_atom('Notes', 'notes.atom', ('note',), 30)


@app.route("/articles.atom")
def articles_atom():
    return render_posts_atom('Articles', 'articles.atom', ('article',), 10)


@app.route("/mentions.atom")
def mentions_atom():
    mentions = Mention\
        .query\
        .filter(Mention.post)\
        .order_by(Mention.pub_date.desc())\
        .limit(30).all()
    return make_response(render_template("mentions.atom",
                                         mentions=mentions), 200,
                         {'Content-Type': 'application/atom+xml'})


@app.route('/' + POST_TYPE_RULE + '/<int:year>/<int(fixed_digits=2):month>/<int(fixed_digits=2):day>/<int:index>', defaults={'slug': None})
@app.route('/' + POST_TYPE_RULE + '/<int:year>/<int(fixed_digits=2):month>/<int(fixed_digits=2):day>/<int:index>/<slug>')
def post_by_date(post_type, year, month, day, index, slug):
    post = Post.lookup_post_by_date(post_type, year, month, day, index)
    if not post:
        abort(410)

    if not slug and post.slug:
        return redirect(
            url_for('post_by_date', post_type=post_type,
                    year=year, month=month, day=day, index=index,
                    slug=post.slug))

    dpost = DisplayPost(post)
    #print("rendering post", post.short_cite, post.short_permalink)
    title = dpost.title
    if not title:
        title = "A {} from {}".format(dpost.post_type,
                                      dpost.pub_date.strftime('%Y-%m-%d'))

    return render_template('post.html', post=dpost, title=title,
                           authenticated=current_user.is_authenticated())


@app.route('/' + POST_TYPE_RULE + '/<string(length=6):yymmdd>/<int:index>')
def post_by_old_date(post_type, yymmdd, index):
    year = int('20' + yymmdd[0:2])
    month = int(yymmdd[2:4])
    day = int(yymmdd[4:6])
    return redirect(url_for('post_by_date', post_type=post_type,
                            year=year, month=month, day=day, index=index))


@app.route('/' + POST_TYPE_RULE + '/<int(max=2014):year>/<int:dbid>',
           defaults={'slug': None})
@app.route('/' + POST_TYPE_RULE + '/<int(max=2014):year>/<int:dbid>/<slug>')
def post_by_id(post_type, year, dbid, slug):
    post = Post.lookup_post_by_id(dbid)
    if not post:
        abort(404)
    return redirect(url_for('post_by_date', post_type=post.post_type,
                            year=post.pub_date.year, month=post.pub_date.month,
                            day=post.pub_date.day, index=post.date_index))


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
            flash('Logged in {} with domain {}'.format(user.login, domain))
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
    return render_template("settings.html", user=current_user,
                           authenticated=current_user.is_authenticated())


@app.route('/locations')
def locations():
    posts = Post.query.filter(Post.latitude != None,
                              Post.latitude != 0,
                              Post.longitude != None,
                              Post.longitude != 0).all()
    locations = [{
        'lat': post.latitude,
        'long': post.longitude,
        'name': post.location_name
    } for post in posts]

    return render_template("locations.html", locations=locations,
                           authenticated=current_user.is_authenticated())


@app.route('/admin/delete')
@login_required
def delete_by_id():
    post_id = request.args.get('id')
    post = Post.query.filter_by(id=post_id).first()

    if not post:
        abort(404)

    db.session.delete(post)
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


@app.route('/admin/delete_mention')
@login_required
def delete_mention_by_id():
    mention_id = request.args.get('id')
    mention = Mention.query.filter_by(id=mention_id).first()

    if not mention:
        abort(404)

    db.session.delete(mention)
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


@app.route('/admin/new')
@login_required
def new_post():
    post_type = request.args.get('type', 'note')
    content_format = 'markdown' if post_type == 'article' else 'plain'
    post = Post(post_type, content_format, current_user)
    post.content = ''

    if post_type == 'reply':
        in_reply_to = request.args.get('in_reply_to')
        if in_reply_to:
            post.in_reply_to = request.args.get('in_reply_to')

    if post_type == 'share':
        repost_source = request.args.get('repost_source')
        if repost_source:
            post.repost_source = repost_source

    if post_type == 'like':
        like_of = request.args.get('like_of')
        if like_of:
            post.like_of = like_of

    content = request.args.get('content')
    if content:
        post.content = content

    return render_template('edit_post.html', post=post,
                           advanced=request.args.get('advanced'),
                           authenticated=current_user.is_authenticated())


@app.route('/admin/edit')
@login_required
def edit_by_id():
    post_id = request.args.get('id')
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        abort(404)
    return render_template('edit_post.html', post=post,
                           advanced=request.args.get('advanced'),
                           authenticated=current_user.is_authenticated())


@app.route('/admin/uploads')
def uploads_popup():
    return render_template('uploads_popup.html')


@app.route('/admin/preview')
@login_required
def post_preview():
    post_id = request.args.get('id')
    post = Post.query.filter_by(id=post_id).first()
    return render_template('post_preview.html', post=DisplayPost(post))


@app.template_filter('strftime')
def strftime_filter(date, fmt='%Y %b %d'):
    if date:
        localdate = pytz.utc.localize(date).astimezone(TIMEZONE)
        return localdate.strftime(fmt)


@app.template_filter('isotime')
def isotime_filter(date):
    if date:
        utctime = pytz.utc.localize(date)
        return utctime.isoformat('T')


@app.template_filter('pluralize')
def pluralize(number, singular = '', plural = 's'):
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


@app.template_filter('get_first_image')
def get_first_image(content, content_format):
    """find the first image (if any) that is in an <img> tag
    in the rendered post"""
    html = format_as_html(content, content_format)
    soup = BeautifulSoup(html)
    img = soup.find('img')
    if img:
        return img.get('src')


@app.template_filter('format_as_html')
def format_as_html(content, content_format, linkify=True):
    if not content:
        html = ''
    elif content_format == 'markdown':
        html = markdown_filter(content)
    elif content_format == 'plain' and linkify:
        html = plain_text_filter(content)
    else:
        html = content
    return html


@app.template_filter('bleach')
def bleach_html(html):
    return bleach.clean(html, strip=True)


@app.template_filter('format_as_text')
def format_as_text(content, content_format):
    if not content:
        return ''
    html = format_as_html(content, content_format, linkify=False)
    soup = BeautifulSoup(html)

    # replace links with the URL
    for a in soup.find_all('a'):
        a.replace_with(a.get('href') or 'link')
    # and images with their alt text
    for i in soup.find_all('img'):
        i.replace_with(i.get('title') or i.get('alt') or 'image')

    return soup.get_text()


@app.template_filter('markdown')
def markdown_filter(data):
    from markdown import markdown
    from smartypants import smartypants
    return smartypants(
        markdown(data, extensions=['codehilite']))


@app.template_filter('autolink')
def plain_text_filter(plain):
    plain = autolinker.make_links(plain)
    plain = plain.replace('\n', '<br />')
    return plain


@app.template_filter('prettify_url')
def prettify_url(url):
    split = url.split('//', 1)
    if len(split) == 2:
        schema, path = split
    else:
        path = url
    return path.strip('/')


## API Methods


@app.route('/api/upload_file', methods=['POST'])
@login_required
def receive_upload():
    file = request.files['file']
    filename = secure_filename(file.filename)
    now = datetime.utcnow()
    directory = os.path.join('static', 'uploads',
                             str(now.year), str(now.month).zfill(2))
    path = os.path.join(directory, filename)
    if not os.path.exists(directory):
        os.makedirs(directory)
    file.save(path)
    return jsonify({'path': '/' + path})


# drafts can be saved or published
# published can be moved back to draft or re-published
# any time a post is 'published', it should send webmentions and
# push notifications.

@app.route('/api/save', methods=['POST'])
@login_required
def save_post():
    try:
        post_id_str = request.form.get('post_id')

        if post_id_str == 'new':
            post_type = request.form.get('post_type', 'note')
            post = Post(post_type, 'plain', current_user)
        else:
            post_id = int(post_id_str)
            post = Post.query.filter_by(id=post_id).first()

        # populate the Post object and save it to the database,
        # redirect to the view
        post.title = request.form.get('title', '')
        post.content = request.form.get('content')
        post.in_reply_to = request.form.get('in_reply_to', '')
        post.repost_source = request.form.get('repost_source', '')
        post.like_of = request.form.get('like_of', '')
        post.content_format = request.form.get('content_format', 'plain')
        post.draft = request.form.get('draft', 'true') == 'true'

        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        post.latitude = lat and float(lat)
        post.longitude = lon and float(lon)
        post.location_name = request.form.get('location_name')

        app.logger.debug("got draft setting from: %s",
                         request.form.get('draft'))

        if not post.pub_date:
            post.pub_date = datetime.utcnow()

        slug = request.form.get('slug')
        if slug:
            post.slug = slug
        elif post.title and not post.slug:
            post.slug = slugify(post.title)

        # generate the date/index identifier
        if not post.date_index:
            post.date_index = 1
            same_day_posts = Post.query\
                                 .filter(Post.post_type == post.post_type,
                                         sqlcast(Post.pub_date, db.Date)
                                         == post.pub_date.date())\
                                 .all()
            if same_day_posts:
                post.date_index += max(post.date_index for post
                                       in same_day_posts)

        post.repost_preview = None

        twitter_status_id = request.form.get("twitter_status_id")
        if twitter_status_id:
            post.twitter_status_id = twitter_status_id

        facebook_post_id = request.form.get("facebook_post_id")
        if facebook_post_id:
            post.facebook_post_id = facebook_post_id

        if not post.id:
            db.session.add(post)
        db.session.commit()
        return jsonify(success=True, id=post.id, permalink=post.permalink)

    except Exception as e:
        app.logger.exception("Failed to save post")
        return jsonify(success=False, error="exception while saving post {}"
                       .format(e))


@app.route('/api/fetch_contexts', methods=['POST'])
@login_required
def fetch_post_contexts():
    try:
        post_id_str = request.form.get('post_id')
        post_id = int(post_id_str)
        post = Post.query.filter_by(id=post_id).first()

        replies = request.form.get('in_reply_to', '').strip().splitlines()
        reposts = request.form.get('repost_source', '').strip().splitlines()
        likes = request.form.get('like_of', '').strip().splitlines()

        for reply_url in replies:
            replyctx = fetch_external_post(reply_url, ReplyContext)
            if replyctx:
                dupes = ReplyContext.query.filter(
                    ReplyContext.post == post,
                    ReplyContext.permalink == replyctx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)
                db.session.add(replyctx)
                post.reply_contexts.append(replyctx)

        for repost_url in reposts:
            sharectx = fetch_external_post(repost_url, ShareContext)
            if sharectx:
                dupes = ShareContext.query.filter(
                    ShareContext.post == post,
                    ShareContext.permalink == sharectx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)
                db.session.add(sharectx)
                post.share_contexts.append(sharectx)

        for like_url in likes:
            likectx = fetch_external_post(like_url, LikeContext)
            if likectx:
                dupes = LikeContext.query.filter(
                    LikeContext.post == post,
                    LikeContext.permalink == likectx.permalink)
                for dupe in dupes:
                    db.session.delete(dupe)

                db.session.add(likectx)
                post.like_contexts.append(likectx)

        db.session.commit()
        return jsonify({
            'success': True,
            'replies': replies,
            'shares': reposts,
            'likes': likes
        })

    except Exception as e:
        app.logger.exception("failure fetching contexts")
        return jsonify({
            'success': False,
            'error': "exception while fetching contexts {}".format(e)
        })


def fetch_external_post_function(func):
    """decorator that plugins can use to register fetch functions"""
    FETCH_EXTERNAL_POST_HOOK.append(func)
    return func


def fetch_external_post(source, ExtPostClass):
    for fetch_fn in FETCH_EXTERNAL_POST_HOOK:
        extpost = fetch_fn(current_user, source, ExtPostClass)
        if extpost:
            return extpost

    response = requests.get(source)
    if response.status_code // 2 == 100:
        hentry = hentry_parser.parse(response.text, source)
        if hentry:
            return ExtPostClass(
                source, hentry.permalink,
                hentry.title, hentry.content, 'html',
                hentry.author.name if hentry.author else '',
                hentry.author.url if hentry.author else '',
                hentry.author.photo if hentry.author else '',
                hentry.pub_date, response.text)

    # get as much as we can without microformats
    soup = BeautifulSoup(response.text)
    title_tag = soup.find('title')
    title = title_tag.text if title_tag else prettify_url(source)
    return ExtPostClass(source, source, title, None, 'plain', None, None, None)


@app.route('/api/mf2')
def convert_mf2():
    from util import mf2
    url = request.args.get('url')
    response = requests.get(url)
    json = mf2.parse(response.text, url)
    return jsonify(json)


def slugify(s):
    slug = unicodedata.normalize('NFKD', s).lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    slug = re.sub(r'[-]+', '-', slug)
    return slug[:256]
