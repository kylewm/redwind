from . import app
from . import db
from . import hooks
from . import util
from .models import Post
from .models import Context
import bs4
import mf2py
import mf2util
from flask.ext.login import current_user


def fetch_contexts(post):
    user_domain = current_user.domain
    for url in post.in_reply_to:
        do_fetch_context(post.path, 'reply_contexts', url, user_domain)

    for url in post.repost_of:
        do_fetch_context(post.path, 'repost_contexts', url, user_domain)

    for url in post.like_of:
        do_fetch_context(post.path, 'like_contexts', url, user_domain)

    for url in post.bookmark_of:
        do_fetch_context(post.path, 'bookmark_contexts', url, user_domain)


def do_fetch_context(post_path, context_attr, url, user_domain):
    app.logger.debug("fetching url %s", url)
    context = create_context(url, user_domain)
    if context:
        if not context.id:
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


def create_context(url, user_domain=None):
    for context in hooks.fire('create-context', url, user_domain):
        if context:
            return context

    response = util.fetch_html(url)
    if response.status_code // 100 != 2:
        app.logger.error(
            'Could not fetch context for url %s, received response %s',
            url, response)
        return None

    context = Context.query.filter_by(url=url).first()
    blob = mf2py.Parser(doc=response.text, url=url).to_dict()
    if blob:
        entry = mf2util.interpret(blob, url)
        if entry:
            published = entry.get('published')
            content = util.clean_foreign_html(entry.get('content', ''))
            content_plain = util.format_as_text(content)

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

    if not context:
        context = Context()
        context.url = context.permalink = url
        html = response.text
        soup = bs4.BeautifulSoup(html)
        if soup.title:
            context.title = soup.title.string

    return context
