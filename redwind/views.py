from redwind import util
from redwind import imageproxy
from redwind.extensions import db
from redwind.models import (
    Post, Tag, Mention, get_settings,
)

from flask import (
    request, redirect, url_for, render_template, g, abort,
    make_response, Markup, send_from_directory, current_app,
    Blueprint,
)

import flask.ext.login as flask_login

import sqlalchemy.orm
import sqlalchemy.sql
import sqlalchemy
import datetime
import json
import os
import pytz
import re
import urllib.parse


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
    ('event', 'events', 'All Events'),
]

POST_TYPE_RULE = '<any({}):post_type>'.format(
    ','.join(tup[0] for tup in POST_TYPES))
PLURAL_TYPE_RULE = '<any({}):plural_type>'.format(
    ','.join(tup[1] for tup in POST_TYPES))
DATE_RULE = (
    '<int:year>/<int(fixed_digits=2):month>/<int(fixed_digits=2):day>/<index>')
BEFORE_TS_FORMAT = '%Y%m%d%H%M%S'

AUTHOR_PLACEHOLDER = 'img/users/placeholder.png'

views = Blueprint('views', __name__)


@views.context_processor
def inject_settings_variable():
    return {
        'settings': get_settings()
    }


def collect_posts(post_types, before_ts, per_page, tag, search=None,
                  include_hidden=False):
    query = Post.query
    query = query.options(
        sqlalchemy.orm.subqueryload(Post.tags),
        sqlalchemy.orm.subqueryload(Post.mentions),
        sqlalchemy.orm.subqueryload(Post.reply_contexts),
        sqlalchemy.orm.subqueryload(Post.repost_contexts),
        sqlalchemy.orm.subqueryload(Post.like_contexts),
        sqlalchemy.orm.subqueryload(Post.bookmark_contexts))
    if tag:
        query = query.filter(Post.tags.any(Tag.name == tag))
    if not include_hidden:
        query = query.filter_by(hidden=False)
    query = query.filter_by(deleted=False, draft=False)
    if post_types:
        query = query.filter(Post.post_type.in_(post_types))
    if search:
        query = query.filter(
            sqlalchemy.func.concat(Post.title, ' ', Post.content)
            .op('@@')(sqlalchemy.func.plainto_tsquery(search)))

    try:
        if before_ts:
            before_dt = datetime.datetime.strptime(before_ts, BEFORE_TS_FORMAT)
            query = query.filter(Post.published < before_dt)
    except ValueError:
        current_app.logger.warn('Could not parse before timestamp: %s',
                                before_ts)

    query = query.order_by(Post.published.desc())
    query = query.limit(per_page)
    posts = query.all()

    posts = [post for post in posts if check_audience(post)]
    if posts:
        last_ts = posts[-1].published\
                           .replace(tzinfo=datetime.timezone.utc)\
                           .astimezone(TIMEZONE)\
                           .strftime(BEFORE_TS_FORMAT)
        view_args = request.view_args.copy()
        view_args['before_ts'] = last_ts
        for k, v in request.args.items():
            view_args[k] = v
        older = url_for(request.endpoint, **view_args)
    else:
        older = None

    return posts, older


def collect_upcoming_events():
    now = datetime.datetime.utcnow()
    events = Post.query\
        .filter(Post.post_type == 'event')\
        .filter(Post.end_utc > now.isoformat('T'))\
        .order_by(Post.start_utc)\
        .all()
    return events


# Font sizes in em. Maybe should be configurable
MIN_TAG_SIZE = 1.0
MAX_TAG_SIZE = 4.0
MIN_TAG_COUNT = 2


def render_tags(title, tags):
    if tags:
        counts = [tag['count'] for tag in tags]
        mincount, maxcount = min(counts), max(counts)
        for tag in tags:
            if maxcount > mincount:
                tag['size'] = (MIN_TAG_SIZE +
                               (MAX_TAG_SIZE - MIN_TAG_SIZE) *
                               (tag['count'] - mincount) /
                               (maxcount - mincount))
            else:
                tag['size'] = MIN_TAG_SIZE
    return util.render_themed('tags.jinja2', tags=tags, title=title,
                              max_tag_size=MAX_TAG_SIZE)


def render_posts(title, posts, older, events=None, template='posts.jinja2'):
    atom_args = request.view_args.copy()
    atom_args.update({'feed': 'atom', '_external': True})
    atom_url = url_for(request.endpoint, **atom_args)
    atom_title = title or 'Stream'
    return util.render_themed(template, posts=posts, title=title,
                              older=older, atom_url=atom_url,
                              atom_title=atom_title, events=events)


def render_posts_atom(title, feed_id, posts):
    return make_response(
        render_template('posts.atom', title=title, feed_id=feed_id,
                        posts=posts),
        200, {'Content-Type': 'application/atom+xml; charset=utf-8'})


@views.route('/')
@views.route('/before-<before_ts>')
def index(before_ts=None):
    post_types = [type[0] for type in POST_TYPES if type[0] != 'event']
    posts, older = collect_posts(
        post_types, before_ts, int(get_settings().posts_per_page),
        None, include_hidden=False)

    if request.args.get('feed') == 'atom':
        return render_posts_atom('Stream', 'index.atom', posts)

    resp = make_response(
        render_posts('Stream', posts, older,
                     events=collect_upcoming_events(),
                     template='home.jinja2'))

    if 'PUSH_HUB' in current_app.config:
        resp.headers.add('Link', '<{}>; rel="hub"'.format(
            current_app.config['PUSH_HUB']))
        resp.headers.add('Link', '<{}>; rel="self"'.format(
            url_for('.index', _external=True)))
    return resp


@views.route('/everything')
@views.route('/everything/before-<before_ts>')
def everything(before_ts=None):
    posts, older = collect_posts(
        None, before_ts, int(get_settings().posts_per_page), None,
        include_hidden=True)

    if request.args.get('feed') == 'atom':
        return render_posts_atom('Everything', 'everything.atom', posts)
    return render_posts('Everything', posts, older)


@views.route('/' + PLURAL_TYPE_RULE)
@views.route('/' + PLURAL_TYPE_RULE + '/before-<before_ts>')
def posts_by_type(plural_type, before_ts=None):
    post_type, _, title = next(tup for tup in POST_TYPES
                               if tup[1] == plural_type)
    posts, older = collect_posts(
        (post_type,), before_ts, int(get_settings().posts_per_page), None,
        include_hidden=True)

    if request.args.get('feed') == 'atom':
        return render_posts_atom(title, plural_type + '.atom', posts)
    return render_posts(title, posts, older)


@views.route('/tags')
def tag_cloud():
    query = db.session.query(
        Tag.name, sqlalchemy.func.count(Post.id)
    ).join(Tag.posts)
    query = query.filter(sqlalchemy.sql.expression.not_(Post.deleted))
    if not flask_login.current_user.is_authenticated():
        query = query.filter(sqlalchemy.sql.expression.not_(Post.draft))
    query = query.group_by(Tag.id).order_by(Tag.name)
    query = query.having(sqlalchemy.func.count(Post.id) >= MIN_TAG_COUNT)
    tagdict = {}
    for name, count in query.all():
        tagdict[name] = tagdict.get(name, 0) + count
    tags = [
        {"name": name, "count": tagdict[name]}
        for name in sorted(tagdict)
    ]
    return render_tags("Tags", tags)


@views.route('/tags/<tag>')
@views.route('/tags/<tag>/before-<before_ts>')
def posts_by_tag(tag, before_ts=None):
    posts, older = collect_posts(
        None, before_ts, int(get_settings().posts_per_page), tag,
        include_hidden=True)
    title = '#' + tag

    if request.args.get('feed') == 'atom':
        return render_posts_atom(title, 'tag-' + tag + '.atom', posts)
    return render_posts(title, posts, older)


@views.route('/search')
@views.route('/search/before-<before_ts>')
def search(before_ts=None):
    q = request.args.get('q')
    if not q:
        abort(404)

    posts, older = collect_posts(
        None, before_ts, int(get_settings().posts_per_page), None,
        include_hidden=True, search=q)
    return render_posts('Search: ' + q, posts, older)


@views.route('/all.atom')
def all_atom():
    return redirect(url_for('.everything', feed='atom'))


@views.route('/updates.atom')
def updates_atom():
    return redirect(url_for('.index', feed='atom'))


@views.route('/articles.atom')
def articles_atom():
    return redirect(
        url_for('.posts_by_type', plural_type='articles', feed='atom'))


def check_audience(post):
    if not post.audience:
        # all posts public by default
        return True

    if flask_login.current_user.is_authenticated():
        # admin user can see everything
        return True

    if flask_login.current_user.is_anonymous():
        # anonymous users can't see stuff
        return False

    # check that their username is listed in the post's audience
    current_app.logger.debug(
        'checking that logged in user %s is in post audience %s',
        flask_login.current_user.get_id(), post.audience)
    return flask_login.current_user.get_id() in post.audience


@views.route('/' + POST_TYPE_RULE + '/' + DATE_RULE + '/files/<filename>')
def post_associated_file_by_historic_path(post_type, year, month, day,
                                          index, filename):
    post = Post.load_by_historic_path('{}/{}/{:02d}/{:02d}/{}'.format(
        post_type, year, month, day, index))
    if not post:
        abort(404)
    return redirect('/{}/files/{}'.format(post.path, filename))


@views.route('/<int:year>/<int(fixed_digits=2):month>/<slug>/files/<filename>')
def attachment(year, month, slug, filename):
    post = Post.load_by_path('{}/{:02d}/{}'.format(year, month, slug))
    if not post:
        current_app.logger.debug('could not find post for path %s %s %s',
                                 year, month, slug)
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not check_audience(post):
        abort(401)  # not authorized TODO a nicer page

    attachment = next(
        (a for a in post.attachments if a.filename == filename), None)

    if not attachment:
        current_app.logger.warn('no attachment naemd %s', filename)

    current_app.logger.debug('image file path: %s. request args: %s',
                             attachment.disk_path, request.args)

    if not os.path.exists(attachment.disk_path):
        current_app.logger.warn('source path does not exist %s',
                                attachment.disk_path)
        abort(404)

    if current_app.debug:
        _, ext = os.path.splitext(attachment.disk_path)
        return send_from_directory(
            os.path.dirname(attachment.disk_path),
            os.path.basename(attachment.disk_path),
            mimetype=attachment.mimetype)

    resp = make_response('')
    # nginx is configured to serve internal resources directly
    resp.headers['X-Accel-Redirect'] = os.path.join(
        '/internal_data', attachment.storage_path)
    resp.headers['Content-Type'] = attachment.mimetype
    del resp.headers['Content-Length']
    current_app.logger.debug('response with X-Accel-Redirect %s', resp.headers)
    return resp


@views.route('/' + POST_TYPE_RULE + '/' + DATE_RULE, defaults={'slug': None})
@views.route('/' + POST_TYPE_RULE + '/' + DATE_RULE + '/<slug>')
def post_by_date(post_type, year, month, day, index, slug):
    post = Post.load_by_historic_path('{}/{}/{:02d}/{:02d}/{}'.format(
        post_type, year, month, day, index))
    if not post:
        abort(404)
    return redirect(post.permalink)


@views.route('/<any({}):tag>/<tail>'.format(','.join(util.TAG_TO_TYPE)))
def post_by_short_path(tag, tail):
    post = Post.load_by_short_path('{}/{}'.format(tag, tail))
    if not post:
        abort(404)
    return redirect(post.permalink)


@views.route('/<int:year>/<int(fixed_digits=2):month>/<slug>')
def post_by_path(year, month, slug):
    post = Post.load_by_path('{}/{:02d}/{}'.format(year, month, slug))
    return render_post(post)


@views.route('/drafts/<hash>')
def draft_by_hash(hash):
    post = Post.load_by_path('drafts/{}'.format(hash))
    return render_post(post)


def render_post(post):
    if not post:
        abort(404)

    if post.deleted:
        abort(410)  # deleted permanently

    if not check_audience(post):
        abort(401)  # not authorized TODO a nicer page

    if post.redirect:
        return redirect(post.redirect)

    return util.render_themed('post.jinja2', post=post,
                              title=post.title_or_fallback)


@views.app_template_filter('json')
def to_json(obj):
    return Markup(json.dumps(obj))


@views.app_template_filter('approximate_latitude')
def approximate_latitude(loc):
    latitude = loc.get('latitude')
    if latitude:
        return '{:.3f}'.format(latitude)


@views.app_template_filter('approximate_longitude')
def approximate_longitude(loc):
    longitude = loc.get('longitude')
    return longitude and '{:.3f}'.format(longitude)


@views.app_template_filter('geo_name')
def geo_name(loc):
    name = loc.get('name')
    if name:
        return name

    locality = loc.get('locality')
    region = loc.get('region')
    if locality and region:
        return "{}, {}".format(locality, region)

    latitude = loc.get('latitude')
    longitude = loc.get('longitude')
    if latitude and longitude:
        return "{:.2f}, {:.2f}".format(float(latitude), float(longitude))

    return "Unknown Location"


@views.app_template_filter('isotime')
def isotime_filter(thedate):
    if thedate:
        thedate = thedate.replace(microsecond=0)
        if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
            tz = pytz.timezone(get_settings().timezone)
            thedate = pytz.utc.localize(thedate).astimezone(tz)
        if isinstance(thedate, datetime.datetime):
            return thedate.isoformat('T')
        return thedate.isoformat()


@views.app_template_filter('human_time')
def human_time(thedate, alternate=None):
    if not thedate:
        return alternate

    if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
        tz = pytz.timezone(get_settings().timezone)
        thedate = pytz.utc.localize(thedate).astimezone(tz)

    if (isinstance(thedate, datetime.datetime)
            and datetime.datetime.now(TIMEZONE) - thedate < datetime.timedelta(days=1)):
        return thedate.strftime('%B %-d, %Y %-I:%M%P %Z')
    else:
        return thedate.strftime('%B %-d, %Y')


@views.app_template_filter('datetime_range')
def datetime_range(rng):
    start, end = rng
    if not start or not end:
        return '???'

    fmt1 = '%Y %B %-d, %-I:%M%P'
    if start.date() == end.date():
        fmt2 = '%-I:%M%P %Z'
    else:
        fmt2 = '%Y %B %-d, %-I:%M%P %Z'

    return (
        '<time class="dt-start" datetime="{}">{}</time>'
        ' &mdash; <time class="dt-end" datetime="{}">{}</time>'
    ).format(
        isotime_filter(start),
        start.strftime(fmt1),
        isotime_filter(end),
        end.strftime(fmt2)
    )


@views.app_template_filter('date')
def date_filter(thedate, first_only=False):
    if thedate:
        if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
            tz = pytz.timezone(get_settings().timezone)
            thedate = pytz.utc.localize(thedate).astimezone(tz)
        formatted = thedate.strftime('%B %-d, %Y')
        if first_only:
            previous = getattr(g, 'previous date', None)
            setattr(g, 'previous date', formatted)
            if previous == formatted:
                return None
        return formatted


@views.app_template_filter('time')
def time_filter(thedate):
    if thedate:
        if hasattr(thedate, 'tzinfo') and not thedate.tzinfo:
            tz = pytz.timezone(get_settings().timezone)
            thedate = pytz.utc.localize(thedate).astimezone(tz)
        if isinstance(thedate, datetime.datetime):
            return thedate.strftime('%-I:%M%P %Z')


@views.app_template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    if number == 1:
        return singular
    else:
        return plural


@views.app_template_filter('month_shortname')
def month_shortname(month):
    return datetime.date(1990, month, 1).strftime('%b')


@views.app_template_filter('month_name')
def month_name(month):
    return datetime.date(1990, month, 1).strftime('%B')


@views.app_template_filter('atom_sanitize')
def atom_sanitize(content):
    return Markup.escape(str(content))


@views.app_template_filter('prettify_url')
def prettify_url(*args, **kwargs):
    return util.prettify_url(*args, **kwargs)


@views.app_template_filter('domain_from_url')
def domain_from_url(url):
    if not url:
        return url
    return urllib.parse.urlparse(url).netloc


@views.app_template_filter('format_syndication_url')
def format_syndication_url(url, include_rel=True):
    fmt = '<a class="u-syndication" '
    if include_rel:
        fmt += 'rel="syndication" '
    fmt += 'href="{}"><i class="fa {}"></i> {}</a>'

    if util.TWITTER_RE.match(url):
        return Markup(fmt.format(url, 'fa-twitter', 'Twitter'))
    if util.FACEBOOK_RE.match(url) or util.FACEBOOK_EVENT_RE.match(url):
        return Markup(fmt.format(url, 'fa-facebook', 'Facebook'))
    if util.INSTAGRAM_RE.match(url):
        return Markup(fmt.format(url, 'fa-instagram', 'Instagram'))

    return Markup(fmt.format(url, 'fa-paper-plane', domain_from_url(url)))


IMAGE_TAG_RE = re.compile(r'<img([^>]*) src="(https?://[^">]+)"')


@views.app_template_filter('proxy_all')
def proxy_all_filter(html, side=None):
    def repl(m):
        url = m.group(2)
        # don't proxy images that come from this site
        if url.startswith(get_settings().site_url):
            return m.group(0)
        url = url.replace('&amp;', '&')
        return '<img{} src="{}"'.format(
            m.group(1), imageproxy.imageproxy_filter(url, side))
    return IMAGE_TAG_RE.sub(repl, html) if html else html
