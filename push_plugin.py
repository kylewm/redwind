import requests

class PushClient:
    def __init__(self, app):
        self.app = app

    def publish(self, url):
        data = { 'hub.mode' : 'publish', 'hub.url' : url }
        response = requests.post('https://pubsubhubbub.appspot.com/', data)
        if response.status_code == 204:
            self.app.logger.info('successfully sent PuSH notification')
        else:
            self.app.logger.warn('unexpected response from PuSH hub %s', response)
        
    def handle_new_or_edit(self, post):
        self.publish('http://kylewm.com/all.atom')
        if post.post_type=='article':
            self.publish('http://kylewm.com/articles.atom')
        elif post.post_type=='note':
            self.publish('http://kylewm.com/notes.atom')
            
