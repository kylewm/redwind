from flask import url_for, current_app, Config
from redwind import hooks
from redwind.tasks import get_queue
import requests


def register(app):
    #app.register_blueprint(push)
    hooks.register('post-saved', send_notifications)


def send_notifications(post, args):
    if not post.hidden and not post.draft and 'PUSH_HUB' in current_app.config:
        urls = [
            url_for('views.index', _external=True),
            url_for('views.index', feed='atom', _external=True),
        ]
        get_queue().enqueue(publish, urls, current_app.config['PUSH_HUB'])


def publish(urls, push_hub):
    if push_hub:
        print('sending PuSH notification to', urls)
        data = {'hub.mode': 'publish', 'hub.url': urls}
        response = requests.post(push_hub, data)
        if response.status_code == 204:
            print('successfully sent PuSH notification.',
                  response, response.text)
        else:
            print('unexpected response from PuSH hub',
                  response, response.text)
