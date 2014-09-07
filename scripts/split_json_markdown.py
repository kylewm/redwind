import json
import os
from redwind.models import Metadata

mdata = Metadata()

for post in mdata.iterate_all_posts():
    print(post.path)
    parentdir = post._get_fs_path(post.path)
    json_filename = os.path.join(parentdir, 'data.json')
    content_filename = os.path.join(parentdir, 'content.md')

    if not os.path.exists(parentdir):
        os.makedirs(parentdir)

    with open(json_filename, 'w') as f:
        json.dump(post.to_json_blob(), f, indent=True)

    with open(content_filename, 'w') as f:
        if post.content:
            f.write(post.content)
