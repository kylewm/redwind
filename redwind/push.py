# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


from . import app
from .queue import queueable
import requests


def send_notifications(post):
    if post.post_type in ('article', 'note', 'share'):
        publish.delay('http://kylewm.com/updates.atom')
    if post.post_type == 'article':
        publish.delay('http://kylewm.com/articles.atom')

    publish.delay('http://kylewm.com/all.atom')


def handle_new_mentions():
    publish.delay('http://kylewm.com/mention.atom')


@queueable
def publish(url):
    app.logger.debug("sending PuSH notification to %s", url)
    data = {'hub.mode': 'publish', 'hub.url': url}
    response = requests.post('https://kylewm.superfeedr.com/', data)
    if response.status_code == 204:
        app.logger.info('successfully sent PuSH notification')
    else:
        app.logger.warn('unexpected response from PuSH hub %s',
                        response)
