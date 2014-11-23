import urllib


def assert_urls_match(u1, u2):
    p1 = urllib.parse.urlparse(u1)
    p2 = urllib.parse.urlparse(u2)
    assert p1.scheme == p2.scheme
    assert p1.netloc == p2.netloc
    assert p1.path == p2.path
    assert urllib.parse.parse_qs(p1.query) == urllib.parse.parse_qs(p2.query)


class FakeResponse:
    def __init__(self, text='', status_code=200, url=None):
        self.text = text
        self.status_code = status_code
        self.content = text and bytes(text, 'utf8')
        self.url = url
        self.headers = {'content-type': 'text/html'}

    def __repr__(self):
        return 'FakeResponse(status={}, text={}, url={})'.format(
            self.status_code, self.text, self.url)

    def raise_for_status(self):
        pass
