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


def construct_url(url, size=None, external=False):
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
    h = hmac.new(current_app.config['PILBOX_KEY'].encode(),
                 querystring.encode(), hashlib.sha1)
    querystring += '&sig=' + h.hexdigest()
    proxy_url = current_app.config['PILBOX_URL'] + '?' + querystring
    if external:
        proxy_url = urllib.parse.urljoin(get_settings().site_url, proxy_url)
    return proxy_url

@imageproxy.app_template_filter('imageproxy')
def imageproxy_filter(src, side=None, external=False):
    return escape(
        construct_url(src, side and str(side), external))

