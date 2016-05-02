from bs4 import BeautifulSoup
from flask import current_app
from flask import request, make_response, render_template, url_for, Blueprint
from redwind import hooks
from redwind import util
from redwind.extensions import db
from redwind.models import Post, Mention, get_settings
from redwind.tasks import get_queue, async_app_context
from werkzeug.exceptions import NotFound
import datetime
import mf2py
import mf2util
import re
import requests
import urllib.parse
import urllib.request

wm_receiver = Blueprint('wm_receiver', __name__)


class MentionResult:
    def __init__(self, mention, create):
        self.mention = mention
        self.create = create


class ProcessResult:
    def __init__(self, post=None, is_person_mention=False, error=None, delete=False):
        self.post = post
        self.is_person_mention = is_person_mention
        self.error = error
        self.delete = delete
        self.mention_results = []

    def add_mention(self, mention, create):
        self.mention_results.append(MentionResult(mention, create))

    @property
    def mentions(self):
        return [r.mention for r in self.mention_results]


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

    current_app.logger.debug(
        "Webmention from %s to %s received", source, target)

    job = get_queue().enqueue(
        do_process_webmention, source, target, callback, current_app.config)
    status_url = url_for('.webmention_status', key=job.id, _external=True)

    return make_response(
        render_template('wm_received.jinja2', status_url=status_url), 202)


@wm_receiver.route('/webmention/status/<key>')
def webmention_status(key):
    job = get_queue().fetch_job(key)

    if not job:
        rv = {
            'response_code': 400,
            'status': 'unknown',
            'reason': 'Job does not exist or its status has expired',
        }

    elif job.result == 'queued':
        rv = {
            'response_code': 202,
            'status': 'queued',
            'reason': 'Mention has been queued for processing',
        }
    else:
        rv = job.result or {}

    return make_response(
        render_template('wm_status.jinja2', **rv),
        rv.get('response_code', 400))


def do_process_webmention(source, target, callback, app_config):
    def call_callback(result):
        if callback:
            requests.post(callback, data=result)
    with async_app_context(app_config):
        try:
            result = interpret_mention(source, target)

            if result.error:
                current_app.logger.warn(
                    'Failed to process webmention: %s', result.error)
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
            elif result.post:
                result.post.mentions.extend(result.mentions)

            elif result.is_person_mention:
                db.session.add_all(result.mentions)

            db.session.commit()
            current_app.logger.debug("saved mentions to %s", result.post.path if result.post else '/')

            hooks.fire('mention-received', post=result.post)
            for mres in result.mention_results:
                if mres.create:
                    send_push_notification(result.post, result.is_person_mention,
                                           mres.mention, app_config)

            response = {
                'source': source,
                'target': target,
                'response_code': 200,
                'status': 'success',
                'reason': 'Deleted' if result.delete
                else 'Created' if any(mres.create for mres
                                      in result.mention_results)
                else 'Updated'
            }

            call_callback(response)
            return response

        except Exception as e:
            current_app.logger.exception(
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


def send_push_notification(post, is_person_mention, mention, app_config):
    # ignore mentions from bridgy
    if mention.url and mention.url.startswith('https://brid-gy.appspot.com/') and not is_person_mention:
        return

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
            'url': post.permalink if post else mention.permalink,
        })


def interpret_mention(source, target):
    current_app.logger.debug(
        'processing webmention from %s to %s', source, target)
    if target and target.strip('/') == get_settings().site_url.strip('/'):
        # received a domain-level mention
        is_person_mention = True
        current_app.logger.debug(
            'received domain-level webmention from %s', source)
        target_post = None
        target_urls = (target,)

    else:
        # confirm that target is a valid link to a post
        is_person_mention = False
        target_post = find_target_post(target)

        if not target_post:
            current_app.logger.warn(
                "Webmention could not find target post: %s. Giving up", target)
            return ProcessResult(
                error="Webmention could not find target post: {}"
                .format(target))
        target_urls = (target, target_post.permalink,)

    if source in target_urls:
        return ProcessResult(
            error='{} and {} refer to the same post'.format(source, target))

    # confirm that source actually refers to the post
    source_response = util.fetch_html(source)
    current_app.logger.debug(
        'received response from source %s', source_response)

    if source_response.status_code == 410:
        current_app.logger.debug("Webmention indicates original was deleted")
        return ProcessResult(post=target_post, delete=True)

    if source_response.status_code // 100 != 2:
        current_app.logger.warn(
            "Webmention could not read source post: %s. Giving up", source)
        return ProcessResult(
            post=target_post,
            error="Bad response when reading source post: {}, {}".format(
                source, source_response))

    source_length = source_response.headers.get('Content-Length')

    if source_length and int(source_length) > 2097152:
        current_app.logger.warn("Very large source. length=%s", source_length)
        return ProcessResult(
            post=target_post,
            error="Source is very large. Length={}".format(source_length))

    status = find_http_equiv_status(source, source_response)
    if status and status == 410:
        current_app.logger.debug("Webmention indicates original was deleted based on http-equiv=status header")
        return ProcessResult(post=target_post, delete=True)

    link_to_target = find_link_to_target(source, source_response, target_urls)
    if not link_to_target:
        current_app.logger.warn(
            "Webmention source %s does not appear to link to target %s. "
            "Giving up", source, target)
        return ProcessResult(
            post=target_post,
            error="Could not find any links from source to target")

    mentions = create_mentions(target_post, source, source_response, is_person_mention)
    if not mentions:
        return ProcessResult(
            post=target_post,
            error="Could not parse a mention from the source")

    result = ProcessResult(
        post=target_post, is_person_mention=is_person_mention)
    for mention in mentions:
        result.add_mention(mention, create=not mention.id)
    return result


def find_http_equiv_status(source, source_response):
    soup = BeautifulSoup(source_response.text)
    meta = soup.find('meta', {
        'http-equiv': re.compile('status', re.IGNORECASE)})
    if meta:
        content = meta.get('content')
        if content:
            try:
                return int(content.split(' ', 1)[0])
            except:
                current_app.logger.warn(
                    'Could not parse http-equiv=status content: %s', content)


def find_link_to_target(source_url, source_response, target_urls):
    if source_response.status_code // 2 != 100:
        current_app.logger.warn(
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
    current_app.logger.debug("looking for target post at %s", target_url)

    # follow redirects if necessary
    redirect_url = urllib.request.urlopen(target_url).geturl()
    if redirect_url and redirect_url != target_url:
        current_app.logger.debug("followed redirection to %s", redirect_url)
        target_url = redirect_url

    parsed_url = urllib.parse.urlparse(target_url)

    if not parsed_url:
        current_app.logger.warn(
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

        urls = current_app.url_map.bind(get_settings().site_url)
        path = parsed_url.path[len(site_prefix):]
        current_app.logger.debug('target path with no prefix %s', path)
        endpoint, args = urls.match(path)
        current_app.logger.debug(
            'found match for target url %r: %r', endpoint, args)
    except NotFound:
        current_app.logger.warn(
            'Webmention could not find target for %s', parsed_url.path)
        return None

    post = None
    if endpoint == 'views.post_by_path':
        year = args.get('year')
        month = args.get('month')
        slug = args.get('slug')
        post = Post.load_by_path(
            '{}/{:02d}/{}'.format(year, month, slug))

    elif endpoint == 'views.post_by_date':
        post_type = args.get('post_type')
        year = args.get('year')
        month = args.get('month')
        day = args.get('day')
        index = args.get('index')
        post = Post.load_by_date(post_type, year, month, day, index)

    elif endpoint == 'views.post_by_old_date':
        post_type = args.get('post_type')
        yymmdd = args.get('yymmdd')
        year = int('20' + yymmdd[0:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        post = Post.load_by_date(post_type, year, month, day, index)

    elif endpoint == 'views.post_by_id':
        dbid = args.get('dbid')
        post = Post.load_by_id(dbid)

    if not post:
        current_app.logger.warn(
            "Webmention target points to unknown post: {}".format(args)),

    return post


def create_mentions(post, url, source_response, is_person_mention):
    # utility function for mf2util
    cached_mf2 = {}

    def fetch_mf2(url):
        if url in cached_mf2:
            return cached_mf2[url]
        p = mf2py.parse(url=url)
        cached_mf2[url] = p
        return p

    target_urls = []
    if post:
        base_target_urls = [post.permalink]

        for base_url in base_target_urls:
            target_urls.append(base_url)
            target_urls.append(base_url.replace('https://', 'http://')
                               if base_url.startswith('https://')
                               else base_url.replace('http://', 'https://'))

    blob = mf2py.parse(doc=source_response.text, url=url)
    cached_mf2[url] = blob

    if not blob:
        current_app.logger.debug('create_mention: no mf2 in source_response')
        return
    entry = mf2util.interpret_comment(
        blob, url, target_urls, fetch_mf2_func=fetch_mf2)
    current_app.logger.debug('interpreted comment: %r', entry)

    if not entry:
        current_app.logger.debug(
            'create_mention: mf2util found no comment entry')
        return
    comment_type = entry.get('comment_type', [])

    to_process = [(entry, url)]
    # process 2nd level "downstream" comments
    if 'reply' in comment_type:
        downstream_cmts = entry.get('comment', [])
        current_app.logger.debug('adding in downstream comments:%d',
                                 len(downstream_cmts))
        for dc in downstream_cmts:
            if dc.get('url'):
                to_process.append((dc, dc.get('url')))

    results = []
    for entry, url in to_process:
        current_app.logger.debug('processing %s %r', url, entry)
        content = util.clean_foreign_html(entry.get('content', ''))
        content_plain = util.format_as_text(content)

        published = entry.get('published')
        if not published:
            published = datetime.datetime.utcnow()

        # update an existing mention
        mention = next((m for m in post.mentions if m.url == url), None)\
                  if post else None

        # or create a new one
        if not mention:
            mention = Mention()
        mention.url = url
        mention.person_mention = is_person_mention
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
        results.append(mention)

    return results
