from . import app
from datetime import date
from flask import url_for
from markdown import markdown
from smartypants import smartyPants
import bleach
import bs4
import datetime
import jwt
import os
import os.path
import random
import re
import requests
import shutil
import unicodedata
import urllib

bleach.ALLOWED_TAGS += ['img', 'p', 'br', 'marquee', 'blink']
bleach.ALLOWED_ATTRIBUTES.update({
    'img': ['src', 'alt', 'title']
})


TWITTER_PROFILE_RE = re.compile(r'https?://(?:www\.)?twitter\.com/(\w+)')
TWITTER_RE = re.compile(r'https?://(?:www\.|mobile\.)?twitter\.com/(\w+)/status(?:es)?/(\w+)')
FACEBOOK_PROFILE_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)')
FACEBOOK_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)/\w+/(\w+)')
YOUTUBE_RE = re.compile(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)')
INSTAGRAM_RE = re.compile(r'https?://instagram\.com/p/(\w+)')

PEOPLE_RE = re.compile(r"\[\[([\w ]+)(?:\|([\w\-'. ]+))?\]\]")
RELATIVE_PATH_RE = re.compile('\[([^\]]*)\]\(([^/)]+)\)')

AT_USERNAME_RE = re.compile(r'(?i)(?<!\w)@([a-z0-9_]+)')
LINK_RE = re.compile(
    # optional schema
    r'(?i)\b([a-z]{3,9}://)?'
    # hostname and port
    '([a-z0-9.\-]+[.][a-z]{2,4}(?::\d{2,6})?'
    # path
    '(?:/(?:[a-z0-9\-_~.;:$?&%#@()/=]*[a-z0-9\-_$?#/])?)?)'
)


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


def filter_empty_keys(data):
    if isinstance(data, list):
        return list(filter_empty_keys(v) for v in data if filter_empty_keys(v))
    if isinstance(data, dict):
        return dict((k, filter_empty_keys(v)) for k, v in data.items()
                    if filter_empty_keys(v))
    return data


def download_resource(url, path):
    from .models import get_settings
    app.logger.debug("downloading {} to {}".format(url, path))
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


def autolink(plain):

    def bs4_sub(regex, repl):
        for txt in soup.find_all(text=True):
            if any(p.name in blacklist for p in txt.parents):
                continue
            nodes = []
            start = 0
            for m in regex.finditer(txt):
                nodes.append(txt[start:m.start()])
                nodes.append(repl(m))
                start = m.end()
            if not nodes:
                continue
            nodes.append(txt[start:])
            parent = txt.parent
            ii = parent.contents.index(txt)
            txt.extract()
            for offset, node in enumerate(nodes):
                parent.insert(ii+offset, node)

    def link_repl(m):
        a = soup.new_tag('a', href=(m.group(1) or 'http://') + m.group(2))
        a.string = m.group(2)
        return a

    blacklist = ('a', 'script', 'pre', 'code', 'embed', 'object',
                 'audio', 'video')
    soup = bs4.BeautifulSoup(plain)
    bs4_sub(LINK_RE, link_repl)
    return ''.join(str(t) for t in soup.body.contents) if soup.body else ''


TAG_TO_TYPE = {
    'n': 'note',
    'a': 'article',
    'r': 'reply',
    's': 'share',
    'l': 'like',
    'c': 'checkin',
    'p': 'photo',
    'b': 'bookmark',
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


def resize_image(source, target, side):
    from PIL import Image, ExifTags
    if not os.path.exists(target):
        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        im = Image.open(source)
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
            shutil.copyfile(source, target)
        else:
            im = im.resize((int(origw * ratio), int(origh * ratio)),
                           Image.ANTIALIAS)
            im.save(target)


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


def image_root_path():
    return app.config.get('IMAGE_ROOT_PATH', app.root_path)


def mirror_image(src, side=None):
    """Downloads a remote resource schema://domain/path to
    static/_mirror/domain/path and optionally resizes it to
    static/_mirro/domain/dirname(path)/resized-64/basename(path)
    """
    from .models import get_settings
    site_netloc = urllib.parse.urlparse(get_settings().site_url).netloc
    o = urllib.parse.urlparse(src)
    if not o.netloc or o.netloc == site_netloc and not side:
        return src

    relpath = os.path.join("_mirror", o.netloc, o.path.strip('/'))
    abspath = os.path.join(image_root_path(), app.static_folder, relpath)

    if os.path.exists(abspath):
        pass
    elif os.path.exists(abspath + '.error'):
        return src
    else:
        try:
            download_resource(src, abspath)
        except BaseException as e:
            app.logger.exception(
                "failed to download %s to %s for some reason", src, abspath)
            if not os.path.exists(os.path.dirname(abspath)):
                os.makedirs(os.path.dirname(abspath))
            with open(abspath + '.error', 'w') as f:
                f.write(str(e))
            return src

    if not side:
        return url_for('static', relpath)

    rz_relpath = os.path.join(
        os.path.dirname(relpath), 'resized-' + str(side),
        os.path.basename(relpath))

    if not any(rz_relpath.lower().endswith(ext)
               for ext in ['.gif', '.jpg', '.png']):
        rz_relpath += '.jpg'

    rz_abspath = os.path.join(image_root_path(), app.static_folder, rz_relpath)

    if not os.path.exists(rz_abspath):
        resize_image(abspath, rz_abspath, side)

    return url_for('static', filename=rz_relpath)


def person_to_microcard(contact, nick):
    if contact:
        url = contact.url or url_for('contact_by_name', nick)
        image = contact.image
        if image:
            image = mirror_image(image, 26)
            return '<a class="microcard h-card" href="{}"><img src="{}" />{}</a>'.format(
                url, image, contact.name)
        return '<a class="microcard h-card" href="{}">@{}</a>'.format(
            url, contact.name)
    url = 'https://twitter.com/' + nick
    return '<a href="{}">@{}</a>'.format(url, nick)


def markdown_filter(data, img_path=None, person_processor=person_to_microcard):
    if data is None:
        return ''

    if img_path:
        # replace relative paths to images with absolute
        data = RELATIVE_PATH_RE.sub('[\g<1>](' + img_path + '/\g<2>)', data)

    if person_processor:
        data = process_people(data, person_processor)

    result = markdown(data, extensions=['codehilite', 'fenced_code'])
    result = autolink(result)
    result = smartyPants(result)
    return result


def process_people(data, person_processor):
    from . import db
    from .models import Contact, Nick

    def process_name(m):
        fullname = m.group(1)
        displayname = m.group(2)
        contact = Contact.query.filter_by(name=fullname).first()
        processed = person_processor(contact, displayname)
        if processed:
            return processed
        return displayname

    def process_nick(m):
        name = m.group(1)
        nick = Nick.query.filter(
            db.func.lower(Nick.name) == db.func.lower(name)).first()
        contact = nick and nick.contact
        processed = person_processor(contact, name)
        if processed:
            return processed
        return m.group(0)

    app.logger.debug('in data %s', data)
    data = PEOPLE_RE.sub(process_name, data)
    app.logger.debug('processed names %s', data)
    data = AT_USERNAME_RE.sub(process_nick, data)
    app.logger.debug('processed nicks %s', data)
    return data

    # while True:
    #     m = PEOPLE_RE.search(data, start)
    #     if not m:
    #         break
    #     if not book:
    #         book = AddressBook()
    #     fullname = m.group(1)
    #     displayname = m.group(2) or fullname
    #     replacement = person_processor(fullname, displayname,
    #                                    book.entries.get(fullname, {}),
    #                                    m.start())
    #     data = data[:m.start()] + replacement + data[m.end():]
    #     start = m.start() + len(replacement)
    # return data


def format_as_text(html, link_fn=None):
    if html is None:
        return ''
    soup = bs4.BeautifulSoup(html)

    # replace links with the URL
    for a in soup.find_all('a'):
        if link_fn:
            link_fn(a)
        else:
            a.replace_with(a.get('href') or '[link]')

    # and remove images
    for i in soup.find_all('img'):
        i.hidden = True

    return soup.get_text().strip()


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
    return path.strip('/')


def fetch_html(url):
    """Utility to fetch HTML from an external site. If the Content-Type
    header does not explicitly list a charset, Requests will assume a
    bad one, so we ahve to use 'get_encodings_from_content` to find
    the meta charset or other indications in the actual response body.

    Return a requests.Response
    """
    response = requests.get(url, timeout=30)
    if response.status_code // 2 == 100:
        # requests ignores <meta charset> when a Content-Type header
        # is provided, even if the header does not define a charset
        if 'charset' not in response.headers.get('content-type', ''):
            encodings = requests.utils.get_encodings_from_content(
                response.text)
            if encodings:
                response.encoding = encodings[0]
    else:
        app.logger.warn('failed to fetch url %s. got response %s.',
                        url, response)
    return response


def clean_foreign_html(html):
    return bleach.clean(html, strip=True)


def jwt_encode(obj):
    obj['nonce'] = random.randint(1000000, 2 ** 31)
    return jwt.encode(obj, app.config['SECRET_KEY'])


def jwt_decode(s):
    return jwt.decode(s, app.config['SECRET_KEY'])
