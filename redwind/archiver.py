from . import app
from . import util

import datetime
import json
import mf2py
import os
import requests
import requests.utils
import urllib


def url_to_archive_path(url):
    parsed = urllib.parse.urlparse(url)
    path = os.path.join(parsed.scheme,
                        parsed.netloc.strip('/'),
                        parsed.path.strip('/'))
    return os.path.join(app.root_path, '_archive', path)


def url_to_json_path(url):
    return os.path.join(url_to_archive_path(url), 'parsed.json')


def url_to_html_path(url):
    return os.path.join(url_to_archive_path(url), 'raw.html')


def url_to_response_path(url):
    return os.path.join(url_to_archive_path(url), 'response.json')


def archive_url(url):
    response = requests.get(url)
    if response.status_code // 2 == 100:
        # requests ignores <meta charset> when a Content-Type header
        # is provided, even if the header does not define a charset
        if 'charset' not in response.headers.get('content-type', ''):
            encodings = requests.utils.get_encodings_from_content(response.text)
            if encodings:
                response.encoding = encodings[0]

        archive_html(url, response.text)
    else:
        app.logger.warn('failed to fetch url %s. got response %s.', url, response)
    archive_response(url, response)


def archive_html(url, html):
    app.logger.debug('archiving url %s', url)
    hpath = url_to_html_path(url)

    if not os.path.exists(os.path.dirname(hpath)):
        os.makedirs(os.path.dirname(hpath))

    with open(hpath, 'w') as fp:
        fp.write(html)
    blob = mf2py.Parser(doc=html, url=url).to_dict()
    json.dump(blob, open(url_to_json_path(url), 'w'), indent=True)


def load_json_from_archive(url):
    path = os.path.join(url_to_archive_path(url), 'parsed.json')
    #app.logger.debug("checking archive for %s => %s", url, path)

    if os.path.exists(path):
        #app.logger.debug("path exists, loading %s", path)
        return json.load(open(path, 'r'))
    app.logger.debug("archive path does not exist %s", path)
    return None


def archive_response(url, response):
    app.logger.debug('archiving response %s', response)
    rpath = url_to_response_path(url)

    if not os.path.exists(os.path.dirname(rpath)):
        os.makedirs(os.path.dirname(rpath))

    blob = {
        'status_code': response.status_code,
        'received': util.isoformat(datetime.datetime.utcnow()),
        'headers': dict(response.headers.items())
    }
    json.dump(blob, open(rpath, 'w'), indent=True)


def load_response(url):
    path = url_to_response_path(url)
    if os.path.exists(path):
        return json.load(open(path, 'r'))
    return None
