from . import app
import os
import urllib
import json
import requests
from mf2py.parser import Parser


def load_json_from_archive(url):
    path = os.path.join(url_to_archive_path(url), 'parsed.json')
    #app.logger.debug("checking archive for %s => %s", url, path)

    if os.path.exists(path):
        #app.logger.debug("path exists, loading %s", path)
        return json.load(open(path, 'r'))
    app.logger.debug("archive path does not exist %s", path)
    return None


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


def archive_url(url):
    response = requests.get(url)
    if response.status_code // 2 == 100:
        archive_html(url, response.text)


def archive_html(url, html):
    hpath = url_to_html_path(url)

    if not os.path.exists(os.path.dirname(hpath)):
        os.makedirs(os.path.dirname(hpath))

    with open(hpath, 'w') as fp:
        fp.write(html)
    blob = Parser(doc=html, url=url).to_dict()
    json.dump(blob, open(url_to_json_path(url), 'w'), indent=True)
