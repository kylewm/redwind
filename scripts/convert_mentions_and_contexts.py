from redwind import app
from redwind.models import Post, Metadata, Mention, Context
from redwind import archiver
from redwind import util
from flask import url_for
import itertools

import bs4
import mf2util

AUTHOR_PLACEHOLDER = 'img/users/placeholder.png'


def create_mention(post_path, url):
    prod_url = app.config.get('PROD_URL')
    site_url = app.config.get('SITE_URL')
    target_urls = []
    if post:
        base_target_urls = [
            post.permalink,
            post.permalink_without_slug,
            post.short_permalink,
        ] + post.previous_permalinks

        for base_url in base_target_urls:
            target_urls.append(base_url)
            target_urls.append(base_url.replace('https://', 'http://')
                               if base_url.startswith('https://')
                               else base_url.replace('http://', 'https://'))
            # use localhost url for testing if it's different from prod
            if prod_url and prod_url != site_url:
                target_urls.append(base_url.replace(site_url, prod_url))

    blob = archiver.load_json_from_archive(url)
    if not blob:
        return
    entry = mf2util.interpret_comment(blob, url, target_urls)
    if not entry:
        return
    comment_type = entry.get('comment_type')

    content = entry.get('content', '')
    content_plain = util.format_as_text(content)

    published = entry.get('published')
    if not published:
        resp = archiver.load_response(url)
        published = resp and util.isoparse(resp.get('received'))

    if not published:
        published = post.published

    author_name = entry.get('author', {}).get('name', '')
    author_image = entry.get('author', {}).get('photo')

    mention = Mention(post_path)
    mention.url = url
    mention.permalink = entry.get('url') or url
    mention.reftype = comment_type[0] if comment_type else 'reference'
    mention.author_name = author_name
    mention.author_url = entry.get('author', {}).get('url', '')
    mention.author_image = author_image
    mention.content = content
    mention.content_plain = content_plain
    mention.published = published
    mention.title = entry.get('name')
    mention.syndication = entry.get('syndication', [])
    mention.save()
    return mention


def create_context(post_path, url):
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

    context.save()
    return context


with app.test_request_context():

    mdata = Metadata()
    for post in mdata.iterate_all_posts():

        for mention_url in post.mention_urls:
            print('mention', mention_url)
            create_mention(post.path, mention_url)

        for context_url in itertools.chain(
                post.in_reply_to, post.repost_of, post.like_of,
                post.bookmark_of):
            print('context', context_url)
            create_context(post.path, context_url)
