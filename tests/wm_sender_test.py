import pytest
from redwind.models import Post
from redwind.plugins import wm_sender
from redwind import db


def test_queue_wm_sender(client, auth, mocker):
    enqueue = mocker.patch('redwind.queue.enqueue')
    client.post('/save_new', data={
        'post_type': 'note',
        'content': 'Some content',
        'in-reply-to': 'http://target/post/url',
    })
    post = Post.query.first()
    enqueue.assert_called_with(wm_sender.do_send_webmentions, post.id)


def test_send_wms(client, mocker):
    poster = mocker.patch('requests.post')
    mocker.patch('urllib.request.urlopen')

    post = Post('note')
    post.content = 'This note links to [wikipedia](https://en.wikipedia.org)'
    post.content_html \
        = 'This note links to <a href="https://en.wikipedia.org">wikipedia</a>'
    post.path = '2014/11/wm-sender-test'
    post.in_reply_to = ['http://target/post/url']
    db.session.add(post)
    db.session.commit()

    wm_sender.do_send_webmentions(post.id)

    poster.assert_called_with(data={'source': post.permalink,
                                    'target': 'http://target/post/url'})
    poster.assert_called_with(data={'source': post.permalink,
                                    'target': 'https://en.wikipedia.org'})
