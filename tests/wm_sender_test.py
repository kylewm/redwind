import pytest
from redwind.models import Post
from redwind.plugins import wm_sender
from redwind import db
from testutil import FakeResponse, FakeUrlOpen, FakeUrlMetadata
import urllib


def test_queue_wm_sender(client, auth, mocker):
    enqueue = mocker.patch('redwind.queue.enqueue')
    client.post('/save_new', data={
        'post_type': 'note',
        'content': 'Some content',
    })
    post = Post.query.first()
    enqueue.assert_called_with(wm_sender.do_send_webmentions, post.id)


def test_send_wms(client, mocker):
    getter = mocker.patch('requests.get')
    poster = mocker.patch('requests.post')
    urlopen = mocker.patch('urllib.request.urlopen')

    post = Post('note')
    post.content = 'This note links to [wikipedia](https://en.wikipedia.org/wiki/Webmention)'
    post.content_html = 'This note links to <a href="https://en.wikipedia.org/wiki/Webmention">wikipedia</a>'
    post.path = '2014/11/wm-sender-test'
    db.session.add(post)
    db.session.commit()

    urlopen.return_value = FakeUrlOpen(
        info=FakeUrlMetadata(content_type='text/html', content_length=256))

    getter.return_value = FakeResponse(text="""<!DOCTYPE html>
    <html>
      <link rel="webmention" href="https://en.wikipedia.org/endpoint">
    </html>""")

    wm_sender.do_send_webmentions(post.id)

    getter.assert_called_with('https://en.wikipedia.org/wiki/Webmention')
    poster.assert_called_with('https://en.wikipedia.org/endpoint', data={
        'source': post.permalink,
        'target': 'https://en.wikipedia.org/wiki/Webmention',
    }, headers={
        'content-type': 'application/x-www-form-urlencoded',
        'accept': 'application/json',
    })
