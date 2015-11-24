from redwind import hooks
from redwind.models import Post
from redwind.tasks import get_queue, async_app_context
from bs4 import BeautifulSoup
import re
import requests
import urllib
from flask import current_app, request, jsonify, Blueprint
from flask.ext.login import login_required


wm_sender = Blueprint('wm_sender', __name__)


def register(app):
    app.register_blueprint(wm_sender)
    hooks.register('post-saved', send_webmentions_on_save)
    hooks.register('post-deleted', send_webmentions_on_delete)
    hooks.register('mention-received', send_webmentions_on_comment)


def send_webmentions_on_save(post, args):
    if args.get('action') in ('save_draft', 'publish_quietly'):
        current_app.logger.debug('skipping webmentions for {}'.format(post.id))
        return

    try:
        current_app.logger.debug("queueing webmentions for {}".format(post.id))
        get_queue().enqueue(do_send_webmentions, post.id, current_app.config)
        return True, 'Success'

    except Exception as e:
        current_app.logger.exception('sending webmentions')
        return False, "Exception while sending webmention: {}"\
            .format(e)


def send_webmentions_on_delete(post, args):
    try:
        current_app.logger.debug("queueing deletion webmentions for %s", post.id)
        get_queue().enqueue(do_send_webmentions, post.id, current_app.config)
        return True, 'Success'

    except Exception as e:
        current_app.logger.exception('sending deletion webmentions')
        return False, "Exception while sending deletion webmention: {}"\
            .format(e)


def send_webmentions_on_comment(post):
    try:
        if post:
            current_app.logger.debug("queueing webmentions for {}".format(post.id))
            get_queue().enqueue(do_send_webmentions, post.id, current_app.config)
        return True, 'Success'

    except Exception as e:
        current_app.logger.exception('sending webmentions')
        return False, "Exception while sending webmention: {}"\
            .format(e)

        
def do_send_webmentions(post_id, app_config):
    with async_app_context(app_config):
        current_app.logger.debug("sending mentions for {}".format(post_id))
        post = Post.load_by_id(post_id)
        return handle_new_or_edit(post)


@wm_sender.route('/send_webmentions', methods=['GET'])
@login_required
def send_webmentions_manually():
    id = request.args.get('id')
    post = Post.load_by_id(id)
    return jsonify({
        'mentions': handle_new_or_edit(post),
    })


def get_source_url(post):
    return post.permalink


def get_target_urls(post):
    target_urls = []
    # send mentions to 'in_reply_to' as well as all linked urls
    target_urls += post.in_reply_to
    target_urls += post.repost_of
    target_urls += post.like_of
    target_urls += post.bookmark_of
    target_urls += [p.url for p in post.people]

    current_app.logger.debug('search post content %s', post.content_html)

    soup = BeautifulSoup(post.content_html)
    for link in soup.find_all('a'):
        link_target = link.get('href')
        if link_target:
            current_app.logger.debug(
                'found link {} with href {}'.format(link, link_target))
            target_urls.append(link_target.strip())

    return target_urls


def get_response(url):
    if url in get_response.cached_responses:
        return get_response.cached_responses[url]
    response = requests.get(url)
    get_response.cached_responses[url] = response
    return response

get_response.cached_responses = {}


def handle_new_or_edit(post):
    target_urls = get_target_urls(post)
    current_app.logger.debug(
        'Sending webmentions to these urls {}'.format(" ; ".join(target_urls)))
    results = []
    for target_url in target_urls:
        results.append(send_mention(post, target_url))
    return results


def send_mention(post, target_url):
    current_app.logger.debug(
        'Looking for webmention endpoint on %s', target_url)

    success, explanation = check_content_type_and_size(target_url)
    if success:
        if supports_webmention(target_url):
            current_app.logger.debug("Site supports webmention")
            success, explanation = send_webmention(post, target_url)

        elif supports_pingback(target_url):
            current_app.logger.debug("Site supports pingback")
            success, explanation = send_pingback(post, target_url)
            current_app.logger.debug(
                'Sending pingback successful: %s', success)

        else:
            current_app.logger.debug("Site does not support mentions")
            success = False
            explanation = 'Site does not support webmentions or pingbacks'

    return {'target': target_url,
            'success': success,
            'explanation': explanation}


def check_content_type_and_size(target_url):
    request = urllib.request.Request(
        target_url, headers={'User-Agent': 'kylewm.com'})
    metadata = urllib.request.urlopen(request).info()
    if not metadata:
        return False, "Could not retrieve metadata for url {}".format(
            target_url)

    content_type = metadata.get_content_maintype()
    content_length = metadata.get('Content-Length')

    if content_type and content_type != 'text':
        return False, "Target content type '{}' is not 'text'".format(
            content_type)

    if content_length and int(content_length) > 2097152:
        return False, "Target content length {} is too large".format(
            content_length)

    return True, None


def supports_webmention(target_url):
    return find_webmention_endpoint(target_url) is not None


def find_webmention_endpoint(target_url):
    current_app.logger.debug(
        'looking for webmention endpoint in %s', target_url)
    response = get_response(target_url)
    current_app.logger.debug(
        'looking for webmention endpoint in headers and body')
    endpoint = (find_webmention_endpoint_in_headers(response.headers)
                or find_webmention_endpoint_in_html(response.text))
    current_app.logger.debug(
        'webmention endpoint %s %s', response.url, endpoint)
    return endpoint and urllib.parse.urljoin(response.url, endpoint)


def find_webmention_endpoint_in_headers(headers):
    if 'link' in headers:
        m = re.search('<(https?://[^>]+)>; rel="webmention"',
                      headers.get('link')) or \
            re.search('<(https?://[^>]+)>; rel="http://webmention.org/?"',
                      headers.get('link'))
        if m:
            return m.group(1)


def find_webmention_endpoint_in_html(body):
    soup = BeautifulSoup(body)
    link = (soup.find('link', attrs={'rel': 'webmention'})
            or soup.find('link', attrs={'rel': 'http://webmention.org/'})
            or soup.find('a', attrs={'rel': 'webmention'}))
    return link and link.get('href')


def send_webmention(post, target_url):
    current_app.logger.debug(
        "Sending webmention from %s to %s",
        get_source_url(post), target_url)

    try:
        endpoint = find_webmention_endpoint(target_url)
        if not endpoint:
            return False, "No webmention endpoint for {}".format(
                target_url)

        payload = {'source': get_source_url(post),
                   'target': target_url}
        headers = {'content-type': 'application/x-www-form-urlencoded',
                   'accept': 'application/json'}
        response = requests.post(endpoint, data=payload, headers=headers)

        #from https://github.com/vrypan/webmention-tools/blob/master/
        #             webmentiontools/send.py
        if response.status_code // 100 != 2:
            current_app.logger.warn(
                "Failed to send webmention for %s. "
                "Response status code: %s, %s",
                target_url, response.status_code, response.text)
            return False, "Status code: {}, Response: {}".format(
                response.status_code, response.text)
        else:
            current_app.logger.debug(
                "Sent webmention successfully to %s. Sender response: %s:",
                target_url, response.text)
            return True, "Successful"

    except Exception as e:
        return False, "Exception while sending webmention {}".format(e)


def supports_pingback(target_url):
    return find_pingback_endpoint(target_url) is not None


def find_pingback_endpoint(target_url):
    response = get_response(target_url)
    endpoint = response.headers.get('x-pingback')
    if not endpoint:
        soup = BeautifulSoup(response.text)
        link = soup.find('link', attrs={'rel': 'pingback'})
        endpoint = link and link.get('href')
    return endpoint


def send_pingback(post, target_url):
    try:
        endpoint = find_pingback_endpoint(target_url)
        source_url = get_source_url(post)

        payload = """\
<?xml version="1.0" encoding="iso-8859-1"?><methodCall>
<methodName>pingback.ping</methodName><params><param>
<value><string>{}</string></value></param><param><value>
<string>{}</string></value></param></params></methodCall>"""
        payload = payload.format(source_url, target_url)
        headers = {'content-type': 'application/xml'}
        response = requests.post(endpoint, data=payload, headers=headers)
        current_app.logger.debug(
            "Pingback to %s response status code %s. Message %s",
            target_url, response.status_code, response.text)

        return True, "Sent pingback successfully"
    except Exception as e:
        return False, "Exception while sending pingback: {}".format(e)
