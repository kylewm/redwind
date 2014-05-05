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

from . import app
from . import auth
from . import util
from . import hentry_parser
from .models import Post, Location, Metadata


from flask import request, url_for, jsonify, abort, make_response
from flask.ext.login import login_required
from werkzeug import secure_filename

import datetime
import os
import requests
import random
import jwt
import urllib


def generate_upload_path(f):
    filename = secure_filename(f.filename)
    now = datetime.datetime.utcnow()

    relpath = 'uploads/{}/{:02d}/{}'.format(now.year, now.month, filename)
    url = url_for('static', filename=relpath)
    fullpath = os.path.join(app.root_path, 'static', relpath)
    return relpath, url, fullpath


@app.route('/api/upload_file', methods=['POST'])
@login_required
def upload_file():
    f = request.files['file']
    relpath, url, fullpath = generate_upload_path(f)

    if not os.path.exists(os.path.dirname(fullpath)):
        os.makedirs(os.path.dirname(fullpath))

    f.save(fullpath)
    return jsonify({'path': url})


@app.route('/api/upload_image', methods=['POST'])
@login_required
def upload_image():
    f = request.files['file']
    relpath, url, fullpath = generate_upload_path(f)

    if not os.path.exists(os.path.dirname(fullpath)):
        os.makedirs(os.path.dirname(fullpath))
    f.save(fullpath)

    result = {'original': url}

    sizes = [('small', 300), ('medium', 600), ('large', 1024)]
    for tag, side in sizes:
        result[tag] = resize_image(relpath, tag, side)

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


@app.route('/api/mf2')
def convert_mf2():
    from mf2py.parser import Parser
    url = request.args.get('url')
    p = Parser(url=url)
    json = p.to_dict()
    return jsonify(json)


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
        'scope': auth_scope,
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
    user = auth.load_user(me)
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
        pub = hentry_parser.parse_datetime(pub_str)
        if pub.tzinfo:
            pub = pub.astimezone(datetime.timezone.utc)
            pub = pub.replace(tzinfo=None)
        post.pub_date = pub
    else:
        post.pub_date = datetime.datetime.utcnow()

    loc_str = request.form.get('location')
    geo_prefix = 'geo:'
    if loc_str and loc_str.startswith(geo_prefix):
        lat, lon = loc_str[len(geo_prefix):].split(',', 1)
        if lat and lon:
            post.location = Location(float(lat), float(lon),
                                     request.form.get('place_name'))

    synd_url = request.form.get('syndication')
    if synd_url:
        post.syndication.append(synd_url)

    photo_file = request.files.get('photo')
    if photo_file:
        relpath, photo_url, fullpath = generate_upload_path(photo_file)
        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))
        photo_file.save(fullpath)

        content = '![]({})'.format(photo_url)
        if post.content:
            content += '\n\n' + post.content
        post.content = content

    post.save()
    post._writeable = False

    with Metadata.writeable() as mdata:
        mdata.add_or_update_post(post)
        mdata.save()

    return make_response('', 201, {'Location': post.permalink})
