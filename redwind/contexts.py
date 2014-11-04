from . import app
from . import db
from . import hooks
from . import util

from .models import Context
import bs4
import mf2py
import mf2util
from flask.ext.login import current_user


def fetch_contexts(post):
    for url in post.in_reply_to:
        do_fetch_context(post, 'reply_contexts', url)

    for url in post.repost_of:
        do_fetch_context(post, 'repost_contexts', url)

    for url in post.like_of:
        do_fetch_context(post, 'like_contexts', url)

    for url in post.bookmark_of:
        do_fetch_context(post, 'bookmark_contexts', url)


def do_fetch_context(post, context_attr, url):
    app.logger.debug("fetching url %s", url)
    context = create_context(url)
    if context:
        if not context.id:
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

    context = None
    response = None
    try:
        response = util.fetch_html(url)
        response.raise_for_status()

        context = Context.query.filter_by(url=url).first()
        blob = mf2py.Parser(doc=response.text, url=url).to_dict()
        if blob:
            entry = mf2util.interpret(blob, url)
            if entry:
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
        app.logger.exception(
            'Could not fetch context for url %s, received response %s',
            url, response)

    if not context:
        context = Context()
        context.url = context.permalink = url
        if response:
            html = response.text
            soup = bs4.BeautifulSoup(html)
            if soup.title:
                context.title = soup.title.string

    return context
