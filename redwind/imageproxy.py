import flask
import os
import shutil
import tempfile
import requests
import hmac
import hashlib
import codecs
from PIL import Image, ExifTags


imageproxy = flask.Blueprint('imageproxy', __name__)


@imageproxy.route('/<digest>/<size>/<encoded_url>')
def image(digest, size, encoded_url):
    url = codecs.decode(encoded_url, 'hex_codec').decode()
    flask.current_app.logger.debug('fetching image from %s', url)

    if not sign(size, url) == digest:
        return flask.abort(403)

    _, ext = os.path.splitext(url)

    original = tempfile.NamedTemporaryFile(suffix=ext)
    mimetype = download_resource(url, original)
    original.seek(0)

    if size == 'n':
        return flask.send_file(original, mimetype=mimetype)

    try:
        size = int(size)
    except:
        return flask.abort(400)

    resized = tempfile.NamedTemporaryFile(suffix=ext)
    success = resize_image(original, resized, size)
    resized.seek(0)
        
    return flask.send_file(resized if success else original,
                           mimetype=mimetype)
        


def sign(size, url):
    key = flask.current_app.config['SECRET_KEY']
    h = hmac.new(key.encode(), digestmod=hashlib.sha1)
    h.update(size.encode())
    h.update(url.encode())
    return h.hexdigest()


def download_resource(url, target):
    flask.current_app.logger.debug("downloading {} to {}".format(url, target))
    response = requests.get(url, stream=True, timeout=10)
    response.raise_for_status()
    for chunk in response.iter_content(512):
        target.write(chunk)

    content_type = response.headers.get('Content-Type', 'image/jpeg')
    mimetype = content_type.split(';', 1)[0]
    return mimetype


def resize_image(source, target, side):
    im = Image.open(source)
    original_format = im.format

    flask.current_app.logger.debug('detected image format %s', original_format)
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

    w, h = im.size
    ratio = side / max(w, h)

    # scale down, not up
    if ratio >= 1:
        return False

    flask.current_app.logger.debug('resizing image file from %s to %s', source.name, target.name)
    im = im.resize((int(w * ratio), int(h * ratio)),
                   Image.ANTIALIAS)
    im.save(target, original_format)
    return True
