from . import util
from PIL import Image, ExifTags
from flask import request, abort, send_file, url_for, make_response, \
    Blueprint, escape, current_app
from requests.exceptions import HTTPError
import datetime
import hashlib
import hmac
import json
import os
import shutil
import urllib.parse

# store image locally as
# /_imageproxy/<encoded url>/(orig|size)

# store info about image locally (when last checked, etc.) as
# /_imageproxy/<encoded url>/info.json

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'


imageproxy = Blueprint('imageproxy', __name__)


def construct_url(url, size):
    args = []
    args.append(('url', url))
    if size:
        args.append(('size', size))
    args.append(('sig', sign(url, size)))
    return '/imageproxy?' + urllib.parse.urlencode(args)
    #return url_for('proxy', url=url, size=size, sig=sign(url, size))


@imageproxy.app_template_filter('imageproxy')
def imageproxy_filter(src, side=None):
    return escape(
        construct_url(src, side and str(side)))


@imageproxy.route('/imageproxy')
def proxy():
    url = request.args.get('url')
    size = request.args.get('size')
    sig = request.args.get('sig')

    if sign(url, size) != sig:
        return abort(403)

    encurl = hashlib.md5(url.encode()).hexdigest()
    parent = os.path.join(
        util.image_root_path(), '_imageproxy', encurl[:1], encurl[:2], encurl)
    intparent = os.path.join(
        '/internal_imageproxy', encurl[:1], encurl[:2], encurl)

    infopath = os.path.join(parent, 'info.json')
    origpath = os.path.join(parent, 'orig')
    if not size:
        resizepath = origpath
        intpath = os.path.join(intparent, 'orig')
    else:
        resizepath = os.path.join(parent, size)
        intpath = os.path.join(intparent, size)

    info = {}
    source = None

    # first check if the info file exists
    if os.path.exists(infopath):
        with open(infopath) as f:
            info = json.load(f)

    # check if it was an error
    if 'error' in info and 'code' in info:
        return abort(info['code'])

    # we may already have the image downloaded and resized
    if 'mimetype' in info and os.path.exists(resizepath):
        return _send_file_x_accel(resizepath, intpath, info['mimetype'])

    # we may already have the original downloaded
    if os.path.exists(origpath):
        source = Image.open(origpath)
        mimetype = Image.MIME.get(source.format)

    # download the source image
    else:
        info = {
            'url': url,
            'retrieved': datetime.datetime.strftime(
                datetime.datetime.utcnow(), DATETIME_FORMAT),
        }

        if not os.path.exists(parent):
            os.makedirs(parent)

        try:
            util.download_resource(url, origpath)
        except HTTPError as e:
            info.update({
                'error': str(e),
                'code': e.response.status_code,
            })
            with open(infopath, 'w') as f:
                json.dump(info, f)
            return abort(e.response.status_code)

        source = Image.open(origpath)
        mimetype = Image.MIME.get(source.format)
        info.update({
            'mimetype': mimetype,
            'width': source.size[0],
            'height': source.size[1],
        })
        with open(infopath, 'w') as f:
            json.dump(info, f)

    if origpath != resizepath:
        resize_image(origpath, resizepath, int(size), source_image=source)
    source.close()
    # TODO X-Accel
    return _send_file_x_accel(resizepath, intpath, mimetype=mimetype)


def _send_file_x_accel(filepath, intpath, mimetype):
    if current_app.debug:
        return send_file(filepath, mimetype=mimetype)
    resp = make_response('')
    resp.headers['X-Accel-Redirect'] = intpath
    resp.headers['Content-Type'] = mimetype
    print('sending response', resp, resp.headers)
    return resp


def sign(url, size):
    key = current_app.config['SECRET_KEY']
    h = hmac.new(key.encode())
    if size:
        h.update(str(size).encode())
    h.update(url.encode())
    return h.hexdigest()


def resize_image(source_path, target_path, side, source_image=None):
    if not os.path.exists(target_path):
        if not os.path.exists(os.path.dirname(target_path)):
            os.makedirs(os.path.dirname(target_path))

        if source_image:
            im = source_image
        else:
            im = Image.open(source_path)

        # grab the format before we start rotating it
        format = im.format
        orientation = next((k for k, v in ExifTags.TAGS.items()
                            if v == 'Orientation'), None)

        if hasattr(im, '_getexif') and im._getexif():
            exif = dict(im._getexif().items())
            if orientation in exif:
                if exif[orientation] == 3:
                    im = im.transpose(Image.ROTATE_180)
                elif exif[orientation] == 6:
                    im = im.transpose(Image.ROTATE_270)
                elif exif[orientation] == 8:
                    im = im.transpose(Image.ROTATE_90)

        origw, origh = im.size
        ratio = side / max(origw, origh)
        # scale down, not up
        if ratio >= 1:
            shutil.copyfile(source_path, target_path)
        else:
            resized = im.resize((int(origw * ratio), int(origh * ratio)),
                                Image.ANTIALIAS)
            resized.save(target_path, format=format)
