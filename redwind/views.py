from . import api
from . import app
from . import auth
from . import contexts
from . import db
from . import hooks
from . import util
from .models import Post, Location, Context, AddressBook, Photo, Tag

from flask import request, redirect, url_for, render_template, flash,\
    abort, make_response, Markup, send_from_directory
from flask.ext.login import login_required, login_user, logout_user,\
    current_user
import sqlalchemy.orm
import sqlalchemy.sql

import bleach
import collections
import datetime
import jinja2.filters
import operator
import os
import pytz
import requests
import urllib.parse

bleach.ALLOWED_TAGS += ['img', 'p', 'br']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})

TIMEZONE = pytz.timezone('US/Pacific')

POST_TYPES = [
    ('article', 'articles', 'All Articles'),
    ('note', 'notes', 'All Notes'),
    ('like', 'likes', 'All Likes'),
    ('share', 'shares', 'All Shares'),
    ('reply', 'replies', 'All Replies'),
    ('checkin', 'checkins', 'All Check-ins'),
    ('photo', 'photos', 'All Photos'),
    ('bookmark', 'bookmarks', 'All Bookmarks'),
]

POST_TYPE_RULE = '<any({}):post_type>'.format(
    ','.join(tup[0] for tup in POST_TYPES))
DATE_RULE = ('<int:year>/<int(fixed_digits=2):month>/'
             '<int(fixed_digits=2):day>/<index>')

AUTHOR_PLACEHOLDER = 'img/users/placeholder.png'


def collect_posts(post_types, page, per_page, tag,
                  include_hidden=False, include_drafts=False):

    query = Post.query
    query = query.options(
        sqlalchemy.orm.subqueryload(Post.tags),
        sqlalchemy.orm.subqueryload(Post.mentions),
        sqlalchemy.orm.subqueryload(Post.photos),
        sqlalchemy.orm.subqueryload(Post.location),
        sqlalchemy.orm.subqueryload(Post.reply_contexts),
        sqlalchemy.orm.subqueryload(Post.repost_contexts),
        sqlalchemy.orm.subqueryload(Post.like_contexts),
        sqlalchemy.orm.subqueryload(Post.bookmark_contexts))
    if tag:
        query = query.filter(Post.tags.any(Tag.name==tag))
    if not include_hidden:
        query = query.filter_by(hidden=False)
    if not include_drafts:
        query = query.filter_by(draft=False)
    query = query.filter_by(deleted=False)
    if post_types:
        query = query.filter(Post.post_type.in_(post_types))
    query = query.order_by(Post.published.desc())
    pagination = query.paginate(page=page, per_page=per_page)
    posts = pagination.items
    is_first = not pagination.has_prev
    is_last = not pagination.has_next
    posts = [post for post in posts if check_audience(post)]
    return posts, is_first, is_last


def render_posts(title, posts, page, is_first, is_last):
    atom_args = request.view_args.copy()
    atom_args.update({'page': 1, 'feed': 'atom', '_external': True})
    atom_url = url_for(request.endpoint, **atom_args)
    atom_title = title or 'Stream'
    return render_template('posts.html', posts=posts, title=title,
                           prev_page=None if is_first else page-1,
                           next_page=None if is_last else page+1,
                           body_class='h-feed', article_class='h-entry',
                           atom_url=atom_url, atom_title=atom_title)


def render_posts_atom(title, feed_id, posts):
    return make_response(
        render_template('posts.atom', title=title, feed_id=feed_id,
                        posts=posts),
        200, {'Content-Type': 'application/atom+xml; charset=utf-8'})


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    # leave out hidden posts
    posts, is_first, is_last = collect_posts(
        None, page, app.config['POSTS_PER_PAGE'], None, include_hidden=False,
        include_drafts=current_user.is_authenticated())
    if request.args.get('feed') == 'atom':
        return render_posts_atom('Stream', 'index.atom', posts)
    return render_posts(None, posts, page, is_first, is_last)


@app.route('/everything', defaults={'page': 1})
@app.route('/everything/page/<int:page>')
def everything(page):
    posts, is_first, is_last = collect_posts(
        None, page, app.config['POSTS_PER_PAGE'], None, include_hidden=True,
        include_drafts=current_user.is_authenticated())

    if request.args.get('feed') == 'atom':
        return render_posts_atom('Everything', 'everything.atom', posts)
    return render_posts('Everything', posts, page, is_first, is_last)


# register view functions for each post type /notes, /photos, etc.
def create_posts_of_type_view_func(post_type, plural, title):
    def posts_of_type(page):
        posts, is_first, is_last = collect_posts(
            (post_type,), page, app.config['POSTS_PER_PAGE'], None,
            include_hidden=True,
            include_drafts=current_user.is_authenticated())

        if request.args.get('feed') == 'atom':
            return render_posts_atom(title, plural + '.atom', posts)
        return render_posts(title, posts, page, is_first, is_last)
    return posts_of_type

for post_type, plural, title in POST_TYPES:
    view_func = create_posts_of_type_view_func(post_type, plural, title)
    app.add_url_rule('/' + plural, plural, view_func, defaults={'page': 1})
    app.add_url_rule('/' + plural + '/page/<int:page>', plural, view_func)


@app.route('/tag/<tag>', defaults={'page': 1})
@app.route('/tag/<tag>/page/<int:page>')
def posts_by_tag(tag, page):
    posts, is_first, is_last = collect_posts(
        None, page, app.config['POSTS_PER_PAGE'], tag, include_hidden=True,
        include_drafts=current_user.is_authenticated())
    title = '#' + tag

    if request.args.get('feed') == 'atom':
        return render_posts_atom(title, 'tag-' + tag + '.atom', posts)
    return render_posts(title, posts, page, is_first, is_last)


@app.route("/all.atom")
def all_atom():
    return redirect(url_for('everything', feed='atom'))


@app.route("/updates.atom")
def updates_atom():
    return redirect(url_for('index', feed='atom'))


@app.route("/articles.atom")
def articles_atom():
    return redirect(url_for('articles', feed='atom'))


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


def resize_associated_image(post, sourcepath, side):
    targetdir = os.path.join('_resized', post.path, 'files', str(side))
    targetpath = os.path.join(targetdir, os.path.basename(sourcepath))
    util.resize_image(
        os.path.join(app.root_path, sourcepath),
        os.path.join(app.root_path, targetpath), side)
    return targetpath


@app.route('/{}/{}/files/<filename>'.format(POST_TYPE_RULE, DATE_RULE))
def post_associated_file(post_type, year, month, day, index, filename):
    post = Post.load_by_date(post_type, year, month, day, index)
    if not post:
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not check_audience(post):
        abort(401)  # not authorized TODO a nicer page

    sourcepath = os.path.join('_data', post.path, 'files', filename)

    size = request.args.get('size')
    if size == 'small':
        sourcepath = resize_associated_image(post, sourcepath, 300)
    elif size == 'medium':
        sourcepath = resize_associated_image(post, sourcepath, 800)
    elif size == 'large':
        sourcepath = resize_associated_image(post, sourcepath, 1024)

    if app.debug:
        _, ext = os.path.splitext(sourcepath)
        return send_from_directory(
            os.path.join(app.root_path, os.path.dirname(sourcepath)),
            os.path.basename(sourcepath), mimetype=None)

    resp = make_response('')
    resp.headers['X-Accel-Redirect'] = '/internal' + sourcepath
    del resp.headers['Content-Type']
    return resp


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

    if post.redirect:
        return redirect(post.redirect)

    if not slug and post.slug:
        return redirect(
            url_for('post_by_date', post_type=post_type,
                    year=year, month=month, day=day, index=index,
                    slug=post.slug))

    title = post.title
    if not title:
        title = jinja2.filters.do_truncate(
            util.format_as_text(post.content), 50)
    if not title:
        title = "A {} from {}".format(post.post_type, post.published)

    return render_template('post.html', post=post, title=title,
                           body_class='h-entry', article_class=None)


@app.route('/short/<string(minlength=5,maxlength=6):tag>')
def shortlink(tag):
    post_type = util.parse_type(tag)
    published = util.parse_date(tag)
    index = util.parse_index(tag)

    if not post_type or not published or not index:
        abort(404)

    return redirect(url_for('post_by_date', post_type=post_type,
                            year=published.year, month=published.month,
                            day=published.day, index=index))


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
    response = requests.get('https://indieauth.com/verify',
                            params={'token': token})

    if response.status_code == 200:
        domain = response.json().get('me')
        user = auth.load_user(urllib.parse.urlparse(domain).netloc)
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


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/settings')
@login_required
def settings():
    return render_template("settings.html", user=current_user)


@app.route('/delete')
@login_required
def delete_by_id():
    shortid = request.args.get('id')
    post = Post.load_by_shortid(shortid)
    if not post:
        abort(404)
    post.deleted = True
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('index')
    app.logger.debug("redirecting to {}".format(redirect_url))
    return redirect(redirect_url)


def get_top_tags(n=10):
    """
    Determine top-n tags based on a combination of frequency and receny.
    ref: https://developer.mozilla.org/en-US/docs/Mozilla/Tech/Places/Frecency_algorithm
    """
    rank = collections.defaultdict(int)
    now = datetime.datetime.utcnow()

    entries = Post.query.join(Post.tags).values(Post.published, Tag.name)
    for published, tag in entries:
        weight = 0
        if published:
            delta = now - published
            if delta < datetime.timedelta(days=4):
                weight = 1.0
            elif delta < datetime.timedelta(days=14):
                weight = 0.7
            elif delta < datetime.timedelta(days=31):
                weight = 0.5
            elif delta < datetime.timedelta(days=90):
                weight = 0.3
            elif delta < datetime.timedelta(days=730):
                weight = 0.1
        rank[tag] += weight

    ordered = sorted(list(rank.items()), key=operator.itemgetter(1),
                     reverse=True)
    return [key for key, _ in ordered[:n]]


@app.route('/new/<type>')
@app.route('/new', defaults={'type': 'note'})
def new_post(type):
    post = Post(type)
    post.published = datetime.datetime.utcnow()
    post.content = ''

    if type == 'reply':
        in_reply_to = request.args.get('url')
        if in_reply_to:
            post.in_reply_to = [in_reply_to]
            post.reply_contexts = [contexts.create_context(in_reply_to)]

    elif type == 'share':
        repost_of = request.args.get('url')
        if repost_of:
            post.repost_of = [repost_of]
            post.repost_contexts = [contexts.create_context(repost_of)]

    elif type == 'like':
        like_of = request.args.get('url')
        if like_of:
            post.like_of = [like_of]
            post.like_contexts = [contexts.create_context(like_of)]

    elif type == 'bookmark':
        bookmark_of = request.args.get('url')
        if bookmark_of:
            post.bookmark_of = [bookmark_of]
            post.bookmark_contexts = [contexts.create_context(bookmark_of)]

    post.content = request.args.get('content')
    return render_template('edit_' + type + '.html', edit_type='new',
                           post=post, top_tags=get_top_tags(20))


@app.route('/edit')
def edit_by_id():
    shortid = request.args.get('id')
    post = Post.load_by_shortid(shortid)
    if not post:
        abort(404)
    type = 'post'
    if not request.args.get('advanced') and post.post_type:
        type = post.post_type
    return render_template('edit_' + type + '.html', edit_type='edit',
                           post=post, top_tags=get_top_tags(20))


@app.route('/uploads')
def uploads_popup():
    return render_template('uploads_popup.html')


@app.template_filter('isotime')
def isotime_filter(thedate):
    if not thedate:
        thedate = datetime.date(1982, 11, 24)

    if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
        tz = pytz.timezone(app.config['TIMEZONE'])
        thedate = pytz.utc.localize(thedate).astimezone(tz)

    if isinstance(thedate, datetime.datetime):
        return thedate.isoformat('T')
    return thedate.isoformat()


@app.template_filter('human_time')
def human_time(thedate, alternate=None):
    if not thedate:
        return alternate

    if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
        tz = pytz.timezone(app.config['TIMEZONE'])
        thedate = pytz.utc.localize(thedate).astimezone(tz)

    #return thedate.strftime('%B %-d, %Y %-I:%M%P %Z')

    if (isinstance(thedate, datetime.datetime)
            and datetime.datetime.now(TIMEZONE) - thedate < datetime.timedelta(days=1)):
        return thedate.strftime('%B %-d, %Y %-I:%M%P %Z')
    else:
        return thedate.strftime('%B %-d, %Y')


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


@app.template_filter('atom_sanitize')
def atom_sanitize(content):
    return Markup.escape(str(content))


@app.template_filter('prettify_url')
def prettify_url(*args, **kwargs):
    return util.prettify_url(*args, **kwargs)


@app.template_filter('domain_from_url')
def domain_from_url(url):
    if not url:
        return url
    return urllib.parse.urlparse(url).netloc


@app.template_filter('format_syndication_url')
def format_syndication_url(url, include_rel=True):
    fmt = '<a class="u-syndication" '
    if include_rel:
        fmt += 'rel="syndication" '
    fmt += 'href="{}"><i class="fa {}"></i> {}</a>'

    if util.TWITTER_RE.match(url):
        return Markup(fmt.format(url, 'fa-twitter', 'Twitter'))
    if util.FACEBOOK_RE.match(url):
        return Markup(fmt.format(url, 'fa-facebook', 'Facebook'))
    if util.INSTAGRAM_RE.match(url):
        return Markup(fmt.format(url, 'fa-instagram', 'Instagram'))

    return Markup(fmt.format(url, 'fa-paper-plane', domain_from_url(url)))


@app.template_filter('mirror_image')
def mirror_image(src, side=None):
    return util.mirror_image(src, side)


@app.route('/save_edit', methods=['POST'])
@login_required
def save_edit():
    shortid = request.form.get('post_id')
    app.logger.debug("saving post %s", shortid)
    post = Post.load_by_shortid(shortid)
    return save_post(post)


@app.route('/save_new', methods=['POST'])
@login_required
def save_new():
    post_type = request.form.get('post_type', 'note')
    app.logger.debug("saving new post of type %s", post_type)
    post = Post(post_type)
    return save_post(post)


def save_post(post):
    if not post.published:
        post.published = datetime.datetime.utcnow()
    post.reserve_date_index()

    # populate the Post object and save it to the database,
    # redirect to the view
    post.title = request.form.get('title', '')
    post.content = request.form.get('content')
    post.content_html = util.markdown_filter(
        post.content, img_path=post.get_image_path())

    post.draft = request.form.get('draft', 'false') == 'true'
    post.hidden = request.form.get('hidden', 'false') == 'true'

    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    if lat and lon:
        post.location = Location(latitude=float(lat),
                                 longitude=float(lon),
                                 name=request.form.get('location_name'))
    else:
        post.location = None

    slug = request.form.get('slug')
    if slug:
        post.slug = util.slugify(slug)
    elif not post.slug:
        if post.title:
            post.slug = util.slugify(post.title)
        elif post.content:
            post.slug = util.slugify(post.content, 32)

    for url_attr, context_attr in (('in_reply_to', 'reply_contexts'),
                                   ('repost_of', 'repost_contexts'),
                                   ('like_of', 'like_contexts'),
                                   ('bookmark_of', 'bookmark_contexts')):
        url_str = request.form.get(url_attr)
        if url_str is not None:
            urls = util.multiline_string_to_list(url_str)
            setattr(post, url_attr, urls)
            setattr(post, context_attr, [Context(url=u, permalink=u)
                                         for u in urls])

    syndication = request.form.get('syndication')
    if syndication is not None:
        post.syndication = util.multiline_string_to_list(syndication)

    audience = request.form.get('audience')
    if audience is not None:
        post.audience = util.multiline_string_to_list(audience)

    tags = request.form.get('tags', '').split(',')
    tags = list(filter(None, map(util.normalize_tag, tags)))
    post.tags = [Tag(tag) for tag in tags]

    # TODO accept multiple photos and captions
    inphoto = request.files.get('photo')
    if inphoto and inphoto.filename:
        app.logger.debug('receiving uploaded file %s', inphoto)
        relpath, photo_url, fullpath \
            = api.generate_upload_path(post, inphoto)
        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))
        inphoto.save(fullpath)
        caption = request.form.get('caption')
        post.photos = [Photo(post,
                             filename=os.path.basename(relpath),
                             caption=caption)]

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

    if not post.id:
        db.session.add(post)
    db.session.commit()

    app.logger.debug("saved post %s %s", post.shortid, post.permalink)
    redirect_url = post.permalink

    contexts.fetch_contexts(post)
    hooks.fire('post-saved', post, request.form)

    return redirect(redirect_url)


@app.route('/addressbook', methods=['GET', 'POST'])
def addressbook():
    book = AddressBook()

    if request.method == 'POST':
        if not current_user.is_authenticated():
            return app.login_manager.unauthorized()

        name = request.form.get('name').strip()
        url = request.form.get('url').strip()
        photo = request.form.get('photo').strip()
        twitter_name = request.form.get('twitter').strip()
        facebook_id = request.form.get('facebook').strip()

        book.entries[name] = {
            'url': url,
            'photo': photo,
            'twitter': twitter_name,
            'facebook': facebook_id,
        }

        book.save()
        return redirect(url_for('addressbook'))

    od = collections.OrderedDict(sorted(book.entries.items()))
    return render_template('addressbook.html', entries=od)
