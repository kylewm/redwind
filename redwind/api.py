from . import app
from . import auth
from . import util
from .models import Post, Location, Metadata

from collections import deque
from flask import request, url_for, jsonify, abort, make_response
from flask.ext.login import login_required
from werkzeug import secure_filename
from bs4 import BeautifulSoup

import datetime
import jwt
import mf2py
import mf2util
import os
import random
import requests
import urllib
import json


def generate_upload_path(post, f, default_ext=None):
    filename = secure_filename(f.filename)
    basename, ext = os.path.splitext(filename)

    if ext:
        app.logger.debug('file has extension: %s, %s', basename, ext)
    else:
        app.logger.debug('no file extension, checking mime_type: %s',
                         f.mimetype)
        if f.mimetype == 'image/png':
            ext = '.png'
        elif f.mimetype == 'image/jpeg':
            ext = '.jpg'
        elif default_ext:
            # fallback application/octet-stream
            ext = default_ext

        filename = basename + ext

    #now = datetime.datetime.utcnow()
    #relpath = 'uploads/{}/{:02d}/{:02d}/{}'.format(now.year, now.month,
    #                                               now.day, filename)

    relpath = '{}/files/{}'.format(post.path, filename)
    url = '/' + relpath
    fullpath = os.path.join(app.root_path, '_data', relpath)
    return relpath, url, fullpath


@app.route('/api/mf2')
def convert_mf2():
    url = request.args.get('url')
    p = mf2py.Parser(url=url)
    blob = p.to_dict()
    return jsonify(blob)


@app.route('/api/token', methods=['POST'])
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
            "rejecting access token request me=%s, expected me=%s", me, auth_me)
        abort(400)

    token = jwt.encode({
        'me': me,
        'client_id': client_id,
        'scope': auth_scope,
        'date_issued': util.isoformat(datetime.datetime.utcnow()),
        'nonce': random.randint(1000000, 2**31),
    }, app.config['SECRET_KEY'])

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


@app.route('/api/micropub', methods=['POST'])
def micropub_endpoint():
    app.logger.info(
        "received micropub request %s, args=%s, form=%s, headers=%s",
        request, request.args, request.form, request.headers)

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
        decoded = jwt.decode(token, app.config['SECRET_KEY'])
    except jwt.DecodeError as e:
        app.logger.warn('could not decode access token: %s', e)
        abort(401)

    me = decoded.get('me')
    parsed = urllib.parse.urlparse(me)
    user = auth.load_user(parsed.netloc)
    if not user:
        app.logger.warn('received valid access token for invalid user: %s', me)
        abort(401)

    app.logger.debug('successfully authenticated as user %s => %s', me, user)

    post = Post('note')
    post._writeable = True

    post.title = request.form.get('name')
    post.content = request.form.get('content')

    pub_str = request.form.get('published')
    if pub_str:
        pub = mf2util.parse_dt(pub_str)
        if pub.tzinfo:
            pub = pub.astimezone(datetime.timezone.utc)
            pub = pub.replace(tzinfo=None)
        post.pub_date = pub
    else:
        post.pub_date = datetime.datetime.utcnow()

    post.reserve_date_index()

    loc_str = request.form.get('location')
    geo_prefix = 'geo:'
    if loc_str and loc_str.startswith(geo_prefix):
        loc_str = loc_str[len(geo_prefix):]
        loc_params = loc_str.split(';')
        if loc_params:
            lat, lon = loc_params[0].split(',', 1)
            if lat and lon:
                post.location = Location(latitude=float(lat),
                                         longitude=float(lon),
                                         name=request.form.get('place_name'))

    synd_url = request.form.get('syndication')
    if synd_url:
        post.syndication.append(synd_url)

    photo_file = request.files.get('photo')
    if photo_file:
        relpath, photo_url, fullpath \
            = generate_upload_path(post, photo_file, '.jpg')
        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))
        photo_file.save(fullpath)

        content = '![]({})'.format(os.path.basename(photo_url))
        if post.content:
            content += '\n\n' + post.content
        post.content = content

    post.save()
    post._writeable = False

    with Metadata.writeable() as mdata:
        mdata.add_or_update_post(post)
        mdata.save()

    return make_response('', 201, {'Location': post.permalink})


@app.route('/api/fetch_profile')
def fetch_profile():
    from .views import TWITTER_PROFILE_RE, FACEBOOK_PROFILE_RE

    try:
        url = request.args.get('url')
        name = None
        twitter = None
        facebook = None
        photo = None

        d = mf2py.Parser(url=url).to_dict()

        for alt in d['rels'].get('me', []):
            m = TWITTER_PROFILE_RE.match(alt)
            if m:
                twitter = m.group(1)
            else:
                m = FACEBOOK_PROFILE_RE.match(alt)
                if m:
                    facebook = m.group(1)

        # check for h-feed
        hfeed = next((item for item in d['items']
                      if 'h-feed' in item['type']), None)
        if hfeed:
            authors = hfeed.get('properties', {}).get('author')
            photos = hfeed.get('properties', {}).get('photo')
            if authors:
                if isinstance(authors[0], dict):
                    name = authors[0].get('properties', {}).get('name')
                    photo = authors[0].get('properties', {}).get('photo')
                else:
                    name = authors[0]
            if photos and not photo:
                photo = photos[0]

        # check for top-level h-card
        for item in d['items']:
            if 'h-card' in item.get('type', []):
                if not name:
                    name = item.get('properties', {}).get('name')
                if not photo:
                    photo = item.get('properties', {}).get('photo')

        return jsonify({
            'name': name,
            'photo': photo,
            'twitter': twitter,
            'facebook': facebook,
        })

    except BaseException as e:
        resp = jsonify({'error': str(e)})
        resp.status_code = 400
        return resp
