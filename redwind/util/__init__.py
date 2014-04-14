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

from .. import app
from datetime import date
from urllib.parse import urljoin
import os
import os.path
import re
import requests


def download_resource(url, path):
    app.logger.debug("downloading {} to {}".format(url, path))

    try:
        response = requests.get(urljoin(app.config['SITE_URL'], url),
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
        app.logger.exception("trying to download resource")


TWITTER_USERNAME_REGEX = r'(?<!\w)@([a-zA-Z0-9_]+)'
LINK_REGEX = r'\b(?<!=.)https?://([a-zA-Z0-9/\.\-_:%?@$#&=]+)'


def autolink(plain):
    plain = re.sub(LINK_REGEX,
                   r'<a href="\g<0>">\g<1></a>', plain)
    plain = re.sub(TWITTER_USERNAME_REGEX,
                   r'<a href="http://twitter.com/\g<1>">\g<0></a>', plain)
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
    try:
        index_enc = tag[4:]
        return base60_decode(index_enc)
    except ValueError:
        app.logger.warn("Could not parse base60 index %s", tag)


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
