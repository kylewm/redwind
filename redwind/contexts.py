from . import hooks
from . import util
from .extensions import db
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


def extract_ogp_context(context, doc, url):
    """ Gets Open Graph Protocol data from the given document
        See http://indiewebcamp.com/The-Open-Graph-protocol
    """
    soup = bs4.BeautifulSoup(doc)

    # extract ogp data
    ogp_title = soup.find('meta', {'property': 'og:title'})
    ogp_image = soup.find('meta', {'property': 'og:image'})
    ogp_site = soup.find('meta', {'property': 'og:site_name'})
    ogp_url = soup.find('meta', {'property': 'og:url'})
    ogp_content = soup.find('meta', {'property': 'og:description'})

    # import the title if mf2 didn't get a title *or* content
    if ogp_title and not context.title and not context.content:
        context.title = ogp_title.get('content')

    if ogp_image and not context.author_image:
        context.author_image = ogp_image.get('content')

    if ogp_site and not context.author_name:
        context.author_name = ogp_site.get('content')

    if ogp_url and not context.permalink:
        context.permalink = ogp_url.get('content')

    if ogp_content and not context.content:
        context.content = ogp_content.get('content')
        context.content_plain = ogp_content.get('content')
        # remove the title if they are the same
        if context.title == context.content:
            context.title = None

    return context


def extract_mf2_context(context, doc, url):
    """ Gets Microformats2 data from the given document
    """
    blob = mf2py.Parser(doc=doc, url=url).to_dict()
    if blob:
        current_app.logger.debug('parsed successfully by mf2py: %s', url)
        entry = mf2util.interpret(blob, url)
        if entry:
            current_app.logger.debug(
                'parsed successfully by mf2util: %s', url)
            published = entry.get('published')
            content = util.clean_foreign_html(entry.get('content', ''))
            content_plain = util.format_as_text(
                content, link_fn=lambda a: a)

            title = entry.get('name')
            if title and len(title) > 512:
                # FIXME is there a db setting to do this automatically?
                title = title[:512]
            author_name = entry.get('author', {}).get('name', '')
            author_image = entry.get('author', {}).get('photo')

            permalink = entry.get('url')
            if not permalink or not isinstance(permalink, str):
                permalink = url

            context.url = url
            context.permalink = permalink
            context.author_name = author_name
            context.author_url = entry.get('author', {}).get('url', '')
            context.author_image = author_image
            context.content = content
            context.content_plain = content_plain
            context.published = published
            context.title = title

    return context


def extract_default_context(context, response, url):
    """ Gets default information if not all info is retrieved
    """
    context = Context() if not context else context

    if not context.url or not context.permalink:
        current_app.logger.debug('getting default url info: %s', url)
        context.url = context.permalink = url

    if not context.title and not context.content:
        current_app.logger.debug('getting default title info: %s', url)
        if response:
            html = response.text
            soup = bs4.BeautifulSoup(html)

            if soup.title:
                context.title = soup.title.string

    return context


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
        current_app.logger.debug(
            'checked for pre-existing context for this url: %s', context)

        if not context:
            context = Context()

        context.url = context.permalink = url

        context = extract_mf2_context(
            context=context,
            doc=response.text,
            url=url
        )
        context = extract_ogp_context(
            context=context,
            doc=response.text,
            url=url
        )
    except:
        current_app.logger.exception(
            'Could not fetch context for url %s, received response %s',
            url, response)

    context = extract_default_context(
        context=context,
        response=response,
        url=url
    )

    return context
