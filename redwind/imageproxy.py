from redwind import util
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
import sys
import urllib.parse

imageproxy = Blueprint('imageproxy', __name__)


def construct_url(url, size=None):
    from redwind.models import get_settings
    if not url:
        return
    url = urllib.parse.urljoin(get_settings().site_url, url)
    query = [('url', url)]
    if size:
        query += [('w', size), ('h', size), ('mode', 'clip')]
    else:
        query += [('op', 'noop')]
    querystring = urllib.parse.urlencode(query)
    if 'PILBOX_KEY' in current_app.config:
        h = hmac.new(current_app.config['PILBOX_KEY'].encode(),
                     querystring.encode(), hashlib.sha1)
        querystring += '&sig=' + h.hexdigest()
        return current_app.config['PILBOX_URL'] + '?' + querystring
    return url


@imageproxy.app_template_filter('imageproxy')
def imageproxy_filter(src, side=None):
    return escape(
        construct_url(src, side and str(side)))
