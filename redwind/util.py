from . import app
from datetime import date
from bs4 import BeautifulSoup
import os
import os.path
import re
import requests
import itertools
import collections
import datetime
import urllib


def isoparse(s):
    """Parse (UTC) datetimes in ISO8601 format"""
    return s and datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


def isoparse_with_tz(s):
    """Parse datetimes with a timezone in ISO8601 format"""
    return s and datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z')


def isoformat(date):
    if date:
        if date.tzinfo:
            date = date.astimezone(datetime.timezone.utc)
            date = date.replace(tzinfo=None)
        date = date.replace(microsecond=0)
        return date.isoformat('T')


def filter_empty_keys(data):
    if isinstance(data, list):
        return list(filter_empty_keys(v) for v in data if filter_empty_keys(v))
    if isinstance(data, dict):
        return dict((k, filter_empty_keys(v)) for k, v in data.items()
                    if filter_empty_keys(v))
    return data


def download_resource(url, path):
    app.logger.debug("downloading {} to {}".format(url, path))

    try:
        response = requests.get(urllib.parse.urljoin(app.config['SITE_URL'], url),
                                stream=True)

        if response.status_code // 2 == 100:
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))

            with open(path, 'wb') as f:
                for chunk in response.iter_content(512):
                    f.write(chunk)

            return True
        else:
            app.logger.warn("Failed to download resource %s. Got response %s",
                            url, str(response))
    except:
        app.logger.exception('downloading resource')


def urls_match(url1, url2):
    if url1 == url2:
        return True
    p1 = urllib.parse.urlparse(url1)
    p2 = urllib.parse.urlparse(url2)
    return p1.netloc == p2.netloc and p1.path == p2.path
                      

TWITTER_USERNAME_REGEX = r'(?<!\w)@([a-zA-Z0-9_]+)'
LINK_REGEX = r'\b(?<!=[\'"])https?://([a-zA-Z0-9/\.\-_:%?@$#&=+]+)'


def autolink(plain, twitter_names=True):
    plain = re.sub(LINK_REGEX, '<a href="\g<0>">\g<1></a>', plain)
    if twitter_names:
        plain = re.sub(TWITTER_USERNAME_REGEX, '<a href="https://twitter.com/\g<1>">\g<0></a>', plain)
    return plain


TAG_TO_TYPE = {
    'n': 'note',
    'a': 'article',
    'r': 'reply',
    's': 'share',
    'l': 'like',
    'c': 'checkin'}

TYPE_TO_TAG = {v: k for k, v in TAG_TO_TYPE.items()}

BASE_ORDINAL = date(1970, 1, 1).toordinal()


def parse_type(tag):
    type_enc = tag[0]
    return TAG_TO_TYPE.get(type_enc)


def parse_date(tag):
    try:
        date_enc = tag[1:4]
        ordinal = base60_decode(date_enc)
        if ordinal:
            return date_from_ordinal(ordinal)
    except ValueError:
        app.logger.warn("Could not parse base60 date %s", tag)


def parse_index(tag):
    index_enc = tag[4:]
    return index_enc


def date_to_ordinal(date0):
    return date0.toordinal() - BASE_ORDINAL


def date_from_ordinal(ordinal):
    return date.fromordinal(ordinal + BASE_ORDINAL)


def tag_for_post_type(post_type):
    return TYPE_TO_TAG.get(post_type)


#use tantek's NewBase60 http://tantek.pbworks.com/w/page/19402946/NewBase60
RADIX = list("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ_abcdefghijkmnopqrstuvwxyz")


def base60_encode(n):
    arr = []
    base = len(RADIX)
    while n > 0:
        c = RADIX[n % base]
        n = n // base
        arr.append(c)

    arr.reverse()
    return ''.join(arr)


def base60_decode(s):
    base = len(RADIX)
    n = 0
    for c in s:
        n *= base
        n += RADIX.index(c)
    return n


def resize_image(sourcedir, filename, side):
    from PIL import Image

    targetdir = os.path.join(app.root_path, '_resized',
                             os.path.relpath(sourcedir, app.root_path),
                             str(side))
    targetpath = os.path.join(targetdir, filename)

    if not os.path.exists(targetpath):
        if not os.path.exists(targetdir):
            os.makedirs(targetdir)

        im = Image.open(os.path.join(sourcedir, filename))
        origw, origh = im.size
        ratio = side / max(origw, origh)
        im = im.resize((int(origw * ratio), int(origh * ratio)), Image.ANTIALIAS)
        im.save(targetpath)

    return targetdir, filename
