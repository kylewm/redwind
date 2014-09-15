from . import app
from datetime import date
from markdown import markdown
from smartypants import smartypants
from flask import url_for
import bs4
import os
import os.path
import re
import requests
import datetime
import unicodedata
import urllib


TWITTER_PROFILE_RE = re.compile(r'https?://(?:www\.)?twitter\.com/(\w+)')
TWITTER_RE = re.compile(r'https?://(?:www\.|mobile\.)?twitter\.com/(\w+)/status(?:es)?/(\w+)')
FACEBOOK_PROFILE_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)')
FACEBOOK_RE = re.compile(r'https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)/\w+/(\w+)')
YOUTUBE_RE = re.compile(r'https?://(?:www.)?youtube\.com/watch\?v=(\w+)')
INSTAGRAM_RE = re.compile(r'https?://instagram\.com/p/(\w+)')

PEOPLE_RE = re.compile(r"\[\[([\w ]+)(?:\|([\w\-'. ]+))?\]\]")
RELATIVE_PATH_RE = re.compile('\[([^\]]*)\]\(([^/)]+)\)')


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
    app.logger.debug("downloading {} to {}".format(url, path))
    response = requests.get(urllib.parse.urljoin(app.config['SITE_URL'], url),
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


LINK_REGEX = r'\bhttps?://([a-zA-Z0-9/\.\-_:;%?@$#&=+]+)'
TWITTER_USERNAME_REGEX = r'(?i)(?<!\w)@([a-z0-9_]+)'
NEW_LINK_REGEX = (
    # optional schema
    r'(?i)\b([a-z]{3,9}://)?'
    # hostname and port
    '([a-z0-9.\-]+[.][a-z]{2,4}(?::\d{2,6})?'
    # path
    '(?:/[a-z0-9\-_.;:$?&%#@()/]*[a-z0-9\-_$?#/])?)'
)


def autolink(plain, twitter_names=True):

    def bs4_sub(regex, repl):
        for txt in soup.find_all(text=True):
            if any(p.name in blacklist for p in txt.parents):
                continue
            nodes = []
            start = 0
            for m in re.finditer(regex, txt):
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

    def twitter_repl(m):
        a = soup.new_tag('a', href='https://twitter.com/' + m.group(1))
        a.string = m.group(0)
        return a

    blacklist = ('a', 'script', 'pre', 'code', 'embed', 'object',
                 'audio', 'video')
    soup = bs4.BeautifulSoup(plain)
    bs4_sub(NEW_LINK_REGEX, link_repl)
    if twitter_names:
        bs4_sub(TWITTER_USERNAME_REGEX, twitter_repl)
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
        if ratio < 1:
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


def mirror_image(src, side=None):
    """Downloads a remote resource schema://domain/path to
    static/_mirror/domain/path and optionally resizes it to
    static/_mirro/domain/dirname(path)/resized-64/basename(path)
    """
    site_netloc = urllib.parse.urlparse(app.config['SITE_URL']).netloc
    o = urllib.parse.urlparse(src)
    if not o.netloc or o.netloc == site_netloc:
        return src

    relpath = os.path.join("_mirror", o.netloc, o.path.strip('/'))
    abspath = os.path.join(app.root_path, app.static_folder, relpath)

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

    rz_abspath = os.path.join(app.root_path, app.static_folder, rz_relpath)

    if not os.path.exists(rz_abspath):
        resize_image(abspath, rz_abspath, side)

    return url_for('static', filename=rz_relpath)


def person_to_microcard(fullname, displayname, entry, pos):
    url = entry.get('url')
    photo = entry.get('photo')
    if url and photo:
        photo_url = mirror_image(photo, 26)
        return '<a class="microcard h-card" href="{}"><img src="{}" />{}</a>'.format(
            url, photo_url, displayname)
    elif url:
        return '<a class="microcard h-card" href="{}">{}</a>'.format(
            url, displayname)

    return displayname


def markdown_filter(data, img_path=None, link_twitter_names=True,
                    person_processor=person_to_microcard):
    if data is None:
        return ''
    
    if img_path:
        # replace relative paths to images with absolute
        data = RELATIVE_PATH_RE.sub('[\g<1>](' + img_path + '/\g<2>)', data)

    if person_processor:
        data = process_people(data, person_processor)

    result = markdown(data, extensions=['codehilite', 'fenced_code'])
    result = autolink(result, twitter_names=link_twitter_names)
    result = smartypants(result)
    return result


def process_people(data, person_processor):
    from .models import AddressBook
    book = None
    start = 0
    while True:
        m = PEOPLE_RE.search(data, start)
        if not m:
            break
        if not book:
            book = AddressBook()
        fullname = m.group(1)
        displayname = m.group(2) or fullname
        replacement = person_processor(fullname, displayname,
                                       book.entries.get(fullname, {}),
                                       m.start())
        data = data[:m.start()] + replacement + data[m.end():]
        start = m.start() + len(replacement)
    return data


def format_as_text(html, remove_imgs=True):
    if html is None:
        return ''
    soup = bs4.BeautifulSoup(html)
    # replace links with the URL
    for a in soup.find_all('a'):
        a.replace_with(a.get('href') or 'link')
    # and images with their alt text
    for i in soup.find_all('img'):
        if remove_imgs:
            i.hidden = True
        else:
            i.replace_with('[{}]'.format(
                i.get('title') or i.get('alt') or 'image'))
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
