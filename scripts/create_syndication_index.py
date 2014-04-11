import os
import json
from redwind import app
from redwind.models import Post


if __name__ == '__main__':
    obj = {}
    for post in Post.iterate_all():
        if post.facebook_url:
            obj[post.facebook_url] = post.path
        if post.twitter_url:
            obj[post.twitter_url] = post.path

    with open(os.path.join(app.root_path, '_data/syndication_index'), 'w') as f:
        json.dump(obj, f, indent=True)

