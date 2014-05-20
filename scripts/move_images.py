from redwind import app
from redwind.models import Post, Metadata
import re
import os
import shutil

mdata = Metadata()
for post in mdata.iterate_all_posts():
    if not post:
        continue
    for match in re.findall('[\'"\[(](/static/[^"\])]+)', post.content):
        img = match

        if 'teamrobot-js' in img:
            continue

        basepath, filename = os.path.split(img)
        source = os.path.join(app.root_path, img.lstrip('/'))
        target = os.path.join(app.root_path, '_data', post.path, 'files', filename)
        print('img', post.path, img, basepath, filename)
        print('moving', source, '\n    ', target)

        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        try:
            post._writeable = True
            shutil.copy(source, target)
            newpath = os.path.join('/' + post.path, 'files', filename)
            post.content = post.content.replace(img, newpath)
            post.save()
        except:
            print('failed to find', source)


    # look for markdown images or html images
    # for match in re.findall('<img[^>]*src="(.*?)".*?>', post.content):
    #     img = match
    #     print('img', post.path, img)

    # for match in re.findall('!\[.*\]\((.*?)\)', post.content):
    #     img = match
    #     print('![]', post.path, img)
