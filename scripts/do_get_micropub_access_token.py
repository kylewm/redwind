#!/bin/python

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, parse_qs


def get_endpoints(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.text)

    return [
        soup.find(None, attrs={'rel': rel})['href']
        for rel in ('authorization_endpoint', 'token_endpoint', 'micropub')
    ]

if __name__ == '__main__':
    url = input('URL: ')
    endpoints = get_endpoints(url)

    params = {
        'me': url,
        'client_id': 'http://example.com/',
        'scope': 'post',
        'redirect_uri': 'https://kylewm.github.io/oob/',
        'state': '123',
    }

    # direct them to the first endpoint
    print('Please visit: ', endpoints[0] + '?' + urlencode(params))

    code = input('IndieAuth code: ')

    params['code'] = code
    r = requests.post(endpoints[1], data=params)

    print('response:', r.text)

    access_token = parse_qs(r.text)['access_token'][0]

    print("curl -i -H 'Authorization: Bearer {}' -d '...'".format(access_token))
