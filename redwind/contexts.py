from . import app
from . import archiver
from . import db
from . import hooks
from . import queue
from . import util
from .models import Post

from .models import Context
import bs4
import bleach
import itertools
import mf2util


def fetch_contexts(post):
    for url in post.in_reply_to:
        do_fetch_context.delay(post.path, 'reply_contexts', url)

    for url in post.repost_of:
        do_fetch_context.delay(post.path, 'repost_contexts', url)

    for url in post.like_of:
        do_fetch_context.delay(post.path, 'like_contexts', url)

    for url in post.bookmark_of:
        do_fetch_context.delay(post.path, 'bookmark_contexts', url)


@queue.queueable
def do_fetch_context(post_path, context_attr, url):
    app.logger.debug("fetching url %s", url)
    context = create_context(url)
    if context:
        post = Post.load_by_path(post_path)
        old_contexts = getattr(post, context_attr)
        new_contexts = []

        for old in old_contexts:
            if old.url == url:
                db.session.delete(old)
            else:
                new_contexts.append(old)

        db.session.add(context)
        new_contexts.append(context)

        setattr(post, context_attr, new_contexts)
        db.session.commit()

def create_context(url):
    for context in hooks.fire('create-context', url):
        if context:
            return context

    archiver.archive_url(url)

    context = None
    blob = archiver.load_json_from_archive(url)
    if blob:
        entry = mf2util.interpret(blob, url)
        if entry:
            published = entry.get('published')
            content = entry.get('content', '')
            content_plain = util.format_as_text(content)

            title = entry.get('name', 'a post')
            author_name = entry.get('author', {}).get('name', '')
            author_image = entry.get('author', {}).get('photo')

            permalink = entry.get('url')
            if not permalink or not isinstance(permalink, str):
                permalink = url

            context = Context()
            context.url = url
            context.permalink = permalink
            context.author_name = author_name
            context.author_url = entry.get('author', {}).get('url', '')
            context.author_image = author_image
            context.content = content
            context.content_plain = content_plain
            context.published = published
            context.title = title

    if not context:
        context = Context()
        context.url = context.permalink = url
        html = archiver.load_html_from_archive(url)
        soup = bs4.BeautifulSoup(html)
        if soup.title:
            context.title = soup.title.string

    return context
