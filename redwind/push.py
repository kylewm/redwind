from . import app
from .spool import spoolable
import requests


def send_notifications(post):
    if post.post_type in ('article', 'note', 'share'):
        publish.spool('http://kylewm.com/updates.atom')
    if post.post_type == 'article':
        publish.spool('http://kylewm.com/articles.atom')
    publish.spool('http://kylewm.com/all.atom')


def handle_new_mentions():
    publish.spool('http://kylewm.com/mention.atom')


@spoolable
def publish(url):
    app.logger.debug("sending PuSH notification to %s", url)
    data = {'hub.mode': 'publish', 'hub.url': url}
    response = requests.post('https://kylewm.superfeedr.com/', data)
    if response.status_code == 204:
        app.logger.info('successfully sent PuSH notification')
    else:
        app.logger.warn('unexpected response from PuSH hub %s',
                        response)
