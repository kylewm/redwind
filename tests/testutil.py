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


class FakeUrlOpen:
    def __init__(self, url=None, info=None):
        self.url_ = url
        self.info_ = info

    def __repr__(self):
        return 'FakeUrlOpenResponse(url={})'.format(self.url)

    def geturl(self):
        return self.url_

    def info(self):
        return self.info_


class FakeUrlMetadata:
    def __init__(self, content_type, content_length):
        self.content_type = content_type
        self.content_length = content_length

    def get(self, prop):
        if prop.lower() == 'content-length':
            return self.content_length
        if prop.lower() == 'content-type':
            return self.content_type

    def get_content_maintype(self):
        return self.content_type.split('/')[0]
