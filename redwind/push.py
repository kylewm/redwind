from . import app
from . import queue
#from .spool import spoolable
import requests


def send_notifications(post):
    site_url = app.config['SITE_URL']
    if post.post_type in ('article', 'note', 'share'):
        publish.delay(site_url + '/updates.atom')
    if post.post_type == 'article':
        publish.delay(site_url + '/articles.atom')
    publish.delay(site_url + '/all.atom')


def handle_new_mentions():
    site_url = app.config['SITE_URL']
    publish.delay(site_url + '/mention.atom')


@queue.queueable
def publish(url):
    publish_url = app.config['PUSH_HUB']
    app.logger.debug("sending PuSH notification to %s", url)
    data = {'hub.mode': 'publish', 'hub.url': url}
    response = requests.post(publish_url, data)
    if response.status_code == 204:
        app.logger.info('successfully sent PuSH notification')
    else:
        app.logger.warn('unexpected response from PuSH hub %s',
                        response)
