from . import app
from . import models
from . import views
import os
import json
from operator import attrgetter, itemgetter


def regenerate():
    posts = []
    mentions = []

    basedir = os.path.join(app.root_path, '_data')
    for post_type in models.POST_TYPES:
        for root, dirs, files in os.walk(os.path.join(basedir, post_type)):
            for filen in files:
                index, ext = os.path.splitext(filen)
                postpath = os.path.join(os.path.relpath(root, basedir), index)
                post = models.Post.load(postpath)
                if not post:
                    continue

                posts.append({
                    'type': post_type,
                    'published': models.format_date(post.pub_date),
                    'draft': post.draft,
                    'deleted': post.deleted,
                    'hidden': post.hidden,
                    'path': postpath,
                })

                for mention in post.mentions:
                    # TODO move MentionProxy to models?
                    proxy = views.MentionProxy(post, mention)
                    mentions.append((post.path, mention,
                                     models.format_date(
                                         proxy.pub_date or post.pub_date)))

    # find the 30 most recent mentions
    mentions.sort(key=itemgetter(2), reverse=True)
    recent_mentions = [{
        'mention': mention,
        'post': post_path,
    } for post_path, mention, pub_date in mentions[:30]]

    models.filter_empty_keys(posts)
    blob = {
        'posts': posts,
        'mentions': recent_mentions,
    }
    json.dump(blob, open(os.path.join(basedir, 'metadata.json'), 'w'))


def load():
    basedir = os.path.join(app.root_path, '_data')
    blob = json.load(open(os.path.join(basedir, 'metadata.json')))

    page = 1
    per_page = 30

    posts = blob['posts']

    posts.sort(key=lambda x: x.get('published'), reverse=True)

    start = (page-1) * per_page
    end = start + per_page

    #for post in posts[start:end]:
    #    print(json.dumps(post, indent=True))

    #mentions = blob['mentions']
    #print(json.dumps(mentions, indent=True))
