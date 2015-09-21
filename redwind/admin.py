from flask import Blueprint, render_template, request, current_app, abort
from flask import flash, redirect, url_for, session, make_response
from redwind import auth
from redwind import contexts
from redwind import hooks
from redwind import maps
from redwind import util
from redwind.extensions import db
from redwind.models import Post, Attachment, Tag, Contact, Mention, Nick
from redwind.models import Venue, Setting, get_settings
from werkzeug import secure_filename
import bs4
import collections
import datetime
import flask.ext.login as flask_login
import hashlib
import itertools
import json
import mf2util
import mimetypes
import operator
import os
import random
import requests
import string
import urllib

admin = Blueprint('admin', __name__)


@admin.context_processor
def inject_settings_variable():
    return {
        'settings': get_settings()
    }


def get_tags():
    return [t.name for t in Tag.query.all()]


def get_top_tags(n=10):
    """
    Determine top-n tags based on a combination of frequency and receny.
    ref: https://developer.mozilla.org/en-US/docs/Mozilla/Tech/Places/
                 Frecency_algorithm
    """
    rank = collections.defaultdict(int)
    now = datetime.datetime.utcnow()

    entries = Post.query.join(Post.tags).values(Post.published, Tag.name)
    for published, tag in entries:
        weight = 0
        if published:
            if published.tzinfo:
                published = published.astimezone(datetime.timezone.utc)
                published = published.replace(tzinfo=None)
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


@admin.route('/new/<type>')
@admin.route('/new', defaults={'type': 'note'})
def new_post(type):
    post = Post(type)
    post.published = datetime.datetime.utcnow()
    post.content = ''

    if type == 'reply':
        in_reply_to = request.args.get('url')
        if in_reply_to:
            post.in_reply_to = [in_reply_to]
            # post.reply_contexts = [contexts.create_context(in_reply_to)]

    elif type == 'share':
        repost_of = request.args.get('url')
        if repost_of:
            post.repost_of = [repost_of]
            # post.repost_contexts = [contexts.create_context(repost_of)]

    elif type == 'like':
        like_of = request.args.get('url')
        if like_of:
            post.like_of = [like_of]
            # post.like_contexts = [contexts.create_context(like_of)]

    elif type == 'bookmark':
        bookmark_of = request.args.get('url')
        if bookmark_of:
            post.bookmark_of = [bookmark_of]
            # post.bookmark_contexts = [contexts.create_context(bookmark_of)]

    post.content = request.args.get('content')
    button_text = {
        'publish': 'Publish',
        'publish_quietly': 'Publish Quietly',
        'publish+tweet': 'Publish & Tweet',
        'save_draft': 'Save as Draft',
    }

    if type == 'event':
        venues = Venue.query.order_by(Venue.name).all()
    else:
        venues = []

    return render_template('admin/edit_' + type + '.jinja2',
                           edit_type='new', post=post,
                           tags=get_tags(), top_tags=get_top_tags(20),
                           button_text=button_text, venues=venues)


@admin.route('/edit')
@flask_login.login_required
def edit_by_id():
    id = request.args.get('id')
    if not id:
        abort(404)
    post = Post.load_by_id(id)
    if not post:
        abort(404)
    type = 'post'
    if not request.args.get('advanced') and post.post_type:
        type = post.post_type

    if post.draft:
        button_text = {
            'publish': 'Publish Draft',
            'publish_quietly': 'Publish Draft Quietly',
            'publish+tweet': 'Publish Draft & Tweet',
            'save_draft': 'Resave Draft',
        }
    else:
        button_text = {
            'publish': 'Republish',
            'publish_quietly': 'Republish Quietly',
            'publish+tweet': 'Republish & Tweet',
            'save_draft': 'Unpublish, Save as Draft',
        }

    template = 'admin/edit_' + type + '.jinja2'
    if request.args.get('full'):
        template = 'admin/edit_post_all.jinja2'

    if type == 'event':
        venues = Venue.query.order_by(Venue.name).all()
    else:
        venues = []

    return render_template(template, edit_type='edit', post=post,
                           tags=get_tags(), top_tags=get_top_tags(20),
                           button_text=button_text, venues=venues)


@admin.route('/uploads')
def uploads_popup():
    return render_template('uploads_popup.jinja2')


@admin.route('/save_edit', methods=['POST'])
@flask_login.login_required
def save_edit():
    id = request.form.get('post_id')
    current_app.logger.debug('saving post %s', id)
    post = Post.load_by_id(id)
    return save_post(post)


@admin.route('/save_new', methods=['POST'])
@flask_login.login_required
def save_new():
    post_type = request.form.get('post_type', 'note')
    current_app.logger.debug('saving new post of type %s', post_type)
    post = Post(post_type)
    return save_post(post)


def save_post(post):
    was_draft = post.draft
    pub_str = request.form.get('published')
    if pub_str:
        post.published = mf2util.parse_dt(pub_str)

    start_str = request.form.get('start')
    if start_str:
        start = mf2util.parse_dt(start_str)
        if start:
            post.start = start
            post.start_utcoffset = start.utcoffset()

    end_str = request.form.get('end')
    if end_str:
        end = mf2util.parse_dt(end_str)
        if end:
            post.end = end
            post.end_utcoffset = end.utcoffset()

    if not post.published or was_draft:
        post.published = datetime.datetime.utcnow()

    # populate the Post object and save it to the database,
    # redirect to the view
    post.title = request.form.get('title', '')
    post.content = request.form.get('content')
    post.draft = request.form.get('action') == 'save_draft'
    post.hidden = request.form.get('hidden', 'false') == 'true'

    venue_name = request.form.get('new_venue_name')
    venue_lat = request.form.get('new_venue_latitude')
    venue_lng = request.form.get('new_venue_longitude')
    if venue_name and venue_lat and venue_lng:
        venue = Venue()
        venue.name = venue_name
        venue.location = {
            'latitude': float(venue_lat),
            'longitude': float(venue_lng),
        }
        venue.update_slug('{}-{}'.format(venue_lat, venue_lng))
        db.session.add(venue)
        db.session.commit()
        hooks.fire('venue-saved', venue, request.form)
        post.venue = venue

    else:
        venue_id = request.form.get('venue')
        if venue_id:
            post.venue = Venue.query.get(venue_id)

    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    if lat and lon:
        if post.location is None:
            post.location = {}

        post.location['latitude'] = float(lat)
        post.location['longitude'] = float(lon)
        loc_name = request.form.get('location_name')
        if loc_name is not None:
            post.location['name'] = loc_name
    else:
        post.location = None

    for url_attr, context_attr in (('in_reply_to', 'reply_contexts'),
                                   ('repost_of', 'repost_contexts'),
                                   ('like_of', 'like_contexts'),
                                   ('bookmark_of', 'bookmark_contexts')):
        url_str = request.form.get(url_attr)
        if url_str is not None:
            urls = util.multiline_string_to_list(url_str)
            setattr(post, url_attr, urls)

    # fetch contexts before generating a slug
    contexts.fetch_contexts(post)

    syndication = request.form.get('syndication')
    if syndication is not None:
        post.syndication = util.multiline_string_to_list(syndication)

    audience = request.form.get('audience')
    if audience is not None:
        post.audience = util.multiline_string_to_list(audience)

    tags = request.form.getlist('tags')
    if post.post_type != 'article' and post.content:
        # parse out hashtags as tag links from note-like posts
        tags += util.find_hashtags(post.content)
    tags = list(filter(None, map(util.normalize_tag, tags)))
    post.tags = [Tag.query.filter_by(name=tag).first() or Tag(tag)
                 for tag in tags]

    slug = request.form.get('slug')
    if slug:
        post.slug = util.slugify(slug)
    elif not post.slug or was_draft:
        post.slug = post.generate_slug()

    # events should use their start date for permalinks
    path_date = post.start or post.published

    if post.draft:
        m = hashlib.md5()
        m.update(bytes(path_date.isoformat() + '|' + post.slug,
                       'utf-8'))
        post.path = 'drafts/{}'.format(m.hexdigest())

    elif not post.path or was_draft:
        base_path = '{}/{:02d}/{}'.format(
            path_date.year, path_date.month, post.slug)
        # generate a unique path
        unique_path = base_path
        idx = 1
        while Post.load_by_path(unique_path):
            unique_path = '{}-{}'.format(base_path, idx)
            idx += 1
        post.path = unique_path

    # generate short path
    if not post.short_path:
        short_base = '{}/{}'.format(
            util.tag_for_post_type(post.post_type),
            util.base60_encode(util.date_to_ordinal(path_date)))
        short_paths = set(
            row[0] for row in db.session.query(Post.short_path).filter(
                Post.short_path.startswith(short_base)).all())
        for idx in itertools.count(1):
            post.short_path = short_base + util.base60_encode(idx)
            if post.short_path not in short_paths:
                break

    infiles = request.files.getlist('files') + request.files.getlist('photo')
    current_app.logger.debug('infiles: %s', infiles)
    for infile in infiles:
        if infile and infile.filename:
            current_app.logger.debug('receiving uploaded file %s', infile)
            attachment = create_attachment_from_file(post, infile)
            os.makedirs(os.path.dirname(attachment.disk_path), exist_ok=True)
            infile.save(attachment.disk_path)
            post.attachments.append(attachment)

    # pre-render the post html
    html = util.markdown_filter(post.content, img_path=post.get_image_path())
    html = util.autolink(html)
    if post.post_type == 'article':
        html = util.process_people_to_microcards(html)
    else:
        html = util.process_people_to_at_names(html)
    post.content_html = html

    if not post.id:
        db.session.add(post)
    db.session.commit()

    current_app.logger.debug('saved post %d %s', post.id, post.permalink)
    redirect_url = post.permalink

    hooks.fire('post-saved', post, request.form)
    return redirect(redirect_url)


def create_attachment_from_file(post, f, default_ext=None):
    filename = secure_filename(f.filename)
    basename, ext = os.path.splitext(filename)
    mimetype, _ = mimetypes.guess_type(f.filename)
    if not mimetype:
        mimetype = f.mimetype

    # special handling for ugly filenames from OwnYourGram
    if basename.startswith('tmp_') and ext.lower() in ('.png', '.jpg'):
        basename = 'photo'

    unique_filename = ''.join(
        random.choice(string.ascii_letters + string.digits)
        for _ in range(8)) + '-' + filename
    now = datetime.datetime.now()
    storage_path = '{}/{:02d}/{:02d}/{}'.format(
        now.year, now.month, now.day, unique_filename)

    idx = 0
    while True:
        if idx == 0:
            filename = '{}{}'.format(basename, ext)
        else:
            filename = '{}-{}{}'.format(basename, idx, ext)
        if filename not in [a.filename for a in post.attachments]:
            break
        idx += 1

    return Attachment(filename=filename,
                      mimetype=f.mimetype,
                      storage_path=storage_path)


def discover_endpoints(me):
    me_response = requests.get(me)
    if me_response.status_code != 200:
        return make_response(
            'Unexpected response from URL: {}'.format(me_response), 400)
    soup = bs4.BeautifulSoup(me_response.text)
    auth_endpoint = soup.find('link', {'rel': 'authorization_endpoint'})
    token_endpoint = soup.find('link', {'rel': 'token_endpoint'})
    micropub_endpoint = soup.find('link', {'rel': 'micropub'})

    return (auth_endpoint and auth_endpoint['href'],
            token_endpoint and token_endpoint['href'],
            micropub_endpoint and micropub_endpoint['href'])


@admin.route('/login')
def login():
    me = request.args.get('me')
    if not me:
        return render_template('admin/login.jinja2',
                               next=request.args.get('next'))

    if current_app.config.get('BYPASS_INDIEAUTH'):
        user = auth.load_user(urllib.parse.urlparse(me).netloc)
        current_app.logger.debug('Logging in user %s', user)
        flask_login.login_user(user, remember=True)
        flash('logged in as {}'.format(me))
        current_app.logger.debug('Logged in with domain %s', me)
        return redirect(request.args.get('next') or url_for('views.index'))

    if not me:
        return make_response('Missing "me" parameter', 400)
    if not me.startswith('http://') and not me.startswith('https://'):
        me = 'http://' + me
    auth_url, token_url, micropub_url = discover_endpoints(me)
    if not auth_url:
        auth_url = 'https://indieauth.com/auth'

    current_app.logger.debug('Found endpoints %s, %s, %s', auth_url, token_url,
                             micropub_url)
    state = request.args.get('next')
    session['endpoints'] = (auth_url, token_url, micropub_url)

    auth_params = {
        'me': me,
        'client_id': get_settings().site_url,
        'redirect_uri': url_for('.login_callback', _external=True),
        'state': state,
    }

    # if they support micropub try to get read indie-config permission
    if token_url and micropub_url:
        auth_params['scope'] = 'config'

    return redirect('{}?{}'.format(
        auth_url, urllib.parse.urlencode(auth_params)))


@admin.route('/login_callback')
def login_callback():
    current_app.logger.debug('callback fields: %s', request.args)

    state = request.args.get('state')
    next_url = state or url_for('views.index')
    auth_url, token_url, micropub_url = session['endpoints']

    if not auth_url:
        flash('Login failed: No authorization URL in session')
        return redirect(next_url)

    code = request.args.get('code')
    client_id = get_settings().site_url
    redirect_uri = url_for('.login_callback', _external=True)

    current_app.logger.debug('callback with auth endpoint %s', auth_url)
    response = requests.post(auth_url, data={
        'code': code,
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
    })

    rdata = urllib.parse.parse_qs(response.text)
    if response.status_code != 200:
        current_app.logger.debug('call to auth endpoint failed %s', response)
        flash('Login failed {}: {}'.format(rdata.get('error'),
                                           rdata.get('error_description')))
        return redirect(next_url)

    current_app.logger.debug('verify response %s', response.text)
    if 'me' not in rdata:
        current_app.logger.debug('Verify response missing required "me" field')
        flash('Verify response missing required "me" field {}'.format(
            response.text))
        return redirect(next_url)

    me = rdata.get('me')[0]
    scopes = rdata.get('scope')
    user = auth.load_user(urllib.parse.urlparse(me).netloc)
    if not user:
        flash('No user for domain {}'.format(me))
        return redirect(next_url)

    try_micropub_config(token_url, micropub_url, scopes, code, me,
                        redirect_uri, client_id, state)

    current_app.logger.debug('Logging in user %s', user)
    flask_login.login_user(user, remember=True)
    flash('Logged in with domain {}'.format(me))
    current_app.logger.debug('Logged in with domain %s', me)

    return redirect(next_url)


def try_micropub_config(token_url, micropub_url, scopes, code, me,
                        redirect_uri, client_id, state):
    if (not scopes or 'config' not in scopes
            or not token_url or not micropub_url):
        flash('Micropub not supported (which is fine).')
        return False

    token_response = requests.post(token_url, data={
        'code': code,
        'me': me,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'state': state,
    })

    if token_response.status_code != 200:
        flash('Unexpected response from token endpoint {}'.format(
            token_response))
        return False

    tdata = urllib.parse.parse_qs(token_response.text)
    if 'access_token' not in tdata:
        flash('Response from token endpoint missing '
              'access_token {}'.format(tdata))
        return False

    access_token = tdata.get('access_token')[0]
    session['micropub'] = (micropub_url, access_token)

    flash('Got micropub access token {}'.format(access_token[:6] + '...'))

    actions_response = requests.get(micropub_url + '?q=actions', headers={
        'Authorization': 'Bearer ' + access_token,
    })
    if actions_response.status_code != 200:
        current_app.logger.debug(
            'Bad response to action handler query %s', actions_response)
        return False

    current_app.logger.debug('Successful action handler query %s',
                             actions_response.text)
    actions_content_type = actions_response.headers.get('content-type', '')
    if 'application/json' in actions_content_type:
        adata = json.loads(actions_response.text)
        current_app.logger.debug('action handlers (json): %s', adata)
        session['action-handlers'] = adata
    else:
        adata = urllib.parse.parse_qs(actions_response.text)
        current_app.logger.debug('action handlers: %s', adata)
        session['action-handlers'] = {
            key: value[0] for key, value in adata.items()}
    return True


@admin.route('/logout')
def logout():
    flask_login.logout_user()
    for key in ('action-handlers', 'endpoints', 'micropub'):
        if key in session:
            del session[key]
    return redirect(request.args.get('next', url_for('views.index')))


@admin.route('/settings', methods=['GET', 'POST'])
@flask_login.login_required
def edit_settings():
    if request.method == 'GET':
        return render_template('admin/settings.jinja2', raw_settings=sorted(
            Setting.query.all(), key=operator.attrgetter('name')))
    for key, value in request.form.items():
        Setting.query.get(key).value = value
    db.session.commit()

    return redirect(url_for('.edit_settings'))


@admin.route('/delete')
@flask_login.login_required
def delete_by_id():
    id = request.args.get('id')
    post = Post.load_by_id(id)
    if not post:
        abort(404)
    post.deleted = True
    db.session.commit()

    redirect_url = request.args.get('redirect') or url_for('views.index')
    current_app.logger.debug('redirecting to {}'.format(redirect_url))
    return redirect(redirect_url)


@admin.route('/addressbook')
def addressbook():
    return redirect(url_for('.contacts'))


@admin.route('/contacts')
def contacts():
    contacts = Contact.query.order_by(Contact.name).all()
    return render_template('admin/contacts.jinja2', contacts=contacts)


@admin.route('/contacts/<name>')
def contact_by_name(name):
    nick = Nick.query.filter_by(name=name).first()
    contact = nick and nick.contact
    if not contact:
        abort(404)
    return render_template('admin/contact.jinja2', contact=contact)


@admin.route('/delete/contact')
@flask_login.login_required
def delete_contact():
    id = request.args.get('id')
    contact = Contact.query.get(id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('.contacts'))


@admin.route('/new/contact', methods=['GET', 'POST'])
def new_contact():
    if request.method == 'GET':
        contact = Contact()
        return render_template('admin/edit_contact.jinja2', contact=contact)

    if not flask_login.current_user.is_authenticated():
        return current_app.login_manager.unauthorized()

    contact = Contact()
    db.session.add(contact)
    return save_contact(contact)


@admin.route('/edit/contact', methods=['GET', 'POST'])
def edit_contact():
    if request.method == 'GET':
        id = request.args.get('id')
        contact = Contact.query.get(id)
        return render_template('admin/edit_contact.jinja2', contact=contact)

    if not flask_login.current_user.is_authenticated():
        return current_app.login_manager.unauthorized()

    id = request.form.get('id')
    contact = Contact.query.get(id)
    return save_contact(contact)


def save_contact(contact):
    contact.name = request.form.get('name')
    contact.image = request.form.get('image')
    contact.url = request.form.get('url')

    for nick in contact.nicks:
        db.session.delete(nick)
    db.session.commit()

    contact.nicks = [Nick(name=nick.strip())
                     for nick
                     in request.form.get('nicks', '').split(',')
                     if nick.strip()]

    contact.social = util.filter_empty_keys({
        'twitter': request.form.get('twitter'),
        'facebook': request.form.get('facebook'),
    })

    if not contact.id:
        db.session.add(contact)
    db.session.commit()

    if contact.nicks:
        return redirect(url_for('.contact_by_name', name=contact.nicks[0].name))
    else:
        return redirect(url_for('.contacts'))


@admin.route('/venues/<slug>')
def venue_by_slug(slug):
    venue = Venue.query.filter_by(slug=slug).first()
    if not venue:
        abort(404)
    current_app.logger.debug('rendering venue, location. %s, %s',
                             venue, venue.location)
    posts = Post.query.filter_by(venue_id=venue.id).all()
    return render_template('admin/venue.jinja2', venue=venue, posts=posts)


@admin.route('/venues')
def all_venues():
    venues = Venue.query.order_by(Venue.name).all()
    markers = [maps.Marker(v.location.get('latitude'),
                           v.location.get('longitude'),
                           'dot-small-pink')
               for v in venues]

    organized = {}
    for venue in venues:
        region = venue.location.get('region')
        locality = venue.location.get('locality')
        if region and locality:
            organized.setdefault(region, {})\
                     .setdefault(locality, [])\
                     .append(venue)

    map_image = maps.get_map_image(600, 400, 13, markers)
    return render_template('admin/venues.jinja2', venues=venues,
                           organized=organized, map_image=map_image)


@admin.route('/new/venue', methods=['GET', 'POST'])
def new_venue():
    venue = Venue()
    if request.method == 'GET':
        return render_template('admin/edit_venue.jinja2', venue=venue)
    return save_venue(venue)


@admin.route('/edit/venue', methods=['GET', 'POST'])
def edit_venue():
    id = request.args.get('id')
    venue = Venue.query.get(id)
    if request.method == 'GET':
        return render_template('admin/edit_venue.jinja2', venue=venue)
    return save_venue(venue)


@admin.route('/delete/venue')
@flask_login.login_required
def delete_venue():
    id = request.args.get('id')
    venue = Venue.query.get(id)
    db.session.delete(venue)
    db.session.commit()
    return redirect(url_for('all_venues'))


def save_venue(venue):
    venue.name = request.form.get('name')
    venue.location = {
        'latitude': float(request.form.get('latitude')),
        'longitude': float(request.form.get('longitude')),
    }
    venue.update_slug(request.form.get('geocode'))

    if not venue.id:
        db.session.add(venue)
    db.session.commit()

    hooks.fire('venue-saved', venue, request.form)
    return redirect(url_for('venue_by_slug', slug=venue.slug))


@admin.route('/drafts')
@flask_login.login_required
def all_drafts():
    posts = Post.query.filter_by(deleted=False, draft=True).all()
    return render_template('admin/drafts.jinja2', posts=posts)


@admin.route('/mentions')
def mentions():
    mentions = Mention.query.order_by(Mention.published.desc()).limit(100)
    return render_template('admin/mentions.jinja2', mentions=mentions)
