import pytest
from redwind.models import Post
from redwind.plugins import wm_sender
from testutil import FakeResponse, FakeUrlOpen, FakeUrlMetadata


@pytest.fixture
def source_post(app, db):
    post = Post('note')
    post.content = 'This note links to [wikipedia](https://en.wikipedia.org/wiki/Webmention)'
    post.content_html = 'This note links to <a href="https://en.wikipedia.org/wiki/Webmention">wikipedia</a>'
    post.path = '2014/11/wm-sender-test'
    db.session.add(post)
    db.session.commit()
    return post


def test_queue_wm_sender(app, auth, client, mocker):
    enqueue = mocker.patch('redwind.tasks.queue.enqueue')
    client.post('/save_new', data={
        'post_type': 'note',
        'content': 'Some content',
    })
    post = Post.query.first()
    enqueue.assert_called_with(wm_sender.do_send_webmentions,
                               post.id, app.config)


def test_send_wms(mocker, source_post):
    getter = mocker.patch('requests.get')
    poster = mocker.patch('requests.post')
    urlopen = mocker.patch('urllib.request.urlopen')

    urlopen.return_value = FakeUrlOpen(
        info=FakeUrlMetadata(content_type='text/html', content_length=256))

    getter.return_value = FakeResponse(text="""<!DOCTYPE html>
    <html>
      <link rel="webmention" href="https://en.wikipedia.org/endpoint">
    </html>""")

    wm_sender.handle_new_or_edit(source_post)

    getter.assert_called_with('https://en.wikipedia.org/wiki/Webmention')
    poster.assert_called_with('https://en.wikipedia.org/endpoint', data={
        'source': source_post.permalink,
        'target': 'https://en.wikipedia.org/wiki/Webmention',
    }, headers={
        'content-type': 'application/x-www-form-urlencoded',
        'accept': 'application/json',
    })
