from . import app
from . import auth
from . import util
from .models import get_settings
from flask import request, abort, make_response, url_for, jsonify
from flask.ext.login import login_user
import datetime
import jwt
import requests
import urllib

SYNDICATION_TARGETS = {
    'https://twitter.com/kylewm2': 'twitter',
    'https://facebook.com/kyle.mahan': 'facebook',
    'http://instagram.com/kylewm2': 'instagram',
    'https://kylewm.wordpress.com': 'wordpress',
}


@app.route('/token', methods=['POST'])
def token_endpoint():
    code = request.form.get('code')
    me = request.form.get('me')
    redirect_uri = request.form.get('redirect_uri')
    client_id = request.form.get('client_id')
    state = request.form.get('state')

    app.logger.debug("received access token request with code=%s, "
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

    app.logger.debug("raw verification response from indieauth %s, %s, %s",
                     response, response.headers, response.text)

    response.raise_for_status()

    resp_data = urllib.parse.parse_qs(response.text)
    auth_me = resp_data.get('me', [])
    auth_scope = resp_data.get('scope', [])

    app.logger.debug("verification response from indieauth. me=%s, "
                     "client_id=%s, scope=%s", auth_me, auth_scope)

    if me not in auth_me:
        app.logger.warn(
            "rejecting access token request me=%s, expected me=%s",
            me, auth_me)
        abort(400)

    token = util.jwt_encode({
        'me': me,
        'client_id': client_id,
        'scope': auth_scope,
        'date_issued': util.isoformat(datetime.datetime.utcnow()),
    })

    app.logger.debug("generating access token %s", token)

    response_body = urllib.parse.urlencode({
        'access_token': token,
        'me': me,
        'scope': ' '.join(auth_scope),
    })
    app.logger.debug("returning urlencoded response %s", response_body)

    return make_response(
        response_body, 200,
        {'Content-Type': 'application/x-www-form-urlencoded'})


@app.route('/micropub', methods=['GET', 'POST'])
def micropub_endpoint():
    app.logger.info(
        "received micropub request %s, args=%s, form=%s, headers=%s",
        request, request.args, request.form, request.headers)

    if request.method == 'GET':
        app.logger.debug('micropub GET request %s -> %s', request,
                         request.args)
        q = request.args.get('q')
        if q == 'syndicate-to':
            app.logger.debug('returning syndication targets')
            response = make_response(urllib.parse.urlencode([
                ('syndicate-to[]', target) for target in SYNDICATION_TARGETS]))
            response.headers['Content-Type'] = 'application/x-www-form-urlencoded'
            return response

        elif q in ('actions', 'json_actions'):
            app.logger.debug('returning action handlers')
            reply_url = url_for('new_post', type='reply', _external=True)
            repost_url = url_for('new_post', type='share', _external=True)
            like_url = url_for('new_post', type='like', _external=True)
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
        app.logger.warn('hit micropub endpoint with no access token')
        abort(401)

    try:
        decoded = util.jwt_decode(token)
    except jwt.DecodeError as e:
        app.logger.warn('could not decode access token: %s', e)
        abort(401)

    me = decoded.get('me')
    parsed = urllib.parse.urlparse(me)
    user = auth.load_user(parsed.netloc)
    if not user:
        app.logger.warn('received valid access token for invalid user: %s', me)
        abort(401)

    in_reply_to = request.form.get('in-reply-to')
    like_of = request.form.get('like-of')
    photo_file = request.files.get('photo')
    bookmark = request.form.get('bookmark') or request.form.get('bookmark-of')
    repost_of = request.form.get('repost-of')

    post_type = ('photo' if photo_file else 'reply' if in_reply_to
                 else 'like' if like_of else 'bookmark' if bookmark
                 else 'share' if repost_of else 'note')

    latitude = None
    longitude = None
    location_name = None

    loc_str = request.form.get('location')
    geo_prefix = 'geo:'
    if loc_str and loc_str.startswith(geo_prefix):
        loc_str = loc_str[len(geo_prefix):]
        loc_params = loc_str.split(';')
        if loc_params:
            latitude, longitude = loc_params[0].split(',', 1)
            location_name = request.form.get('place_name')

    syndicate_to = request.form.getlist('syndicate-to[]')

    # translate from micropub's verbage.TODO unify
    translated = util.filter_empty_keys({
        'post_type': post_type,
        'published': request.form.get('published'),
        'title': request.form.get('name'),
        'content': request.form.get('content'),
        'latitude': latitude,
        'longitude': longitude,
        'location_name': location_name,
        'syndication': request.form.get('syndication'),
        'in_reply_to': in_reply_to,
        'like_of': like_of,
        'repost_of': repost_of,
        'bookmark_of': bookmark,
        'photo': photo_file,
        'syndicate-to[]': [SYNDICATION_TARGETS.get(to) for to in syndicate_to],
        'hidden': 'true' if in_reply_to or like_of or bookmark else 'false',
    })
    with app.test_request_context(base_url=get_settings().site_url, path='/save_new',
                                  method='POST', data=translated):
        app.logger.debug('received fake request %s: %s', request, request.args)
        login_user(user)
        app.logger.debug('successfully authenticated as user %s => %s', me, user)
        from . import views
        resp = views.save_new()
        return make_response('Created', 201, {'Location': resp.location})
