import datetime
import urllib

from redwind import auth
from redwind import util
from redwind.models import get_settings, Post, Venue, Credential
from redwind.extensions import db

import jwt
import requests
from flask import request, abort, make_response, url_for, jsonify, Blueprint
from flask import current_app, redirect
from flask.ext.login import login_user


SYNDICATION_TARGETS = {
    'https://twitter.com/kylewmahan': 'twitter',
    'https://facebook.com/kyle.mahan': 'facebook',
    'http://instagram.com/kylewmahan': 'instagram',
    'https://kylewm.wordpress.com': 'wordpress',
}

micropub = Blueprint('micropub', __name__)


@micropub.route('/token', methods=['POST'])
def token_endpoint():
    code = request.form.get('code')
    me = request.form.get('me')
    redirect_uri = request.form.get('redirect_uri')
    client_id = request.form.get('client_id')
    state = request.form.get('state')

    current_app.logger.debug("received access token request with code=%s, "
                             "me=%s, redirect_uri=%s, client_id=%s, state=%s",
                             code, me, redirect_uri, client_id, state)

    # delegate to indieauth to authenticate this token request
    auth_endpoint = 'https://indieauth.com/auth'
    response = requests.post(auth_endpoint, data={
        'code': code,
        'me': me,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'state': state,
    })

    current_app.logger.debug(
        "raw verification response from indieauth %s, %s, %s",
        response, response.headers, response.text)

    response.raise_for_status()

    resp_data = urllib.parse.parse_qs(response.text)
    auth_me = resp_data.get('me', [])
    auth_scope = resp_data.get('scope', [])

    current_app.logger.debug(
        "verification response from indieauth. me=%s, client_id=%s, scope=%s",
        auth_me, client_id, auth_scope)

    if me not in auth_me:
        current_app.logger.warn(
            "rejecting access token request me=%s, expected me=%s",
            me, auth_me)
        abort(400)

    token = util.jwt_encode({
        'me': me,
        'client_id': client_id,
        'scope': auth_scope,
        'date_issued': util.isoformat(datetime.datetime.utcnow()),
    })

    current_app.logger.debug("generating access token %s", token)

    response_body = urllib.parse.urlencode({
        'access_token': token,
        'me': me,
        'scope': ' '.join(auth_scope),
    })
    current_app.logger.debug("returning urlencoded response %s", response_body)

    return make_response(
        response_body, 200,
        {'Content-Type': 'application/x-www-form-urlencoded'})


@micropub.route('/micropub', methods=['GET', 'POST'])
def micropub_endpoint():
    current_app.logger.info(
        "received micropub request %s, args=%s, form=%s, headers=%s",
        request, request.args, request.form, request.headers)

    if request.method == 'GET':
        current_app.logger.debug('micropub GET request %s -> %s', request,
                                 request.args)
        q = request.args.get('q')
        if q == 'syndicate-to':
            current_app.logger.debug('returning syndication targets')
            response = make_response(urllib.parse.urlencode([
                ('syndicate-to[]', target) for target in SYNDICATION_TARGETS]))
            response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
            return response

        elif q in ('actions', 'json_actions'):
            current_app.logger.debug('returning action handlers')
            reply_url = url_for('admin.new_post', type='reply', _external=True)
            repost_url = url_for('admin.new_post', type='share', _external=True)
            like_url = url_for('admin.new_post', type='like', _external=True)
            payload = {
                'reply': reply_url + '?url={url}',
                'repost': repost_url + '?url={url}',
                'favorite': like_url + '?url={url}',
                'like': like_url + '?url={url}',
            }
            accept_header = request.headers.get('accept', '')
            if q == 'json_actions' or 'application/json' in accept_header:
                return jsonify(payload)
            else:
                response = make_response(urllib.parse.urlencode(payload))
                response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
                return response

        else:
            abort(404)

    bearer_prefix = 'Bearer '
    header_token = request.headers.get('authorization')
    if header_token and header_token.startswith(bearer_prefix):
        token = header_token[len(bearer_prefix):]
    else:
        token = request.form.get('access_token')

    if not token:
        current_app.logger.warn('hit micropub endpoint with no access token')
        abort(401)

    try:
        decoded = util.jwt_decode(token)
    except jwt.DecodeError as e:
        current_app.logger.warn('could not decode access token: %s', e)
        abort(401)

    me = decoded.get('me')
    client_id = decoded.get('client_id')
    cred = Credential.query.filter_by(type='indieauth', value=me).first()
    user = cred and cred.user
    if not user or not user.is_authenticated():
        current_app.logger.warn(
            'received valid access token for invalid user: %s', me)
        abort(401)

    h = request.form.get('h')
    in_reply_to = request.form.get('in-reply-to')
    like_of = request.form.get('like-of')
    photo_url = request.form.get('photo')
    photo_file = request.files.get('photo')
    bookmark = request.form.get('bookmark') or request.form.get('bookmark-of')
    repost_of = request.form.get('repost-of')

    if photo_url and not photo_file:
        photo_file = urllib.request.urlopen(photo_url)

    post_type = ('event' if h == 'event'
                 else 'article' if 'name' in request.form
                 else 'photo' if photo_file
                 else 'reply' if in_reply_to
                 else 'like' if like_of
                 else 'bookmark' if bookmark
                 else 'share' if repost_of
                 else 'note')

    latitude = None
    longitude = None
    location_name = None
    venue_id = None

    loc_str = request.form.get('location')
    geo_prefix = 'geo:'
    if loc_str:
        if loc_str.startswith(geo_prefix):
            loc_str = loc_str[len(geo_prefix):]
            loc_params = loc_str.split(';')
            if loc_params:
                latitude, longitude = loc_params[0].split(',', 1)
                location_name = request.form.get('place_name')
        else:
            venue_prefix = urllib.parse.urljoin(get_settings().site_url, 'venues/')
            if loc_str.startswith(venue_prefix):
                slug = loc_str[len(venue_prefix):]
                venue = Venue.query.filter_by(slug=slug).first()
                if venue:
                    venue_id = venue.id

    # url of the venue, e.g. https://kylewm.com/venues/cafe-trieste-berkeley-california
    venue = request.form.get('venue')

    syndicate_to = request.form.getlist('syndicate-to[]')
    syndication = request.form.get('syndication')

    # TODO check client_id
    if client_id == 'https://kylewm-responses.appspot.com/' and syndication:
        current_app.logger.debug(
            'checking for existing post with syndication %s', syndication)
        existing = Post.query.filter(
            Post.syndication.like(db.literal('%"' + syndication + '"%')),
            ~Post.deleted
        ).first()
        if existing:
            current_app.logger.debug(
                'found post for %s: %s', syndication, existing)
            return redirect(existing.permalink)
        else:
            current_app.logger.debug(
                'no post found with syndication %s', syndication)

    # translate from micropub's verbage.TODO unify
    translated = util.filter_empty_keys({
        'post_type': post_type,
        'published': request.form.get('published'),
        'start': request.form.get('start'),
        'end': request.form.get('end'),
        'title': request.form.get('name'),
        'content': request.form.get('content'),
        'venue': venue_id,
        'latitude': latitude,
        'longitude': longitude,
        'location_name': location_name,
        'syndication': syndication,
        'in_reply_to': in_reply_to,
        'like_of': like_of,
        'repost_of': repost_of,
        'bookmark_of': bookmark,
        'photo': photo_file,
        'syndicate-to': [SYNDICATION_TARGETS.get(to) for to in syndicate_to],
        'hidden': 'true' if like_of or bookmark else 'false',
    })
    with current_app.test_request_context(
            base_url=get_settings().site_url, path='/save_new',
            method='POST', data=translated
    ):
        current_app.logger.debug('received fake request %s: %s',
                                 request, request.args)
        login_user(user)
        current_app.logger.debug('successfully authenticated as user %s => %s',
                                 me, user)
        from . import admin
        resp = admin.save_new()
        return make_response('Created', 201, {'Location': resp.location})
