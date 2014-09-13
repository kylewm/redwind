from . import api
from . import app
from . import auth
from . import db
from . import hooks
from . import util
from . import contexts

from .models import Post, Location, Metadata, AddressBook, Mention,\
    Context, Photo, POST_TYPES

from flask import request, redirect, url_for, render_template, flash,\
    abort, make_response, Markup, send_from_directory
from flask.ext.login import login_required, login_user, logout_user,\
    current_user
from sqlalchemy.orm import subqueryload

import urllib.parse
import jinja2.filters

import bleach
import collections
import datetime
import itertools
import operator
import os
import pytz
import requests


bleach.ALLOWED_TAGS += ['img', 'p', 'br']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})

TIMEZONE = pytz.timezone('US/Pacific')

POST_TYPE_RULE = '<any({}):post_type>'.format(','.join(POST_TYPES))
DATE_RULE = ('<int:year>/<int(fixed_digits=2):month>/<int(fixed_digits=2):day>/<index>')

AUTHOR_PLACEHOLDER = 'img/users/placeholder.png'


def render_posts(title, post_types, page, per_page, tag=None,
                 include_hidden=False, include_drafts=False):

    query = Post.query
    query = query.options(subqueryload(Post.mentions),
                          subqueryload(Post.photos),
                          subqueryload(Post.location),
                          subqueryload(Post.reply_contexts),
                          subqueryload(Post.repost_contexts),
                          subqueryload(Post.like_contexts),
                          subqueryload(Post.bookmark_contexts))

    if not include_hidden:
        query = query.filter_by(hidden=False)
    if not include_drafts:
        query = query.filter_by(draft=False)
    query = query.order_by(Post.published.desc())
    pagination = query.paginate(page=page, per_page=per_page)
    posts = pagination.items
    is_first = not pagination.has_prev
    is_last = not pagination.has_next

    if not posts:
        abort(404)

    posts = [post for post in posts if check_audience(post)]
    return render_template('posts.html', posts=posts, title=title,
                           prev_page=None if is_first else page-1,
                           next_page=None if is_last else page+1,
                           body_class='h-feed', article_class='h-entry')


@app.route('/', defaults={'page': 1})
@app.route('/page/<int:page>')
def index(page):
    # leave out hidden posts
    return render_posts(None, POST_TYPES, page, 15,
                        include_hidden=False,
                        include_drafts=current_user.is_authenticated())


@app.route('/articles', defaults={'page': 1})
@app.route('/articles/page/<int:page>')
def articles(page):
    return render_posts('All Articles', ('article',), page, 10,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


@app.route('/checkins', defaults={'page': 1})
@app.route('/checkins/page/<int:page>')
def checkins(page):
    return render_posts('All Check-ins', ('checkin',), page, 10,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


@app.route('/bookmarks', defaults={'page': 1})
@app.route('/bookmarks/page/<int:page>')
def bookmarks(page):
    return render_posts('All Bookmarks', ('bookmark',), page, 10,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


@app.route('/photos', defaults={'page': 1})
@app.route('/photos/page/<int:page>')
def photos(page):
    return render_posts('All Photos', ('photo',), page, 10,
                        include_hidden=True,
                        include_drafts=current_user.is_authenticated())


@app.route('/likes', defaults={'page': 1})
@app.route('/likes/page/<int:page>')
def likes(page):
    return render_posts('All Likes', ('like',), page, 30,
                        include_hidden=True,
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
    return render_posts('All posts tagged ' + tag, POST_TYPES, page, 30,
                        tag=tag, include_hidden=True,
                        include_drafts=current_user.is_authenticated())


def render_posts_atom(title, feed_id, post_types, count):
    mdata = Metadata()
    posts, _, _ = mdata.load_posts(reverse=True, post_types=post_types,
                                   page=1, per_page=10)
    posts = [post for post in posts if check_audience(post)]
    return make_response(
        render_template('posts.atom', title=title, feed_id=feed_id,
                        posts=posts),
        200, {'Content-Type': 'application/atom+xml; charset=utf-8'})


@app.route("/all.atom")
def all_atom():
    return render_posts_atom('All', 'all.atom', None, 5)


@app.route("/updates.atom")
def updates_atom():
    return render_posts_atom('Updates', 'updates.atom',
                             ('article', 'note', 'share'), 5)


@app.route("/articles.atom")
def articles_atom():
    return render_posts_atom('Articles', 'articles.atom', ('article',), 5)


# @app.route("/mentions.atom")
# def mentions_atom():
#     mdata = Metadata()
#     mentions = mdata.get_recent_mentions()
#     proxies = []
#     for mention in mentions:
#         post_path = mention.get('post')
#         post = Post.load(post_path) if post_path else None
#         mention_url = mention.get('mention')
#         proxies.append(create_dmention(post, mention_url))
#     return make_response(render_template('mentions.atom',
#                                          title='kylewm.com: Mentions',
#                                          feed_id='mentions.atom',
#                                          mentions=proxies), 200,
#                          {'Content-Type': 'application/atom+xml'})


@app.route('/archive', defaults={'year': None, 'month': None})
@app.route('/archive/<int:year>/<int(fixed_digits=2):month>')
def archive(year, month):
    # give the template the posts from this month,
    # and the list of all years/month
    posts = []
    if year and month:
        posts = [post for post
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


def get_top_tags(n=10):
    """
    Determine top-n tags based on a combination of frequency and receny.
    ref: https://developer.mozilla.org/en-US/docs/Mozilla/Tech/Places/Frecency_algorithm
    """
    rank = collections.defaultdict(int)
    now = datetime.datetime.utcnow()
    mdata = Metadata()
    for post in mdata.get_post_blobs():
        published = util.isoparse(post.get('published'))
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
        for tag in post.get('tags', []):
            rank[tag] += weight

    ordered = sorted(list(rank.items()), key=operator.itemgetter(1),
                     reverse=True)
    return [key for key, _ in ordered[:n]]


@app.route('/new/<type>')
@app.route('/new', defaults={'type': 'note'})
def new_post(type):
    post = Post(type)
    post.published = datetime.datetime.utcnow()
    post._content = ''

    if type == 'reply':
        in_reply_to = request.args.get('url')
        if in_reply_to:
            post.in_reply_to = [in_reply_to]

    if type == 'share':
        repost_of = request.args.get('url')
        if repost_of:
            post.repost_of = [repost_of]

    if type == 'like':
        like_of = request.args.get('url')
        if like_of:
            post.like_of = [like_of]

    if type == 'bookmark':
        bookmark_of = request.args.get('url')
        if bookmark_of:
            post.bookmark_of = [bookmark_of]

    context_urls = itertools.chain(post.in_reply_to, post.repost_of,
                                   post.like_of, post.bookmark_of)
    post._contexts = {
        url: contexts.create_context(post.path, url)
        for url in context_urls
    }

    content = request.args.get('content')
    if content:
        post._content = content

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
    with Post.writeable(Post.shortid_to_path(shortid)) as post:
        return save_post(post)


@app.route('/save_new', methods=['POST'])
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
    try:
        app.logger.debug("acquired write lock %s", post)

        # populate the Post object and save it to the database,
        # redirect to the view
        post.title = request.form.get('title', '')
        post.content = post._content = request.form.get('content')

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

        if not post.published:
            post.published = datetime.datetime.utcnow()
        post.reserve_date_index()

        slug = request.form.get('slug')
        if slug:
            post.slug = util.slugify(slug)
        elif not post.slug:
            if post.title:
                post.slug = util.slugify(post.title)
            elif post.content:
                post.slug = util.slugify(post.content, 32)

        in_reply_to = request.form.get('in_reply_to')
        if in_reply_to is not None:
            post.in_reply_to = util.multiline_string_to_list(in_reply_to)

        repost_of = request.form.get('repost_of')
        if repost_of is not None:
            post.repost_of = util.multiline_string_to_list(repost_of)

        like_of = request.form.get('like_of')
        if like_of is not None:
            post.like_of = util.multiline_string_to_list(like_of)

        bookmark_of = request.form.get('bookmark_of')
        if bookmark_of is not None:
            post.bookmark_of = util.multiline_string_to_list(bookmark_of)

        syndication = request.form.get('syndication')
        if syndication is not None:
            post.syndication = util.multiline_string_to_list(syndication)

        audience = request.form.get('audience')
        if audience is not None:
            post.audience = util.multiline_string_to_list(audience)

        tags = request.form.get('tags', '').split(',')
        post.tags = list(filter(None, map(util.normalize_tag, tags)))

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

        post.save()
        if not post.id:
            db.session.add(post)
        db.session.commit()

        with Metadata.writeable() as mdata:
            mdata.add_or_update_post(post)
            mdata.save()

        app.logger.debug("saved post %s %s", post.shortid, post.permalink)
        redirect_url = post.permalink

        contexts.fetch_contexts(post)
        hooks.fire('post-saved', post, request.form)

        return redirect(redirect_url)

    except Exception as e:
        app.logger.exception("Failed to save post")
        flash('failed to save post {}'.format(e))

        return redirect(url_for('index'))


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
