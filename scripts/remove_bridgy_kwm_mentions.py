import os
import json
from redwind import app
from redwind.models import Post, Metadata


if __name__ == '__main__':
    mdata = Metadata()
    for post in mdata.iterate_all_posts():
        path = os.path.join(app.root_path, '_data', post.mentions_path)
        if os.path.exists(path):
            mentions1 = json.load(open(path, 'r'))
            mentions2 = [m for m in mentions1 if 'bridgy-kwm' not in m]
            if mentions1 != mentions2:
                print('writing', path)
                json.dump(mentions2, open(path, 'w'))
