from . import app
from .models import Post
from .queue import queueable
from .twitter import twitter_client
from .util import hentry_parser
from bs4 import BeautifulSoup
from flask.ext.login import current_user
import requests


def fetch_post_contexts(post):
    do_fetch_post_contexts.delay(post.shortid)


@queueable
def do_fetch_post_contexts(post_id):
    try:
        with Post.writeable(Post.shortid_to_path(post_id)) as post:

            app.logger.debug("fetching replies {}, shares {}, likes {}"
                             .format(post.reply_contexts,
                                     post.share_contexts,
                                     post.like_contexts))

            if post.reply_contexts:
                for reply_ctx in post.reply_contexts:
                    fetch_external_post(reply_ctx)

            if post.share_contexts:
                for share_ctx in post.share_contexts:
                    fetch_external_post(share_ctx)

            if post.like_contexts:
                for like_ctx in post.like_contexts:
                    fetch_external_post(like_ctx)

            post.save()

        return True, 'Success'

    except Exception as e:
        app.logger.exception("failure fetching contexts")
        return False, "exception while fetching contexts {}".format(e)


def fetch_external_post(context):
    from .views import prettify_url

    app.logger.debug("checking twitter for {}".format(context))
    if twitter_client.fetch_external_post(context):
        return True

    app.logger.debug("parsing for microformats {}".format(context))
    response = requests.get(context.source)
    if response.status_code // 2 == 100:
        hentry = hentry_parser.parse(response.text, context.source)
        if hentry:
            context.permalink = hentry.permalink
            context.title = hentry.title
            context.content = hentry.content
            context.content_format = 'html'
            context.author_name = hentry.author.name if hentry.author else ''
            context.author_url = hentry.author.url if hentry.author else ''
            context.author_image = hentry.author.photo if hentry.author else ''
            context.pub_date = hentry.pub_date
            return True

    # get as much as we can without microformats
    soup = BeautifulSoup(response.text)
    title_tag = soup.find('title')
    context.permalink = response.url
    context.title = title_tag.text if title_tag else prettify_url(context.source)
