import facebook

class FacebookClient:

    def __init__(self, app):
        self.app = app
            
    def handle_new_or_edit(self, post):
        graph = facebook.GraphAPI(post.author.facebook_access_token)
        response = graph.put_object("me", "feed", name=post.title, message=post.content, link=post.repost_source)
        post.facebook_post_id = response['id']

