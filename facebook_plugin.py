from app import app, db
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for
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


class FacebookClient:
    def __init__(self, app):
        self.app = app

    def handle_new_or_edit(self, post):
        app.logger.debug('publishing to facebook')

        actions = {'name': 'See Original',
                   'link': post.permalink}
        privacy = {'value': 'EVERYONE'}

        post_args = {'access_token': post.author.facebook_access_token,
                     'name': post.title,
                     'message': post.content,
                     'link': post.repost_source,
                     'actions': json.dumps(actions),
                     'privact': json.dumps(privacy)}

        response = requests.post('https://graph.facebook.com/me/feed',
                                 data=post_args)
        if 'json' in response.headers['content-type']:
            result = response.json()

        app.logger.debug('published to facebook. response {}'.format(result))
        if result:
            post.facebook_post_id = result['id']
