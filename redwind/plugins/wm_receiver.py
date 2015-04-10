from ..tasks import (session_scope, queue,)
from .. import util
from ..models import (Post, Mention, get_settings,)
from bs4 import BeautifulSoup
from flask import (
    request, make_response, render_template, url_for, Blueprint, current_app,
)
from werkzeug.exceptions import NotFound
import collections
import datetime
import mf2py
import mf2util
import requests
import urllib.parse
import urllib.request
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

wm_receiver = Blueprint('wm_receiver', __name__)

ProcessResult = collections.namedtuple(
    'ProcessResult', 'post mention create delete error')


def register(app):
    app.register_blueprint(wm_receiver)


@wm_receiver.route('/webmention', methods=['GET', 'POST'])
def receive_webmention():
    if request.method == 'GET':
        return render_template('webmention.jinja2')

    source = request.form.get('source')
    target = request.form.get('target')
    callback = request.form.get('callback')

    if not source:
        return make_response(
            'webmention missing required source parameter', 400)

    if not target:
        return make_response(
            'webmention missing required target parameter', 400)

    logger.debug(
        "Webmention from %s to %s received", source, target)

    job = queue.enqueue(do_process_webmention, source, target, callback,
                        current_app.config, current_app.url_map)
    status_url = url_for('.webmention_status', key=job.id, _external=True)

    return make_response(
        render_template('wm_received.jinja2', status_url=status_url), 202)


@wm_receiver.route('/webmention/status/<key>')
def webmention_status(key):
    rv = queue.fetch_job(key)

    if not rv:
        rv = {
            'response_code': 400,
            'status': 'unknown',
            'reason': 'Job does not exist or its status has expired',
        }

    elif rv == 'queued':
        rv = {
            'response_code': 202,
            'status': 'queued',
            'reason': 'Mention has been queued for processing',
        }

    return make_response(
        render_template('wm_status.jinja2', **rv),
        rv.get('response_code', 400))


def do_process_webmention(source, target, callback, app_config, app_url_map):
    def call_callback(result):
        if callback:
            requests.post(callback, data=result)

    logger.debug('processing webmention using database %s',
                 app_config['SQLALCHEMY_DATABASE_URI'])
    with session_scope(app_config) as session:
        try:
            result = interpret_mention(source, target, app_url_map, session)

            if result.error:
                logger.warn("Failed to process webmention: %s", result.error)
                response = {
                    'source': source,
                    'target': target,
                    'response_code': 400,
                    'status': 'error',
                    'reason': result.error
                }
                call_callback(response)
                return response

            if result.post and result.delete:
                result.post.mentions = [m for m in result.post.mentions if
                                        m.url != source]
            elif result.post and result.mention:
                result.post.mentions.append(result.mention)

            session.commit()
            logger.debug("saved mentions to %s", result.post.path)

            if result.post and result.mention and result.create:
                send_push_notification(result.post, result.mention, app_config)

            response = {
                'source': source,
                'target': target,
                'response_code': 200,
                'status': 'success',
                'reason': 'Deleted' if result.delete
                else 'Created' if result.create
                else 'Updated'
            }

            call_callback(response)
            return response

        except Exception as e:
            logger.exception(
                "exception while processing webmention")
            response = {
                'source': source,
                'target': target,
                'response_code': 400,
                'status': 'error',
                'reason': "exception while processing webmention {}".format(e)
            }
            call_callback(response)
            return response


def send_push_notification(post, mention, app_config):
    if 'PUSHOVER_TOKEN' in app_config and 'PUSHOVER_USER' in app_config:
        token = app_config['PUSHOVER_TOKEN']
        user = app_config['PUSHOVER_USER']
        message = '{} from {}{}'.format(
            mention.reftype, mention.author_name,
            (': ' + mention.content_plain[:256])
            if mention.content_plain else '')

        requests.post('https://api.pushover.net/1/messages.json', data={
            'token': token,
            'user': user,
            'message': message,
            'url': post.permalink,
        })


def interpret_mention(source, target, app_url_map, session=None):
    logger.debug("processing webmention from %s to %s", source, target)
    if target and target.strip('/') == get_settings().site_url.strip('/'):
        # received a domain-level mention
        logger.debug('received domain-level webmention from %s', source)
        target_post = None
        target_urls = (target,)
        # TODO save domain-level webmention somewhere
    else:
        # confirm that target is a valid link to a post
        target_post = find_target_post(target, app_url_map, session)

        if not target_post:
            logger.warn(
                "Webmention could not find target post: %s. Giving up", target)
            return ProcessResult(
                post=None, mention=None, create=False, delete=False,
                error="Webmention could not find target post: {}".format(
                    target))
        target_urls = (target, target_post.permalink,)

    if source in target_urls:
        return ProcessResult(
            post=None, mention=None, create=False, delete=False,
            error='{} and {} refer to the same post'.format(source, target))

    # confirm that source actually refers to the post
    source_response = util.fetch_html(source)
    logger.debug('received response from source %s', source_response)

    if source_response.status_code == 410:
        logger.debug("Webmention indicates original was deleted")
        return ProcessResult(
            post=target_post, mention=None, create=False, delete=True,
            error=None)

    if source_response.status_code // 100 != 2:
        logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return ProcessResult(
            post=target_post, mention=None, create=False, delete=False,
            error="Bad response when reading source post: {}, {}".format(
                source, source_response))

    source_length = source_response.headers.get('Content-Length')

    if source_length and int(source_length) > 2097152:
        logger.warn("Very large source. length=%s", source_length)
        return ProcessResult(
            post=target_post, mention=None, create=False, delete=False,
            error="Source is very large. Length={}".format(source_length))

    link_to_target = find_link_to_target(source, source_response, target_urls)
    if not link_to_target:
        logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return ProcessResult(
            target_post, None, False,
            "Could not find any links from source to target")

    mention = create_mention(target_post, source, source_response)
    return ProcessResult(
        post=target_post, mention=mention, create=not mention.id,
        delete=False, error=None)


def find_link_to_target(source_url, source_response, target_urls):
    if source_response.status_code // 2 != 100:
        logger.warn(
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


def find_target_post(target_url, app_url_map, session=None):
    logger.debug("looking for target post at %s", target_url)

    # follow redirects if necessary
    redirect_url = urllib.request.urlopen(target_url).geturl()
    if redirect_url and redirect_url != target_url:
        logger.debug("followed redirection to %s", redirect_url)
        target_url = redirect_url

    parsed_url = urllib.parse.urlparse(target_url)

    if not parsed_url:
        logger.warn(
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

        urls = app_url_map.bind(get_settings().site_url)
        path = parsed_url.path[len(site_prefix):]
        logger.debug('target path with no prefix %s', path)
        endpoint, args = urls.match(path)
        logger.debug('found match for target url %r: %r',
                     endpoint, args)
    except NotFound:
        logger.warn("Webmention could not find target for %s",
                    parsed_url.path)
        return None

    post = None
    if endpoint == 'views.post_by_path':
        year = args.get('year')
        month = args.get('month')
        slug = args.get('slug')
        post = Post.load_by_path(
            '{}/{:02d}/{}'.format(year, month, slug), session)

    elif endpoint == 'views.post_by_date':
        post_type = args.get('post_type')
        year = args.get('year')
        month = args.get('month')
        day = args.get('day')
        index = args.get('index')
        post = Post.load_by_date(post_type, year, month, day, index, session)

    elif endpoint == 'views.post_by_old_date':
        post_type = args.get('post_type')
        yymmdd = args.get('yymmdd')
        year = int('20' + yymmdd[0:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        post = Post.load_by_date(post_type, year, month, day, index, session)

    elif endpoint == 'views.post_by_id':
        dbid = args.get('dbid')
        post = Post.load_by_id(dbid, session)

    if not post:
        logger.warn(
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
        logger.debug('create_mention: no mf2 in source_response')
        return
    entry = mf2util.interpret_comment(blob, url, target_urls)
    if not entry:
        logger.debug(
            'create_mention: mf2util found no comment entry')
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
    mention.rsvp = entry.get('rsvp')
    return mention
