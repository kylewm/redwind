from webmentiontools.send import WebmentionSend
from bs4 import BeautifulSoup
import logging
import re
import requests
from app import app

class MentionClient:
    def __init__(self):
        self.cached_responses = {}
    
    def get_source_url(self, post):
        return post.permalink_url

    def get_target_urls(self, post):
        target_urls = []

        # send mentions to 'in_reply_to' as well as all linked urls
        if post.in_reply_to:
            target_urls.append(post.in_reply_to)

        if post.repost_source:
            target_urls.append(post.repost_source)

        soup = BeautifulSoup(post.html_content)
        for link in soup.find_all('a'):
            link_target = link.get('href')
            if link_target:
                target_urls.append(link_target)

        return target_urls

    def get_response(self, url):
        if url in self.cached_responses:
            return self.cached_responses[url]
        response = requests.get(url)
        self.cached_responses[url] = response
        return response

    def handle_new_or_edit(self, post):
        for target_url in self.get_target_urls(post):
            self.send_mention(post, target_url)

    def send_mention(self, post, target_url):
        if self.supports_webmention(target_url):
            success = self.send_webmention(post, target_url)
        elif self.supports_pingback(target_url):
            success = self.send_pingback(post, target_url)

    def supports_webmention(self, target_url):
        return self.find_webmention_endpoint(target_url) is not None

    def find_webmention_endpoint(self, target_url):
        response = self.get_response(target_url)
        endpoint = self.find_webmention_endpoint_in_headers(response.headers) or \
                   self.find_webmention_endpoint_in_html(response.text)
        return endpoint
        
    def find_webmention_endpoint_in_headers(self, headers):
        if 'link' in headers:
            m = re.search('<(https?://[^>]+)>; rel="webmention"', headers.get('link')) or \
                re.search('<(https?://[^>]+)>; rel="http://webmention.org/?"', headers.get('link'))
            if m:
                return m.group(1)

    def find_webmention_endpoint_in_html(self, body):
        soup = BeautifulSoup(body)
        link = soup.find('link', attrs={'rel': 'webmention'}) or \
               soup.find('link', attrs={'rel': 'http://webmention.org/'})
        return link and link.get('href')

    def send_webmention(self, post, target_url):
        app.logger.debug( "Sending webmention from %s to %s", self.get_source_url(post), target_url)

        endpoint = self.find_webmention_endpoint(target_url)
        payload = {'source': self.get_source_url(post), 'target': target_url}
        headers = {'content-type': 'application/x-www-form-urlencoded', 'accept': 'application/json'}
        response = requests.post(endpoint, data=payload, headers=headers)
        #from https://github.com/vrypan/webmention-tools/blob/master/webmentiontools/send.py
        if response.status_code / 100 != 2:
            app.logger.warn("Failed to send webmention for %s. Response status code: %s", target_url, response.status_code)
            return False
        else:
            app.logger.debug("Sent webmention successfully to %s. Sender response: %s:", target_url, response.text)
            return True

    def supports_pingback(self, target_url):
        return self.find_pingback_endpoint(target_url) is not None

    def find_pingback_endpoint(self, target_url):
        response = self.get_response(target_url)
        endpoint = response.headers.get('x-pingback')
        if not endpoint:
            soup = BeautifulSoup(response.text)
            link = soup.find('link', attrs={'rel':'pingback'})
            endpoint = link and link.get('href')
        return endpoint
    
    def send_pingback(self, post, target_url):
        endpoint = self.find_pingback_endpoint(target_url)
        source_url = self.get_source_url(post)

        payload = """<?xml version="1.0" encoding="iso-8859-1"?><methodCall><methodName>pingback.ping</methodName><params><param><value><string>{}</string></value></param><param><value><string>{}</string></value></param></params></methodCall>"""\
            .format(source_url, target_url)
        headers = {'content-type': 'application/xml'}
        response = requests.post(endpoint, data=payload, headers=headers)
        app.logger.debug("Pingback to %s response status code %s. Message %s", target_url, response.status_code, response.text)
        return True # TODO detect errors


mention_client = MentionClient()
