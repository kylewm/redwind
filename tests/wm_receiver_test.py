import pytest
from testutil import FakeResponse, FakeUrlOpen
from redwind.plugins import wm_receiver
from flask.ext.login import current_user


@pytest.fixture
def target_url(client, auth, mocker):
    mocker.patch('redwind.queue.enqueue')
    rv = client.post('/save_new', data={
        'post_type': 'note',
        'content': 'This post serves as the webmention target',
        'action': 'Publish Quietly',
    })
    assert 302 == rv.status_code
    return rv.location


def test_wm_receipt(client, target_url, mocker):
    enqueue = mocker.patch('redwind.queue.enqueue')
    source_url = 'http://foreign/permalink/url'

    assert not current_user.is_authenticated()
    rv = client.post('/webmention', data={'source': source_url,
                                          'target': target_url})
    assert 202 == rv.status_code
    enqueue.assert_called_once_with(wm_receiver.process_webmention,
                                    source_url, target_url, None)


def test_process_wm(client, target_url, mocker):
    source_url = 'http://foreign/permalink/url'

    urlopen = mocker.patch('urllib.request.urlopen')
    getter = mocker.patch('requests.get')

    urlopen.return_value = FakeUrlOpen(target_url)  # follows redirects
    getter.return_value = FakeResponse("""

    <!DOCTYPE html>
    <html>
      <head></head>
      <body class="h-entry">
        <a href="{}" class="u-in-reply-to">In Reply To</a>
        This is the source of the webmention
        <a href="{}" class="u-url">Permalink</a>
      </body>
    </html>
    """.format(target_url, source_url))

    assert not current_user.is_authenticated()
    target_post, mention, delete, error \
        = wm_receiver.do_process_webmention(source_url, target_url)

    assert target_post.permalink == target_url
    assert mention is not None
    assert mention.reftype == 'reply'
    assert not delete
    assert not error
    getter.assert_called_once_with('http://foreign/permalink/url', timeout=30)


def test_process_wm_no_target_post(client, mocker):
    source_url = 'http://foreign/permalink/url'
    target_url = 'http://example.com/buy/cialis'  # possible spam

    urlopen = mocker.patch('urllib.request.urlopen')
    urlopen.return_value = FakeUrlOpen(target_url)  # follows redirects

    assert not current_user.is_authenticated()
    target_post, mention, delete, error \
        = wm_receiver.do_process_webmention(source_url, target_url)

    assert target_post is None
    assert mention is None
    assert not delete
    assert error.startswith('Webmention could not find target')


def test_process_wm_deleted(client, target_url, mocker):
    source_url = 'http://foreign/permalink/url'

    urlopen = mocker.patch('urllib.request.urlopen')
    getter = mocker.patch('requests.get')

    urlopen.return_value = FakeUrlOpen(target_url)  # follows redirects
    getter.return_value = FakeResponse(status_code=410)

    assert not current_user.is_authenticated()
    target_post, mention, delete, error \
        = wm_receiver.do_process_webmention(source_url, target_url)

    assert target_post.permalink == target_url
    assert not mention
    assert delete is True
    assert error is None
    getter.assert_called_once_with('http://foreign/permalink/url', timeout=30)
