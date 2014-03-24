from app import app, db
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for, jsonify
from models import Post
from urllib.parse import urljoin
import views

import requests
import json


@app.route('/admin/authorize_facebook')
@login_required
def authorize_facebook():
    import urllib.parse
    import urllib.request
    redirect_uri = app.config.get('SITE_URL') + '/admin/authorize_facebook'
    params = {'client_id': app.config.get('FACEBOOK_APP_ID'),
              'redirect_uri': redirect_uri,
              'scope': 'publish_stream'}

    code = request.args.get('code')
    if code:
        params['code'] = code
        params['client_secret'] = app.config.get('FACEBOOK_APP_SECRET')

        r = urllib.request.urlopen(
            'https://graph.facebook.com/oauth/access_token?'
            + urllib.parse.urlencode(params))
        payload = urllib.parse.parse_qs(r.read())
        access_token = payload[b'access_token']
        current_user.facebook_access_token = access_token
        db.session.commit()
        return redirect(url_for('settings'))
    else:
        return redirect('https://graph.facebook.com/oauth/authorize?'
                        + urllib.parse.urlencode(params))


@app.route('/api/syndicate_to_facebook', methods=['POST'])
@login_required
def syndicate_to_facebook():
    try:
        post_id = int(request.form.get('post_id'))
        post = Post.query.filter_by(id=post_id).first()
        handle_new_or_edit(post)
        db.session.commit()
        return jsonify(success=True, facebook_post_id=post.facebook_post_id,
                       facebook_permalink=post.facebook_url)
    except Exception as e:
        app.logger.exception('posting to facebook')
        response = jsonify(success=False,
                           error="exception while syndicating to Facebook: {}"
                           .format(e))
        return response


def handle_new_or_edit(post):
    app.logger.debug('publishing to facebook')

    share_link = next((share_context.source for share_context
                       in post.share_contexts), None)

    actions = {'name': 'See Original',
               'link': post.permalink}
    privacy = {'value': 'EVERYONE'}

    img_url = views.get_first_image(post.content, post.content_format)
    if img_url:
        img_url = urljoin(app.config['SITE_URL'], img_url)

    post_args = {'access_token': post.author.facebook_access_token,
                 'name': post.title,
                 'message': views.format_as_text(post.content,
                                                 post.content_format),
                 'link': share_link,
                 'picture': img_url,
                 'actions': json.dumps(actions),
                 'privact': json.dumps(privacy)}

    if post.facebook_post_id:
        response = requests.post('http://graph.facebook.com/{}'
                                 .format(post.facebook_post_id),
                                 data=post_args)
    else:
        response = requests.post('https://graph.facebook.com/me/feed',
                                 data=post_args)

    app.logger.debug("Got response from facebook %s", response)

    if response.status_code // 100 != 2:
        raise RuntimeError("Bad response from Facebook. Status: {}, Content: {}"
                           .format(response.status_code, response.content))

    if 'json' in response.headers['content-type']:
        result = response.json()

    app.logger.debug('published to facebook. response {}'.format(result))
    if result:
        post.facebook_post_id = result['id']
