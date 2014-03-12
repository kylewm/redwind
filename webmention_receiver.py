from app import app, db

from models import Post, Mention
from flask import make_response
from werkzeug.exceptions import NotFound
import urllib.parse
import requests

from bs4 import BeautifulSoup
import hentry_parser


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

    hentry = hentry_parser.parse(source_response.text)

    if not hentry:
        app.logger.warn(
            "Webmention could not find h-entry on source page: %s. Giving up",
            source)
        return None

    reftypes = set()
    for ref in hentry.references:
        if (ref.url == target_post.permalink_url
                or ref.url == target_post.short_permalink_url):
            reftypes.add(ref.reftype)

    # if it's not a reply, repost, or like, it's just a reference
    if not reftypes:
        reftypes.add('reference')

    mentions = []
    for reftype in reftypes:
        mention = Mention(source, hentry.permalink, target_post,
                          hentry.content, reftype,
                          hentry.author and hentry.author.name,
                          hentry.author and hentry.author.url,
                          hentry.author and hentry.author.photo)
        mentions.append(mention)

    return mentions


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
    response = requests.get(target_url)
    # follow redirects if necessary
    if response.status_code // 2 == 100:
        target_url = response.url

    urls = app.url_map.bind(app.config['SITE_URL'])
    parsed_url = urllib.parse.urlparse(target_url)

    if not parsed_url:
        app.logger.warn(
            "Could not parse target_url of received webmention: %s",
            target_url)
        return None

    try:
        endpoint, args = urls.match(parsed_url.path)
    except NotFound:
        app.logger.debug("Webmention could not find target for %s",
                         parsed_url.path)
        return None

    if endpoint == 'post_by_date':
        post_type = args.get('post_type')
        year = args.get('year')
        month = args.get('month')
        day = args.get('day')
        index = args.get('index')
        post = Post.lookup_post_by_date(post_type, year, month, day, index)

    elif endpoint == 'post_by_old_date':
        post_type = args.get('post_type')
        yymmdd = args.get('yymmdd')
        year = int('20' + yymmdd[0:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        post = Post.lookup_post_by_date(post_type, year, month, day, index)

    elif endpoint == 'post_by_id':
        dbid = args.get('dbid')
        post = Post.lookup_post_by_id(dbid)

    if not post:
        app.logger.warn(
            "Webmention target points to unknown post: %s, %s, %d",
            post_type, year, month, day, index)

    return post
