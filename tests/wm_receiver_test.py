import pytest
from testutil import FakeResponse, FakeUrlOpen
from redwind.plugins import wm_receiver
from flask.ext.login import current_user
from flask import current_app


@pytest.fixture
def target_url(client, auth, mocker):
    mocker.patch('redwind.plugins.wm_receiver.get_queue')
    rv = client.post('/save_new', data={
        'post_type': 'note',
        'content': 'This post serves as the webmention target',
        'action': 'publish_quietly',
    })
    assert 302 == rv.status_code
    return rv.location


def test_wm_receipt(client, target_url, mocker):
    get_queue = mocker.patch('redwind.plugins.wm_receiver.get_queue')
    source_url = 'http://foreign/permalink/url'

    assert not current_user.is_authenticated()
    rv = client.post('/webmention', data={'source': source_url,
                                          'target': target_url})
    assert 202 == rv.status_code
    get_queue().enqueue.assert_called_once_with(
        wm_receiver.do_process_webmention, source_url, target_url, None,
        current_app.config)


def test_process_wm(db, client, target_url, mocker):
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

    result = wm_receiver.interpret_mention(source_url, target_url)

    assert result.post.permalink == target_url
    assert result.mentions
    assert result.mentions[0].reftype == 'reply'
    assert result.mention_results[0].create
    assert not result.delete
    assert not result.error
    getter.assert_called_once_with('http://foreign/permalink/url', timeout=30)


def test_process_wm_no_target_post(client, mocker):
    source_url = 'http://foreign/permalink/url'
    target_url = 'http://example.com/buy/cialis'  # possible spam

    urlopen = mocker.patch('urllib.request.urlopen')
    urlopen.return_value = FakeUrlOpen(target_url)  # follows redirects

    assert not current_user.is_authenticated()
    result = wm_receiver.interpret_mention(source_url, target_url)

    assert result.post is None
    assert not result.mentions
    assert not result.delete
    assert result.error.startswith('Webmention could not find target')


def test_process_wm_deleted(client, target_url, mocker):
    source_url = 'http://foreign/permalink/url'

    urlopen = mocker.patch('urllib.request.urlopen')
    getter = mocker.patch('requests.get')

    urlopen.return_value = FakeUrlOpen(target_url)  # follows redirects
    getter.return_value = FakeResponse(status_code=410)

    assert not current_user.is_authenticated()
    result = wm_receiver.interpret_mention(source_url, target_url)

    assert result.post.permalink == target_url
    assert not result.mentions
    assert result.delete is True
    assert result.error is None
    getter.assert_called_once_with('http://foreign/permalink/url', timeout=30)
