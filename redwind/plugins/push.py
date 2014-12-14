from .. import app
from .. import hooks
from .. import queue
import requests
from flask import url_for


def register():
    hooks.register('post-saved', send_notifications)


def send_notifications(post, args):
    if not post.hidden and not post.draft:
        queue.enqueue(publish, url_for('index', _external=True))
        queue.enqueue(publish, url_for('index', feed='atom', _external=True))


def publish(url):
    publish_url = app.config.get('PUSH_HUB')
    if publish_url:
        app.logger.debug("sending PuSH notification to %s", url)
        data = {'hub.mode': 'publish', 'hub.url': url}
        response = requests.post(publish_url, data)
        if response.status_code == 204:
            app.logger.info('successfully sent PuSH notification')
        else:
            app.logger.warn('unexpected response from PuSH hub %s',
                            response)
