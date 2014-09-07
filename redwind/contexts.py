
from . import app
from . import archiver

from . import hooks
from . import queue
from . import util

from .models import Context
import bs4
import bleach
import itertools
import mf2util


def fetch_contexts(post):
    for url in itertools.chain(post.in_reply_to, post.repost_of,
                               post.like_of, post.bookmark_of):
        do_fetch_context.delay(post.path, url)


@queue.queueable
def do_fetch_context(post_path, url):
    app.logger.debug("fetching url %s", url)
    context = create_context(post_path, url)
    if context:
        for old in Context.load_all(post_path):
            app.logger.debug('checking old context wtih url %s', old.url)
            if old.url == url:
                app.logger.debug('deleting old context')
                old.delete()
        context.save()


def create_context(post_path, url):
    for context in hooks.fire('create-context', post_path, url):
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

            context = Context(post_path)
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
        context = Context(post_path)
        context.url = context.permalink = url
        html = archiver.load_html_from_archive(url)
        soup = bs4.BeautifulSoup(html)
        if soup.title:
            context.title = soup.title.string

    return context
