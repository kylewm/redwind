import os
import json
from redwind import app
from redwind.models import Post, Mention


if __name__ == '__main__':
    mentions = []
    for post in Post.iterate_all():
        for mention in post.mentions:
            if not mention.deleted:
                mentions.append((post, mention))

    def sortkey(pair):
        post, mention = pair
        return mention.pub_date, post.pub_date

    mentions.sort(key=sortkey, reverse=True)

    recent_mentions = []
    for pair in mentions[:30]:
        post, mention = pair
        obj = {
            'post': {
                'title': post.title or post.content,
                'permalink': post.permalink
            },
            'mention': mention.to_json()
        }
        recent_mentions.append(obj)

    json.dump(recent_mentions,
              open(os.path.join(app.root_path, '_data/recent_mentions'), 'w'),
              indent=True)
