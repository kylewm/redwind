from app import app
from flask import redirect, url_for, abort
import base60
from datetime import date

TAG_TO_TYPE = {
    'n': 'note',
    'a': 'article',
    'r': 'reply',
    's': 'share',
    'l': 'like'}

TYPE_TO_TAG = {v: k for k, v in TAG_TO_TYPE.items()}

BASE_ORDINAL = date(1970, 1, 1).toordinal()


@app.route('/short/<string(minlength=5,maxlength=6):tag>')
def shortlink(tag):
    post_type = parse_type(tag)
    pub_date = parse_date(tag)
    index = parse_index(tag)

    if not post_type or not pub_date or not index:
        abort(404)

    return redirect(url_for('post_by_date', post_type=post_type,
                            year=pub_date.year, month=pub_date.month,
                            day=pub_date.day, index=index))


def parse_type(tag):
    type_enc = tag[0]
    return TAG_TO_TYPE.get(type_enc)


def parse_date(tag):
    date_enc = tag[1:4]
    ordinal = base60.decode(date_enc)
    if ordinal:
        return date_from_ordinal(ordinal)


def parse_index(tag):
    index_enc = tag[4:]
    return base60.decode(index_enc)


def date_to_ordinal(date0):
    return date0.toordinal() - BASE_ORDINAL


def date_from_ordinal(ordinal):
    return date.fromordinal(ordinal + BASE_ORDINAL)


def tag_for_post_type(post_type):
    return TYPE_TO_TAG.get(post_type)
