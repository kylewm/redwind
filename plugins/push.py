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


from app import app
from models import Post
from flask import request, jsonify
from flask.ext.login import login_required
import requests


@app.route('/api/send_push_notification', methods=['POST'])
@login_required
def send_push_notification():
    try:
        post_id = request.form.get('post_id')
        post = Post.query.filter_by(id=post_id).first()
        handle_new_or_edit(post)
        return jsonify(success=True)

    except Exception as e:
        app.logger.exception('posting to PuSH')
        response = jsonify(success=False,
                           error="Exception while sending PuSH notification {}"
                           .format(e))
        return response


def publish(url):
    app.logger.debug("sending PuSH notification to %s", url)
    data = {'hub.mode': 'publish', 'hub.url': url}
    response = requests.post('https://kylewm.superfeedr.com/', data)
    if response.status_code == 204:
        app.logger.info('successfully sent PuSH notification')
    else:
        app.logger.warn('unexpected response from PuSH hub %s',
                        response)


def handle_new_or_edit(post):
    if post.post_type in ('article', 'note', 'share'):
        publish('http://kylewm.com/all.atom')
    if post.post_type == 'article':
        publish('http://kylewm.com/articles.atom')
    elif post.post_type == 'note':
        publish('http://kylewm.com/notes.atom')


def handle_new_mentions():
    publish('http://kylewm.com/mention.atom')
