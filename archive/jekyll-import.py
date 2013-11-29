
import os
import os.path
import re
import yaml
from api import slugify
import datetime
import json
import csv 

from app import db
from models import *

db.session.rollback()
db.drop_all()
db.create_all()

kyle = User("kyle", "kyle.mahan@gmail.com", "shakira")

db.session.add(kyle)

posts = []
for root, dirs, files in os.walk("/home/kmahan/Projects/kylewm.com/_posts"):
    for file in files:
        postfile = os.path.join(root, file)
        with open(postfile) as f:
            text = f.read()
            m = re.match("---\n(.*?)---\n(.*)", text, re.MULTILINE | re.DOTALL)
            meta = yaml.load(m.group(1))
            meta['content'] = m.group(2)
            posts.append(meta)


all_tags = set()
for page in posts:
    if 'tags' in page:
        tags = page['tags']
        for tag in tags:
            all_tags.update(tags)

tags_by_name = {}
for name in all_tags:
    tag = Tag(name)
    tags_by_name[name] = tag
    db.session.add(tag)

for page in posts:
    title = page['title'].strip()
    #print("processing: " + title)
    slug = page.get('slug') or slugify(title)
    content = page['content'].strip()
    post_type = 'article'
    content_format = 'markdown'
    datestr = page['date']
    date = datestr if isinstance(datestr, datetime.date) \
           else datetime.datetime.strptime(datestr, "%Y-%m-%dT%H:%M")
    
    post = Post(title, slug, content, post_type, content_format, kyle, date)
    if 'tags' in page:
        post.tags += [ tags_by_name[name] for name in page['tags'] ]
    db.session.add(post)

db.session.commit()
