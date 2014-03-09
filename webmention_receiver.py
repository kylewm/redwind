from app import app, db
from models import Post, Mention
from flask import request, abort, make_response
import urllib.parse
import requests

from bs4 import BeautifulSoup


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    source = request.form.get('source')
    target = request.form.get('target')

    app.logger.debug("Webmention from %s to %s received", source, target)

    success = process_webmention(source, target)
    if not success:
        abort(404)


def process_webmention(source, target):
    app.logger.debug("processing webmention from %s to %s", source, target)
    
    # confirm that source actually refers to the post
    source_response = requests.get(source)

    if source_response.status_code // 100 != 2:
        app.logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return None

    # confirm that target is a valid link to a post
    target_post = find_target_post(target)

    if not target_post:
        app.logger.warn(
            "Webmention could not find target post: %s. Giving up", target)
        return None

    link_to_target = find_link_to_target(source, source_response, target)
    if not link_to_target:
        app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return None

    is_reply = ('in-reply-to' in link_to_target.get('rel', [])
                or 'u-in-reply-to' in link_to_target.get('class', []))

    app.logger.debug("Webmention from %s to %s, verified (%s).",
                     source, target, "reply" if is_reply else "mention")

    soup = BeautifulSoup(source_response.text)
    hentry = soup.find(class_="h-entry")

    if not hentry:
        app.logger.warn(
            "Webmention could not find h-entry on source page: %s. Giving up",
            source)
        return None

    permalink = extract_permalink(hentry)
    source_content = extract_source_content(hentry)
    author_name, author_url = determine_author(soup, hentry)

    mention = Mention(permalink or source, target_post,
                      source_content, is_reply,
                      author_name, author_url)
    db.session.add(mention)
    db.session.commit()

    return make_response("Received mention, thanks!")

def extract_permalink(hentry):
    permalink = hentry.find(class_='u-url')
    if permalink:
        app.logger.debug('webmention, original source: found permalink: {}'.format(permalink))
        permalink_url = permalink.get('href') or permalink.text
        return permalink_url

def determine_author(soup, hentry):
    pauthor = hentry.find(class_='p-author')
    if pauthor:
        if 'h-card' in pauthor['class']:
            return parse_hcard_for_author(pauthor)
        return pauthor.text, pauthor.get('href')

    # use top-level h-card
    hcard = soup.find(class_='h-card')
    if hcard:
        return parse_hcard_for_author(hcard)

    # use page title
    title = soup.find('title')
    if title:
        return title.text, None


def parse_hcard_for_author(hcard):
    pname = hcard.find(class_='p-name')
    if pname:
        author = pname.text
    else:
        author = hcard.text
    uurl = hcard.find(class_='u-url')
    if uurl:
        url = uurl.get('href') or uurl.text
    else:
        url = hcard.get('href')
    return author, url


def extract_source_content(hentry):
    econtent = hentry.find(class_='e-content')
    if econtent:
        return econtent.text
    pname = hentry.find(class_='p-name')
    if pname:
        return pname.text
    return hentry.text


def find_link_to_target(source_url, source_response, target_url):
    if source_response.status_code != 200:
        app.logger.warn(
            "Received unexpected response from webmention source: %s",
            source_response.text)
        return None

    soup = BeautifulSoup(source_response.text)
    for link in soup.find_all('a'):
        link_target = link.get('href')
        if link_target == target_url:
            return link


def find_target_post(target_url):
    urls = app.url_map.bind(app.config['SITE_URL'])
    parsed_url = urllib.parse.urlparse(target_url)

    if not parsed_url:
        app.logger.warn(
            "Could not parse target_url of received webmention: %s",
            target_url)
        return None

    endpoint, args = urls.match(parsed_url.path)
    if endpoint != 'post_by_id':
        app.logger.warn("Webmention target is not a post: %s", parsed_url.path)
        return None

    if not 'post_id' in args:
        app.logger.warn(
            "Webmention target is not a valid permalink: %s", target_url)
        return None

    post_id = args['post_id']
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        app.logger.warn(
            "Webmention target points to unknown post_id: %s", post_id)

    return post
