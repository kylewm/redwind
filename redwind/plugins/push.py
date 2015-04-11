from flask import url_for, current_app
from redwind import hooks
from redwind.tasks import get_queue
import requests


def register(app):
    #app.register_blueprint(push)
    hooks.register('post-saved', send_notifications)


def send_notifications(post, args):
    if not post.hidden and not post.draft:
        get_queue().enqueue(
            publish, url_for('views.index', _external=True),
            current_app.config)
        get_queue().enqueue(
            publish, url_for('views.index', feed='atom', _external=True),
            current_app.config)


def publish(url, app_config):
    publish_url = app_config.get('PUSH_HUB')
    if publish_url:
        print('sending PuSH notification to', url)
        data = {'hub.mode': 'publish', 'hub.url': url}
        response = requests.post(publish_url, data)
        if response.status_code == 204:
            print('successfully sent PuSH notification.',
                  response, response.text)
        else:
            print('unexpected response from PuSH hub',
                  response, response.text)
