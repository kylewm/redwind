from app import app, db
from flask import request, jsonify
from models import Post, Mention
from werkzeug.exceptions import NotFound
import urllib.parse
import urllib.request
import requests
import push_plugin

from bs4 import BeautifulSoup
import hentry_parser


@app.route('/webmention', methods=["POST"])
def receive_webmention():
    try:
        source = request.form.get('source')
        target = request.form.get('target')

        app.logger.debug("Webmention from %s to %s received", source, target)

        mentions, error = process_webmention(source, target)
        if not mentions:
            app.logger.debug("Failed to process webmention: %s", error)
            response = jsonify(success=False, source=source,
                               target=target, error=error)
            return response

        # de-dup on incoming url
        if mentions:
            for existing in Mention.query.filter_by(
                    post_id=mentions[0].post.id,
                    permalink=mentions[0].permalink).all():
                db.session.delete(existing)

        for mention in mentions:
            db.session.add(mention)

        db.session.commit()

        push_plugin.handle_new_mentions(mentions)
        return jsonify(success=True, source=source, target=target)
    except Exception as e:
        response = jsonify(success=False,
                           error="Exception while receiving webmention {}"
                           .format(e))
        return response


def process_webmention(source, target):
    app.logger.debug("processing webmention from %s to %s", source, target)

    # confirm that target is a valid link to a post
    target_post = find_target_post(target)

    if not target_post:
        app.logger.warn(
            "Webmention could not find target post: %s. Giving up", target)
        return None, "Webmention could not find target post: {}".format(target)

    # confirm that source actually refers to the post
    source_metadata = urllib.request.urlopen(source).info()
    if not source_metadata:
        app.logger.warn("Could not open source URL: %s. Giving up", source)
        return None, "Could not open source URL: {}".format(source)

    source_length = source_metadata.get('Content-Length')
    source_content_type = source_metadata.get_content_maintype()

    if source_content_type and source_content_type != 'text':
        app.logger.warn("Cannot process mention from non-text type %s",
                        source_content_type)
        return None, "Source content type {}. 'text' is required.".format(
            source_content_type)

    if source_length and int(source_length) > 2097152:
        app.logger.warn("Very large source. length=%s", source_length)
        return None, "Source is very large. Length={}".format(source_length)

    source_response = requests.get(source)

    if source_response.status_code // 100 != 2:
        app.logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return None, "Bad response when reading source post: {}, {}".format(
            source, source_response)

    link_to_target = find_link_to_target(source, source_response,
                                         [target, target_post.permalink,
                                          target_post.short_permalink])
    if not link_to_target:
        app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return None, "Could not find any links from source to target"

    hentry = hentry_parser.parse(source_response.text, source)

    if not hentry:
        app.logger.warn(
            "Webmention could not find h-entry on source page: %s. Giving up",
            source)
        return None, "Could not find h-entry in source page"

    reftypes = set()
    for ref in hentry.references:
        if (ref.url == target_post.permalink
                or ref.url == target_post.short_permalink):
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
                          hentry.author and hentry.author.photo,
                          hentry.pub_date)
        mentions.append(mention)

    return mentions, None


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
            "Webmention target points to unknown post: {}".format(args)),

    return post
