import re
import pytest
import requests
from mock import MagicMock


def test_empty_db(client):
    """Make sure there are no articles when the database is empty"""
    rv = client.get('/')
    assert '<article' not in rv.get_data(as_text=True)


def test_create_post(client, auth):
    """Create a simple post as the current user"""
    rv = client.post('/save_new', data={
        'post_type': 'note',
        'content': 'This is a test note'})
    assert 302 == rv.status_code
    assert re.match('.*/\d+/\d+/this-is-a-test-note$', rv.location)
    # follow the redirect
    rv = client.get(rv.location)
    assert 'This is a test note' in rv.get_data(as_text=True)


@pytest.fixture(scope='module')
def silly_posts(client, auth):
    data = [
        {
            'post_type': 'note',
            'content': 'Probably a <i>dumb</i> joke',
            'tags': 'dumbjoke',
        },
        {
            'post_type': 'article',
            'title': 'First interesting article',
            'content': 'Something really thoughtful and interesting',
            'tags': 'thoughtful,interesting',
        },
        {
            'post_type': 'reply',
            'in_reply_to': 'http://foo.com/bar',
            'content': 'This foo article on bar is really great',
        },
        {
            'post_type': 'like',
            'like_of': 'https://mal.colm/reynolds',
            'tags': 'firefly',
        },
        {
            'post_type': 'like',
            'like_of': 'https://buf.fy/summers/',
            'tags': 'buffy',
        },
        {
            'post_type': 'article',
            'title': 'Second interesting article',
            'content': 'With lots of interesting and good content',
            'tags': 'interesting,good',
        },
    ]

    for datum in data:
        rv = client.post('/save_new', data=datum)
        assert 302 == rv.status_code


def test_tagged_posts(client, silly_posts):
    text = client.get('/tag/interesting').get_data(as_text=True)
    assert 'First interesting article' in text
    assert 'Second interesting article' in text


def test_posts_by_type(client, silly_posts):
    text = client.get('/likes').get_data(as_text=True)
    assert re.search('u-like-of.*https://mal\.colm/reynolds', text)
    assert re.search('u-like-of.*https://buf\.fy/summers', text)


def test_posts_atom(client, silly_posts):
    # check the main feed
    rv = client.get('/', query_string={'feed': 'atom'})
    assert 200 == rv.status_code
    assert rv.content_type.startswith('application/atom+xml')
    content = rv.get_data(as_text=True)
    assert 'Probably a &lt;i&gt;dumb&lt;/i&gt; joke' in content
    assert 'First interesting article' in content

    # check the notes feed
    rv = client.get('/notes', query_string={'feed': 'atom'})
    assert 200 == rv.status_code
    assert rv.content_type.startswith('application/atom+xml')
    content = rv.get_data(as_text=True)
    assert 'Probably a &lt;i&gt;dumb&lt;/i&gt; joke' in content
    assert 'First interesting article' not in content


def test_atom_redirects(client):
    rv = client.get('/all.atom')
    assert 302 == rv.status_code
    assert rv.location.endswith('/everything?feed=atom')
    rv = client.get('/updates.atom')
    assert 302 == rv.status_code
    assert rv.location.endswith('/?feed=atom')
    rv = client.get('/articles.atom')
    assert 302 == rv.status_code
    assert rv.location.endswith('/articles?feed=atom')


class FakeRequestsResponse:
    def __init__(self, status_code=200, text=None, url=None):
        self.status_code = status_code
        self.text = text
        self.content = text and bytes(text, 'utf8')
        self.url = url


def test_indieauth_login(client):
    requests.get == MagicMock(return_value=FakeRequestResponse())
    client.get('/login?me=http://example.com')

    # fetches example to look for endpoints
    requests.get.assert_called_with('http://example.com')
