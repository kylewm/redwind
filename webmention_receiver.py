from app import app, db
from models import Post, Mention
from flask import make_response
import urllib.parse
import requests

from bs4 import BeautifulSoup


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

    to_target_rels = link_to_target.get('rel', [])
    to_target_classes = link_to_target.get('class', [])

    if ('in-reply-to' in to_target_rels or
            'u-in-reply-to' in to_target_classes):
        mention_type = 'reply'
    elif ('u-like' in to_target_classes
          or 'u-like-of' in to_target_classes):
        mention_type = 'like'
    elif ('u-repost' in to_target_classes
          or 'u-repost-of' in to_target_classes):
        mention_type = 'repost'
    else:
        mention_type = 'reference'

    app.logger.debug("Webmention from %s to %s, verified (%s).",
                     source, target, mention_type)

    soup = BeautifulSoup(source_response.text)
    hentry = soup.find(class_="h-entry")

    if not hentry:
        app.logger.warn(
            "Webmention could not find h-entry on source page: %s. Giving up",
            source)
        return None

    permalink = extract_permalink(hentry)
    source_content = extract_source_content(hentry)
    author_name, author_url, author_image = determine_author(soup, hentry)

    mention = Mention(source, permalink, target_post,
                      source_content, mention_type,
                      author_name, author_url, author_image)
    db.session.add(mention)
    db.session.commit()

    return make_response("Received mention, thanks!")


def extract_permalink(hentry):
    permalink = hentry.find(class_='u-url')
    if permalink:
        app.logger.debug('webmention, original source: found permalink: {}'
                         .format(permalink))
        permalink_url = permalink.get('href') or permalink.text
        return permalink_url


def determine_author(soup, hentry):
    pauthor = hentry.find(class_='p-author')
    if pauthor:
        if 'h-card' in pauthor['class']:
            return parse_hcard_for_author(pauthor)
        return pauthor.text, pauthor.get('href'), None

    # use top-level h-card
    hcard = soup.find(class_='h-card')
    if hcard:
        return parse_hcard_for_author(hcard)

    # use page title
    title = soup.find('title')
    if title:
        return title.text, None, None


def parse_hcard_for_author(hcard):
    pname = hcard.find(class_='p-name')
    if pname:
        author = pname.text
    else:
        author = hcard.text

    uurl = hcard.find(class_='u-url')
    if uurl:
        url = uurl.get('href', uurl.text)
    else:
        url = hcard.get('href')

    uphoto = hcard.find(class_='u-photo')
    if uphoto:
        img = uphoto.get('src') or uphoto.get('href')

    return author, url, img


def extract_source_content(hentry):
    econtent = hentry.find(class_='e-content')
    if econtent:
        return econtent.text
    pname = hentry.find(class_='p-name')
    if pname:
        return pname.text
    return hentry.text


def find_link_to_target(source_url, source_response, target_url):
    if source_response.status_code // 2 != 100:
        app.logger.warn(
            "Received unexpected response from webmention source: %s",
            source_response.text)
        return None

    # Don't worry about Microformats for now; just see if there is a
    # link anywhere that points back to the target
    soup = BeautifulSoup(source_response.text)
    for link in soup.find_all(['a', 'link']):
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
    if endpoint != 'post_by_date':
        app.logger.warn("Webmention target is not a post: %s", parsed_url.path)
        return None

    post_type = args.get('post_type')
    year = args.get('year')
    month = args.get('month')
    day = args.get('day')
    index = args.get('index')

    post = Post.lookup_post_by_date(post_type, year, month, day, index)

    if not post:
        app.logger.warn(
            "Webmention target points to unknown post: %s, %s, %d",
            post_type, date_str, date_index)

    return post
