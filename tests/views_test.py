import re
import pytest
import urllib
import datetime
from redwind.models import User
from testutil import FakeResponse, assert_urls_match
from werkzeug.datastructures import MultiDict



def test_empty_db(client):
    """Make sure there are no articles when the database is empty"""
    rv = client.get('/')
    assert '<article' not in rv.get_data(as_text=True)


def test_create_post(client, auth, mocker):
    """Create a simple post as the current user"""
    mocker.patch('requests.get').return_value = FakeResponse()
    mocker.patch('redwind.queue.enqueue')
    rv = client.post('/save_new', data={
        'post_type': 'note',
        'content': 'This is a test note',
        'action': 'publish_quietly',
    })
    assert 302 == rv.status_code
    assert re.match('.*/\d+/\d+/this-is-a-test-note$', rv.location)
    # follow the redirect
    rv = client.get(rv.location)
    assert 'This is a test note' in rv.get_data(as_text=True)


@pytest.fixture
def silly_posts(client, auth, mocker):
    mocker.patch('requests.get').return_value = FakeResponse()
    mocker.patch('redwind.queue.enqueue')

    data = [
        {
            'post_type': 'note',
            'content': 'Probably a <i>dumb</i> joke',
            'tags': ['dumbjoke'],
        },
        {
            'post_type': 'article',
            'title': 'First interesting article',
            'content': 'Something really thoughtful and interesting',
            'tags': ['thoughtful', 'interesting'],
            'syndication': 'https://twitter.com/kylewm2/status/123456\nhttps://facebook.com/kyle.mahan/status/123456',
        },
        {
            'post_type': 'reply',
            'in_reply_to': 'http://foo.com/bar',
            'content': 'This foo article on bar is really great',
            'tags': ['good'],
        },
        {
            'post_type': 'like',
            'like_of': 'https://mal.colm/reynolds',
            'tags': ['firefly', 'interesting'],
            'hidden': True,
        },
        {
            'post_type': 'like',
            'like_of': 'https://buf.fy/summers/',
            'tags': ['buffy'],
            'hidden': True,
        },
        {
            'post_type': 'article',
            'title': 'Second interesting article',
            'content': 'With lots of interesting and good content',
            'tags': ['interesting', 'good'],
        },
    ]

    for datum in data:
        datum['action'] = 'publish_quietly'
        rv = client.post('/save_new', data=datum)
        assert 302 == rv.status_code


def test_tagged_posts(client, silly_posts):
    text = client.get('/tags/interesting').get_data(as_text=True)
    assert 'First interesting article' in text
    assert 'Second interesting article' in text

def test_posts_by_type(client, silly_posts):
    text = client.get('/likes').get_data(as_text=True)
    assert re.search('u-like-of.*https://mal\.colm/reynolds', text)
    assert re.search('u-like-of.*https://buf\.fy/summers', text)


def test_posts_everything(client, silly_posts):
    text = client.get('/everything').get_data(as_text=True)
    assert 'https://mal.colm/reynolds' in text
    assert 'https://buf.fy/summers' in text


def test_post_permalink(client, silly_posts):
    today = datetime.date.today()
    rv = client.get('/{}/{:02d}/{}'.format(today.year, today.month,
                                           'first-interesting-article'))
    assert 200 == rv.status_code
    content = rv.get_data(as_text=True)
    assert 'fa-twitter' in content
    assert 'Something really thoughtful and interesting' in content
    assert re.search('<a[^>]*class="p-category"[^>]*>thoughtful', content)


def test_posts_atom(client, silly_posts):
    # check the main feed
    rv = client.get('/', query_string={'feed': 'atom'})
    assert 200 == rv.status_code
    assert rv.content_type.startswith('application/atom+xml')
    content = rv.get_data(as_text=True)
    assert 'Probably a &lt;i&gt;dumb&lt;/i&gt; joke' in content
    assert 'First interesting article' in content

    # check the everything feed
    rv = client.get('/everything', query_string={'feed': 'atom'})
    assert 200 == rv.status_code
    assert rv.content_type.startswith('application/atom+xml')
    content = rv.get_data(as_text=True)
    assert 'mal.colm/reynolds' in content  # a hidden post
    assert 'First interesting article' in content

    # check the notes feed
    rv = client.get('/notes', query_string={'feed': 'atom'})
    assert 200 == rv.status_code
    assert rv.content_type.startswith('application/atom+xml')
    content = rv.get_data(as_text=True)
    assert 'Probably a &lt;i&gt;dumb&lt;/i&gt; joke' in content
    assert 'First interesting article' not in content


def test_tag_cloud(client, silly_posts):
    # check the tag cloud
    rv = client.get('/tags')
    assert 200 == rv.status_code
    content = rv.get_data(as_text=True)
    print(content)
    assert re.search('<a[^>]*title="2"[^>]*>good', content)
    assert re.search('<a[^>]*title="3"[^>]*>interesting', content)


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


def test_upload_image(client, mocker):
    import io
    today = datetime.date.today()
    mocker.patch('requests.get')
    mocker.patch('redwind.queue.enqueue')

    rv = client.post('/save_new', data={
        'photo': (open('tests/image.jpg', 'rb'), 'image.jpg', 'image/jpeg'),
        'post_type': 'photo',
        'content': 'High score',
        'action': 'publish_quietly',
    })

    assert rv.status_code == 302
    assert (rv.location == 'http://example.com/{}/{:02d}/high-score'.format(
        today.year, today.month))
    permalink = rv.location

    rv = client.get(permalink)
    assert rv.status_code == 200
    content = rv.get_data(as_text=True)

    assert 'High score' in content
    assert '<img' in content

    rv = client.get(permalink + '/files/image.jpg')
    assert rv.status_code == 200
    # Removed depndency on PIL
    # im = Image.open(io.BytesIO(rv.data))
    # assert im.size[0] > 300 or im.size[1] > 300

    # FIXME resizing depends on an external service now;
    #       we can only test that the proper url is constructed
    # rv = client.get(permalink + '/files/image.jpg',
    #                 query_string={'size': 'small'})
    # assert rv.status_code == 200
    # im = Image.open(io.BytesIO(rv.data))
    # assert im.size[0] <= 300 and im.size[1] <= 300


def test_indieauth_login(app, client, mocker):
    mock_get = mocker.patch('requests.get')
    mock_post = mocker.patch('requests.post')
    mock_login = mocker.patch('flask_login.login_user')
    mock_logout = mocker.patch('flask_login.logout_user')

    mock_get.return_value = FakeResponse('<html></html>')
    rv = client.get('/login?me=http://example.com')

    assert rv.status_code == 302
    assert_urls_match(
        rv.location,
        'https://indieauth.com/auth?' + urllib.parse.urlencode({
            'state': None,
            'me': 'http://example.com',
            'client_id': 'http://example.com',
            'redirect_uri': 'http://localhost/login_callback',
        }))
    mock_get.assert_called_once_with('http://example.com')
    mock_get.reset_mock()

    mock_post.return_value = FakeResponse(urllib.parse.urlencode({
        'me': 'http://example.com',
    }))
    rv = client.get('/login_callback?' + urllib.parse.urlencode({
        'code': 'abc123'
    }))
    assert rv.status_code == 302
    assert rv.location == 'http://localhost/'
    mock_post.assert_called_once_with('https://indieauth.com/auth', data={
        'code': 'abc123',
        'client_id': 'http://example.com',
        'redirect_uri': 'http://localhost/login_callback',
        'state': None,
    })

    mock_login.assert_called_once_with(User('example.com'), remember=True)
    client.get('/logout')
    mock_logout.assert_called_once_with()
