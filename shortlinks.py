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


from app import app
from flask import redirect, url_for, abort
from util import base60
from datetime import date

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
        ordinal = base60.decode(date_enc)
        if ordinal:
            return date_from_ordinal(ordinal)
    except ValueError:
        app.logger.warn("Could not parse base60 date %s", tag)



def parse_index(tag):
    try:
        index_enc = tag[4:]
        return base60.decode(index_enc)
    except ValueError:
        app.logger.warn("Could not parse base60 index %s", tag)


def date_to_ordinal(date0):
    return date0.toordinal() - BASE_ORDINAL


def date_from_ordinal(ordinal):
    return date.fromordinal(ordinal + BASE_ORDINAL)


def tag_for_post_type(post_type):
    return TYPE_TO_TAG.get(post_type)
