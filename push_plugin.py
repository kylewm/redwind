import requests

class PushClient:
    def __init__(self, app):
        self.app = app

    def handle_new_or_edit(self, post):
        data = { 'hub.mode' : 'publish', 
                 'hub.url' : 'http://kylewm.com/all.atom' }
        response = requests.post('https://pubsubhubbub.appspot.com/', data)
        if response.status_code == 204:
            self.app.logger.info('successfully sent PuSH notification')
