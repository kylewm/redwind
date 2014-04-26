# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


from . import push
from . import app
from . import archive
from .models import Post, acquire_lock

from flask import request, make_response
from werkzeug.exceptions import NotFound

import urllib.parse
import urllib.request
import requests
import json
from .spool import spoolable
import os

from bs4 import BeautifulSoup


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    source = request.form.get('source')
    target = request.form.get('target')
    callback = request.form.get('callback')

    if not source:
        return make_response(
            'webmention missing required source parameter', 400)

    if not target:
        return make_response(
            'webmention missing required target parameter', 400)

    app.logger.debug("Webmention from %s to %s received", source, target)
    process_webmention.spool(source, target, callback)
    return make_response('webmention queued for processing', 202)


@spoolable
def process_webmention(source, target, callback):
    def call_callback(status, reason):
        if callback:
            requests.post(callback, data={
                'source': source,
                'target': target,
                'status': status,
                'reason': reason
            })

    try:
        mentions_path, mention_url, delete, error = do_process_webmention(
            source, target)

        if error or not mentions_path or not mention_url:
            app.logger.warn("Failed to process webmention: %s", error)
            call_callback(400, error)
            return 400, error

        # TODO move this to models
        mentions_path = os.path.join(app.root_path, '_data', mentions_path)
        app.logger.debug("saving mentions to %s", mentions_path)
        with acquire_lock(mentions_path, 30):
            mention_list = []
            if os.path.exists(mentions_path):
                mention_list = json.load(open(mentions_path, 'r'))

            if delete:
                mention_list.remove(mention_url)
            else:
                if mention_url not in mention_list:
                    mention_list.append(mention_url)

            if not os.path.exists(os.path.dirname(mentions_path)):
                os.makedirs(os.path.dirname(mentions_path))

            json.dump(mention_list, open(mentions_path, 'w'), indent=True)
            app.logger.debug("saved mentions to %s", mentions_path)

        Post.update_recent_mentions(mention_url)
        push.handle_new_mentions()

        call_callback(200, 'Success')
        return 200, 'Success'

    except Exception as e:
        app.logger.exception("exception while processing webmention")
        error = "exception while processing webmention {}".format(e)
        call_callback(400, error)
        return 400, error


def do_process_webmention(source, target):
    app.logger.debug("processing webmention from %s to %s", source, target)
    # confirm that target is a valid link to a post
    target_post = find_target_post(target)

    if not target_post:
        app.logger.warn(
            "Webmention could not find target post: %s. Giving up", target)
        return None, None, False, "Webmention could not find target post: {}"\
            .format(target)

    target_urls = (target, target_post.permalink, target_post.short_permalink)
    mentions_path = target_post.mentions_path

    # confirm that source actually refers to the post
    source_response = requests.get(source)
    app.logger.debug('received response from source %s', source_response)

    if source_response.status_code == 410:
        app.logger.debug("Webmention indicates original was deleted")
        return mentions_path, None, True, None

    if source_response.status_code // 100 != 2:
        app.logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return mentions_path, None, False, \
            "Bad response when reading source post: {}, {}"\
            .format(source, source_response)

    source_length = source_response.headers.get('Content-Length')

    if source_length and int(source_length) > 2097152:
        app.logger.warn("Very large source. length=%s", source_length)
        return mentions_path, None, False,\
            "Source is very large. Length={}"\
            .format(source_length)

    link_to_target = find_link_to_target(source, source_response, target_urls)
    if not link_to_target:
        app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return mentions_path, None, False,\
            "Could not find any links from source to target"

    archive.archive_html(source, source_response.text)

    return mentions_path, source, False, None


def find_link_to_target(source_url, source_response, target_urls):
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
        if link_target in target_urls:
            return link


def find_target_post(target_url):
    app.logger.debug("looking for target post at %s", target_url)

    # follow redirects if necessary
    redirect_url = urllib.request.urlopen(target_url).geturl()
    if redirect_url and redirect_url != target_url:
        app.logger.debug("followed redirection to %s", redirect_url)
        target_url = redirect_url

    parsed_url = urllib.parse.urlparse(target_url)

    if not parsed_url:
        app.logger.warn(
            "Could not parse target_url of received webmention: %s",
            target_url)
        return None

    try:
        urls = app.url_map.bind(app.config['SITE_URL'])
        endpoint, args = urls.match(parsed_url.path)
    except NotFound:
        app.logger.warn("Webmention could not find target for %s",
                        parsed_url.path)
        return None

    if endpoint == 'post_by_date':
        post_type = args.get('post_type')
        year = args.get('year')
        month = args.get('month')
        day = args.get('day')
        index = args.get('index')
        post = Post.load_by_date(post_type, year, month, day, index)

    elif endpoint == 'post_by_old_date':
        post_type = args.get('post_type')
        yymmdd = args.get('yymmdd')
        year = int('20' + yymmdd[0:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        post = Post.load_by_date(post_type, year, month, day, index)

    elif endpoint == 'post_by_id':
        dbid = args.get('dbid')
        post = Post.load_by_id(dbid)

    if not post:
        app.logger.warn(
            "Webmention target points to unknown post: {}".format(args)),

    return post
