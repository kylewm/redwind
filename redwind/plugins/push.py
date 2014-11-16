from .. import hooks
from ..extensions import queue
import requests
from flask import url_for, current_app


def register(app):
    hooks.register('post-saved', send_notifications)


def send_notifications(post, args):
    if not post.hidden and not post.draft:
        queue.enqueue(publish, url_for('views.index', _external=True))
        queue.enqueue(publish, url_for('views.index', feed='atom', _external=True))


def publish(url):
    with current_app.app_context():
        publish_url = current_app.config.get('PUSH_HUB')
        if publish_url:
            current_app.logger.debug("sending PuSH notification to %s", url)
            data = {'hub.mode': 'publish', 'hub.url': url}
            response = requests.post(publish_url, data)
            if response.status_code == 204:
                current_app.logger.info('successfully sent PuSH notification')
            else:
                current_app.logger.warn('unexpected response from PuSH hub %s',
                                        response)
