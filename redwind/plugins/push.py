from .. import app
from .. import hooks
from .. import queue
import requests


def register():
    hooks.register('post-saved', send_notifications)


def send_notifications(post):
    site_url = app.config['SITE_URL']
    if post.post_type in ('article', 'note', 'share'):
        publish.delay(site_url + '/updates.atom')
    if post.post_type == 'article':
        publish.delay(site_url + '/articles.atom')
    publish.delay(site_url + '/all.atom')


@queue.queueable
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
