from .. import hooks
from ..tasks import queue
import requests
from flask import url_for, current_app
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def register(app):
    #app.register_blueprint(push)
    hooks.register('post-saved', send_notifications)


def send_notifications(post, args):
    if not post.hidden and not post.draft:
        queue.enqueue(
            publish, url_for('views.index', _external=True),
            current_app.config)
        queue.enqueue(
            publish, url_for('views.index', feed='atom', _external=True),
            current_app.config)


def publish(url, app_config):
    publish_url = app_config.get('PUSH_HUB')
    if publish_url:
        logger.debug("sending PuSH notification to %s", url)
        data = {'hub.mode': 'publish', 'hub.url': url}
        response = requests.post(publish_url, data)
        if response.status_code == 204:
            logger.info('successfully sent PuSH notification. %r %r',
                        response, response.text)
        else:
            logger.warn('unexpected response from PuSH hub %r %r',
                        response, response.text)
