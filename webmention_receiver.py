from app import *
from models import *

from flask import request, redirect, jsonify, abort, make_response
import urllib.parse
import requests

from bs4 import BeautifulSoup


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    source = request.form.get('source')
    target = request.form.get('target')

    app.logger.debug("Webmention from %s to %s received", source, target)

    # confirm that target is a valid link to a post
    target_post = find_target_post(target)

    if not target_post:
        app.logger.warn(
            "Webmention could not find target post: %s. Giving up", target)
        abort(400)

    # confirm that source actually refers to the post
    source_response = requests.get(source)

    if not confirm_source_links_to_target(source, source_response, target):
        app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        abort(400)

    app.logger.debug("Webmention from %s to %s verified", source, target)

    source_content = extract_source_content(source_response)
    mention = Mention(source, target_post, source_content)
    db.session.add(mention)
    db.session.commit()

    return make_response("Successfully processed mention, thanks!")


def extract_source_content(source_response):
    if source_response.status_code == 200:
        soup = BeautifulSoup(source_response.text)
        found = soup.find(attrs={"class": "h-entry"})
        if found:
            return found.text


def confirm_source_links_to_target(source_url, source_response, target_url):
    if source_response.status_code != 200:
        app.logger.warn(
            "Received unexpected response from webmention source: %s",
            source_response.text)
        return None

    soup = BeautifulSoup(source_response.text)
    for link in soup.find_all('a'):
        link_target = link.get('href')
        if link_target == target_url:
            return True


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
