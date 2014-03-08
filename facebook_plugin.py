from app import *
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for

import facebook

@app.route('/admin/authorize_facebook')
@login_required
def authorize_facebook():
    import urllib.parse, urllib.request, json
    
    params = {"client_id" : app.config.get('FACEBOOK_APP_ID'),
              "redirect_uri" : app.config.get('SITE_URL') + '/admin/authorize_facebook',
              "scope" : "publish_stream" }

    code = request.args.get('code')
    if code:
        params["code"] = code
        params["client_secret"] = app.config.get('FACEBOOK_APP_SECRET')
  
        r = urllib.request.urlopen("https://graph.facebook.com/oauth/access_token?" \
                                   + urllib.parse.urlencode(params))
        payload = urllib.parse.parse_qs(r.read())
        access_token = payload[b"access_token"]
        current_user.facebook_access_token = access_token
        db.session.commit()
        return redirect(url_for('settings'))
    else:
        return redirect("https://graph.facebook.com/oauth/authorize?" \
                        + urllib.parse.urlencode(params))


class FacebookClient:
    def __init__(self, app):
        self.app = app
            
    def handle_new_or_edit(self, post):
        graph = facebook.GraphAPI(post.author.facebook_access_token)
        response = graph.put_object("me", "feed", name=post.title, message=post.content, link=post.repost_source, actions=["See Original", post.permalink_url])
        post.facebook_post_id = response['id']

