from .extensions import db
from . import hooks
from . import util

from .models import Context
import bs4
import mf2py
import mf2util

from flask import current_app


def fetch_contexts(post):
    do_fetch_context(post, 'reply_contexts', post.in_reply_to)
    do_fetch_context(post, 'repost_contexts', post.repost_of)
    do_fetch_context(post, 'like_contexts', post.like_of)
    do_fetch_context(post, 'bookmark_contexts', post.bookmark_of)


def do_fetch_context(post, context_attr, urls):
    current_app.logger.debug("fetching urls %s", urls)
    old_contexts = getattr(post, context_attr)
    new_contexts = [create_context(url) for url in urls]

    for old in old_contexts:
        if old not in new_contexts:
            db.session.delete(old)

    for new_context in new_contexts:
        db.session.add(new_context)

    setattr(post, context_attr, new_contexts)
    db.session.commit()


def create_context(url):
    for context in hooks.fire('create-context', url):
        if context:
            return context

    context = None
    response = None
    try:
        response = util.fetch_html(url)
        response.raise_for_status()

        context = Context.query.filter_by(url=url).first()
        current_app.logger.debug('checked for pre-existing context for this url: %s', context)
        blob = mf2py.Parser(doc=response.text, url=url).to_dict()
        if blob:
            current_app.logger.debug('parsed successfully by mf2py: %s', url)
            entry = mf2util.interpret(blob, url)
            if entry:
                current_app.logger.debug('parsed successfully by mf2util: %s', url)
                published = entry.get('published')
                content = util.clean_foreign_html(entry.get('content', ''))
                content_plain = util.format_as_text(
                    content, link_fn=lambda a: a)

                title = entry.get('name')
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
    except:
        current_app.logger.exception(
            'Could not fetch context for url %s, received response %s',
            url, response)

    if not context:
        current_app.logger.debug('Generating default context: %s', url)
        context = Context()
        context.url = context.permalink = url
        if response:
            html = response.text
            soup = bs4.BeautifulSoup(html)
            if soup.title:
                current_app.logger.debug('Found title: %s', soup.title.string)
                context.title = soup.title.string

    return context
