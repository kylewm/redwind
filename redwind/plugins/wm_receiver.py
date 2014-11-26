from .. import app
from .. import db
from .. import queue
from .. import redis
from .. import util
from ..models import Post, Mention, get_settings
from bs4 import BeautifulSoup
from flask import request, make_response, render_template, url_for
from werkzeug.exceptions import NotFound
from rq.job import Job
from werkzeug.exceptions import NotFound
import datetime
import mf2py
import mf2util
import requests
import urllib.parse
import urllib.request

_app = None


def register():
    pass


@app.route('/webmention', methods=['GET', 'POST'])
def receive_webmention():
    if request.method == 'GET':
        return render_template('webmention.html')

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

    job = queue.enqueue(process_webmention, source, target, callback)
    status_url = url_for('webmention_status', key=job.id, _external=True)

    return make_response(
        render_template('wm_received.html', status_url=status_url), 202)


@app.route('/webmention/status/<key>')
def webmention_status(key):
    job = Job.fetch(key, connection=redis)
    rv = job.result
    if not rv:
        rv = {
            'response_code': 202,
            'status': 'queued',
            'reason': 'Mention has not been processed or status has expired'
        }
    return make_response(
        render_template('wm_status.html', **rv),
        rv.get('response_code', 400))


def process_webmention(source, target, callback):
    def call_callback(result):
        if callback:
            requests.post(callback, data=result)
    with app.app_context():
        try:
            target_post, mention, delete, error = do_process_webmention(
                source, target)

            if error or not target_post or not mention:
                app.logger.warn("Failed to process webmention: %s", error)
                result = {
                    'source': source,
                    'target': target,
                    'response_code': 400,
                    'status': 'error',
                    'reason': error
                }
                call_callback(result)
                return result

            if delete:
                target_post.mentions = [m for m in target_post.mentions if
                                        m.url != source]

            if not delete:
                target_post.mentions.append(mention)

            db.session.commit()
            app.logger.debug("saved mentions to %s", target_post.path)

            result = {
                'source': source,
                'target': target,
                'response_code': 200,
                'status': 'success',
                'reason': 'Deleted' if delete else 'Created'
            }

            call_callback(result)
            return result

        except Exception as e:
            app.logger.exception("exception while processing webmention")
            result = {
                'source': source,
                'target': target,
                'response_code': 400,
                'status': 'error',
                'reason': "exception while processing webmention {}".format(e)
            }
            call_callback(result)
            return result


def do_process_webmention(source, target):
    app.logger.debug("processing webmention from %s to %s", source, target)
    if target and target.strip('/') == get_settings().site_url.strip('/'):
        # received a domain-level mention
        app.logger.debug('received domain-level webmention from %s', source)
        target_post = None
        target_urls = (target,)
        # TODO save domain-level webmention somewhere
    else:
        # confirm that target is a valid link to a post
        target_post = find_target_post(target)

        if not target_post:
            app.logger.warn(
                "Webmention could not find target post: %s. Giving up", target)
            return (None, None, False,
                    "Webmention could not find target post: {}".format(target))
        target_urls = (target, target_post.permalink,)

    if source in target_urls:
        return (None, None, False,
                '{} and {} refer to the same post'.format(source, target))

    # confirm that source actually refers to the post
    source_response = util.fetch_html(source)
    app.logger.debug('received response from source %s', source_response)

    if source_response.status_code == 410:
        app.logger.debug("Webmention indicates original was deleted")
        return target_post, None, True, None

    if source_response.status_code // 100 != 2:
        app.logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return target_post, None, False, \
            "Bad response when reading source post: {}, {}"\
            .format(source, source_response)

    source_length = source_response.headers.get('Content-Length')

    if source_length and int(source_length) > 2097152:
        app.logger.warn("Very large source. length=%s", source_length)
        return target_post, None, False,\
            "Source is very large. Length={}"\
            .format(source_length)

    link_to_target = find_link_to_target(source, source_response, target_urls)
    if not link_to_target:
        app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return target_post, None, False,\
            "Could not find any links from source to target"

    mention = create_mention(target_post, source, source_response)
    return target_post, mention, False, None


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
        # FIXME this is a less-than-perfect fix for hosting from a
        # subdirectory. The url_map may have some clever work-around.
        parsed_site_root = urllib.parse.urlparse(get_settings().site_url)
        site_prefix = parsed_site_root.path
        if site_prefix.endswith('/'):
            site_prefix = site_prefix[:-1]
        if not parsed_url.path.startswith(parsed_site_root.path):
            raise NotFound
        urls = app.url_map.bind(get_settings().site_url)
        path = parsed_url.path[len(site_prefix):]
        app.logger.debug('target path with no prefix %s', path)
        endpoint, args = urls.match(path)
        app.logger.debug('found match for target url %r: %r', endpoint, args)
    except NotFound:
        app.logger.warn("Webmention could not find target for %s",
                        parsed_url.path)
        return None

    post = None
    if endpoint == 'post_by_path':
        year = args.get('year')
        month = args.get('month')
        slug = args.get('slug')
        post = Post.load_by_path('{}/{:02d}/{}'.format(year, month, slug))

    elif endpoint == 'post_by_date':
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


def create_mention(post, url, source_response):
    target_urls = []
    if post:
        base_target_urls = [post.permalink]

        for base_url in base_target_urls:
            target_urls.append(base_url)
            target_urls.append(base_url.replace('https://', 'http://')
                               if base_url.startswith('https://')
                               else base_url.replace('http://', 'https://'))

    blob = mf2py.Parser(doc=source_response.text, url=url).to_dict()
    if not blob:
        app.logger.debug('create_mention: no mf2 in source_response')
        return
    entry = mf2util.interpret_comment(blob, url, target_urls)
    if not entry:
        app.logger.debug('create_mention: mf2util found no comment entry')
        return
    comment_type = entry.get('comment_type')

    content = util.clean_foreign_html(entry.get('content', ''))
    content_plain = util.format_as_text(content)

    published = entry.get('published')
    if not published:
        published = datetime.datetime.utcnow()

    # update an existing mention
    mention = next((m for m in post.mentions if m.url == url), None)
    # or create a new one
    if not mention:
        mention = Mention()
    mention.url = url
    mention.permalink = entry.get('url') or url
    mention.reftype = comment_type[0] if comment_type else 'reference'
    mention.author_name = entry.get('author', {}).get('name', '')
    mention.author_url = entry.get('author', {}).get('url', '')
    mention.author_image = entry.get('author', {}).get('photo')
    mention.content = content
    mention.content_plain = content_plain
    mention.published = published
    mention.title = entry.get('name')
    mention.syndication = entry.get('syndication', [])
    return mention
