from flask import url_for, current_app
from markdown import markdown
from requests.exceptions import HTTPError, SSLError
from smartypants import smartyPants
import bleach
import brevity
import bs4
import jwt
import mf2py

from datetime import date
import cgi
import collections
import datetime
import functools
import os
import os.path
import random
import re
import requests

import unicodedata
import urllib


bleach.ALLOWED_TAGS += ['img', 'p', 'br', 'marquee', 'blink']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})


TWITTER_PROFILE_RE = re.compile(r'https?://(?:www\.)?twitter\.com/(\w+)')
TWITTER_RE = re.compile(r'https?://(?:www\.|mobile\.)?twitter\.com/(\w+)/status(?:es)?/(\w+)')
FACEBOOK_PROFILE_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([\w.-]+)/?')
FACEBOOK_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([\w.-]+)/\w+/(\w+)/?')
FACEBOOK_EVENT_RE = re.compile(r'https?://(?:www\.)?facebook\.com/events/([0-9]+)/?')
YOUTUBE_RE = re.compile(r'https?://(?:www.)?youtube\.com/watch\?v=([\w-]+)')
INSTAGRAM_RE = re.compile(r'https?://(?:www\.|mobile\.)?instagram\.com/p/([\w\-]+)/?')
PEOPLE_RE = re.compile(r"\[\[([\w ]+)(?:\|([\w\-'. ]+))?\]\]")
RELATIVE_PATH_RE = re.compile('\[([^\]]*)\]\(([^/)]+)\)')
INDIENEWS_RE = re.compile(r'https?://news.indiewebcamp.com/(.*)')
FLICKR_RE = re.compile(r'https?://(?:www\.)?flickr\.com/photos/([@\w\-]+)/(\d+)/?')
GOODREADS_RE = re.compile(r'https?://(?:www\.)?goodreads\.com/(.*)')
GITHUB_RE = re.compile(r'https?://(?:www\.)?github\.com/(.*)')

HASHTAG_RE = re.compile('(?<![\w&])#(\w\w+)', re.I)
AT_USERNAME_RE = re.compile(r"""(?<![\w&])@(\w+)(?=($|[\s,:;.?!'")&-]))""", re.I)

BLACKLIST_TAGS = ('a', 'script', 'pre', 'code', 'embed', 'object',
                  'audio', 'video')

USER_AGENT = 'Red Wind (https://github.com/kylewm/redwind)'


def isoparse(s):
    """Parse (UTC) datetimes in ISO8601 format"""
    if s:
        try:
            return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
        except:
            return datetime.datetime.strptime(s, '%Y-%m-%d')


def isoparse_with_tz(s):
    """Parse datetimes with a timezone in ISO8601 format"""
    return s and datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z')


def isoformat(date):
    if date:
        if (isinstance(date, datetime.date)
                and not isinstance(date, datetime.datetime)):
            return date.isoformat()
        if date.tzinfo:
            date = date.astimezone(datetime.timezone.utc)
            date = date.replace(tzinfo=None)
        date = date.replace(microsecond=0)
        return date.isoformat('T')


def isoformat_with_tz(date):
    if hasattr(date, 'tzinfo') and not date.tzinfo:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return date.isoformat(sep='T')


def normalize_tag(tag):
    # lowercase and remove spaces, dashes, and underscores
    tag = unicodedata.normalize('NFKD', tag).lower()
    tag = re.sub(r'[ _\-]', '', tag)
    return tag


def trim_nulls(data):
    if isinstance(data, list):
        return list(trim_nulls(v) for v in data if trim_nulls(v))
    if isinstance(data, dict):
        return dict((k, trim_nulls(v)) for k, v in data.items()
                    if trim_nulls(v))
    return data


def download_resource(url, path):
    from .models import get_settings
    current_app.logger.debug("downloading {} to {}".format(url, path))
    response = requests.get(urllib.parse.urljoin(get_settings().site_url, url),
                            stream=True, timeout=10)
    response.raise_for_status()
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    with open(path, 'wb') as f:
        for chunk in response.iter_content(512):
            f.write(chunk)


def urls_match(url1, url2):
    if url1 == url2:
        return True
    p1 = urllib.parse.urlparse(url1)
    p2 = urllib.parse.urlparse(url2)
    return p1.netloc == p2.netloc and p1.path == p2.path


def url_to_link(url, soup):
    a = soup.new_tag('a', href=url)
    a.string = prettify_url(url)
    return a


def process_text(fn, doc, blacklist=BLACKLIST_TAGS):
    """Process text nodes in an HTML document, skipping over nodes inside
    blacklisted HTML tags (like <code> tags).

    :param fn function: takes a text argument and return the processed result
    :param doc string: the HTML document to process
    :param blacklist iterable: tags inside which text should not be processed

    :return string: the processed result
    """
    result = []
    pend = 0

    opentags = collections.defaultdict(lambda: 0)
    for m in re.finditer('</?(\w+)[^>]*>', doc, re.I):
        head = doc[pend:m.start()]
        result.append(
            head if any(opentags[tagname] > 0 for tagname in blacklist)
            else fn(head))

        tag = m.group()
        tagname = m.group(1).lower()
        if not tag.endswith('/>'):
            opentags[tagname] += -1 if tag.startswith('</') else 1

        result.append(tag)
        pend = m.end()

    result.append(fn(doc[pend:]))
    return ''.join(filter(None, result))


def autolink(text):
    def link_hashtag(m):
        return '<a href="/tags/{}">{}</a>'.format(
            m.group(1).lower(), m.group())

    def link_hashtags(span):
        return HASHTAG_RE.sub(link_hashtag, span)

    text = process_text(link_hashtags, text)
    text = process_text(brevity.autolink, text)
    return text


def process_people(fn, plain):
    def process_nick(m):
        from .extensions import db
        from .models import Nick
        name = m.group(1)
        nick = Nick.query.filter(
            db.func.lower(Nick.name) == db.func.lower(name)).first()
        contact = nick and nick.contact
        processed = fn(contact, name)
        return processed if processed else m.group()

    def process_span(text):
        return AT_USERNAME_RE.sub(process_nick, text)

    return process_text(process_span, plain)


def process_people_to_microcards(plain):
    def to_microcard(contact, nick):
        from . import imageproxy
        if contact:
            url = contact.url or url_for('contact_by_name', nick)
            result = '<a class="microcard h-card" href="{}">'.format(url)

            image = contact.image
            if image:
                mcard_size = current_app.config.get('MICROCARD_SIZE', 24)
                image = cgi.escape(imageproxy.construct_url(image, mcard_size))
                result += '<img alt="" src="{}" />'.format(image)
                result += contact.name
            else:
                result += '@' + contact.name
            return result + '</a>'

        return ('<a class="microcard h-card" '
                'href="https://twitter.com/{}">@{}</a>'.format(nick, nick))

    return process_people(to_microcard, plain)


def process_people_to_at_names(plain):
    def to_at_name(contact, nick):
        if contact:
            url = contact.url or url_for('contact_by_name', nick)
        else:
            url = 'https://twitter.com/' + nick
        return '<a class="microcard h-card" href="{}">@{}</a>'.format(
            url, nick)
    return process_people(to_at_name, plain)


def find_hashtags(plain):
    """Finds hashtags in a document and returns a list of tags encountered
    """
    def fn(tags, text):
        tags += HASHTAG_RE.findall(text)

    tags = []
    process_text(functools.partial(fn, tags), plain)
    return [t.lower() for t in tags]


TAG_TO_TYPE = {
    'n': 'note',
    'a': 'article',
    'r': 'reply',
    's': 'share',
    'l': 'like',
    'c': 'checkin',
    'p': 'photo',
    'b': 'bookmark',
    'e': 'event',
}

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
        current_app.logger.warn("Could not parse base60 date %s", tag)


def parse_index(tag):
    index_enc = tag[4:]
    return index_enc


def date_to_ordinal(date0):
    return date0.toordinal() - BASE_ORDINAL


def date_from_ordinal(ordinal):
    return date.fromordinal(ordinal + BASE_ORDINAL)


def tag_for_post_type(post_type):
    return TYPE_TO_TAG.get(post_type)


# use tantek's NewBase60 http://tantek.pbworks.com/w/page/19402946/NewBase60
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


def slugify(s, limit=256):
    slug = unicodedata.normalize('NFKD', s).lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    slug = re.sub(r'[-]+', '-', slug)
    # trim to first - after the limit
    if len(slug) > limit:
        idx = slug.find('-', limit)
        if idx >= 0:
            slug = slug[:idx]
    return slug


def multiline_string_to_list(s):
    return [l.strip() for l in s.split('\n') if l.strip()]


def markdown_filter(data, img_path=None):
    if data is None:
        return ''

    if img_path:
        # replace relative paths to images with absolute
        data = RELATIVE_PATH_RE.sub('[\g<1>](' + img_path + '/\g<2>)', data)

    data = convert_legacy_people_to_at_names(data)
    if data.startswith('#'):
        data = '\\' + data
    result = markdown(data, extensions=['codehilite', 'fenced_code'])
    result = smartyPants(result)
    return result


def convert_legacy_people_to_at_names(data):
    from .models import Contact

    def process_name(m):
        fullname = m.group(1)
        displayname = m.group(2)
        contact = Contact.query.filter_by(name=fullname).first()
        if contact and contact.nicks:
            return '@' + contact.nicks[0].name
        return '@' + displayname

    data = PEOPLE_RE.sub(process_name, data)
    return data


def format_as_text(html, link_fn=None):
    if html is None:
        return ''

    # collapse whitespace
    html = re.sub(r'\s\s+', ' ', html, re.MULTILINE)

    soup = bs4.BeautifulSoup(html)
    # replace links with the URL
    for a in soup.find_all('a'):
        if link_fn:
            link_fn(a)
        else:
            a.replace_with(a.text)

    for br in soup.find_all('br'):
        br.replace_with('\n')

    for p in soup.find_all('p'):
        p.append('\n\n')
        p.unwrap()

    # and remove images
    for i in soup.find_all('img'):
        i.hidden = True

    result = soup.get_text().strip()
    # remove spaces before or after a linebreak
    result = re.sub(r' *(\n+) *', r'\1', result)
    return result


def is_cached_current(original, cached):
    """Compare a file and the processed, cached version to see if the cached
    version is up to date.
    """
    return (os.path.exists(cached)
            and os.stat(cached).st_mtime >= os.stat(original).st_mtime)


def prettify_url(url):
    """Return a URL without its schema
    """
    if not url:
        return url
    split = url.split('//', 1)
    if len(split) == 2:
        schema, path = split
    else:
        path = url
    return path.rstrip('/')


def fetch_html(url):
    """Utility to fetch HTML from an external site. If the Content-Type
    header does not explicitly list a charset, Requests will assume a
    bad one, so we have to use 'get_encodings_from_content` to find
    the meta charset or other indications in the actual response body.

    Return a requests.Response
    """
    response = requests.get(url, timeout=30, headers={
        'User-Agent': USER_AGENT,
    })
    if response.status_code // 2 == 100:
        # requests ignores <meta charset> when a Content-Type header
        # is provided, even if the header does not define a charset
        if 'charset' not in response.headers.get('content-type', ''):
            encodings = requests.utils.get_encodings_from_content(
                response.text)
            if encodings:
                response.encoding = encodings[0]
    else:
        current_app.logger.warn('failed to fetch url %s. got response %s.',
                                url, response)
    return response


def clean_foreign_html(html):
    html = re.sub('<script.*?</script>', '', html, flags=re.DOTALL)
    return bleach.clean(html, strip=True)


def jwt_encode(obj):
    obj['nonce'] = random.randint(1000000, 2 ** 31)
    return jwt.encode(obj, current_app.config['SECRET_KEY'])


def jwt_decode(s):
    return jwt.decode(s, current_app.config['SECRET_KEY'])


def posse_post_discovery(post, regex):
    """Given a post object and a permalink regex, looks for silo-specific
    in-reply-to, repost-of, like-of URLs. If the post.like_of is a silo url,
    that url is returned; otherwise we fetch the source and attempt to
    look for u-syndication URLs.

    Return:
      a tuple of the first match for (in-reply-to, repost-of, like-of)
    """
    def find_syndicated(original):
        if regex.match(original):
            return original
        try:
            d = mf2py.Parser(url=original).to_dict()
            urls = d['rels'].get('syndication', [])
            for item in d['items']:
                if 'h-entry' in item['type']:
                    urls += item['properties'].get('syndication', [])
            for url in urls:
                if regex.match(url):
                    return url
        except HTTPError:
            current_app.logger.exception('Could not fetch original')
        except SSLError:
            current_app.logger.exception('SSL Error')
        except Exception as e:
            current_app.logger.exception('MF2 Parser error: %s', e)

    def find_first_syndicated(originals):
        for original in originals:
            syndicated = find_syndicated(original)
            if syndicated:
                return syndicated

    return (
        find_first_syndicated(post.in_reply_to),
        find_first_syndicated(post.repost_of),
        find_first_syndicated(post.like_of),
    )
