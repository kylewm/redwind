from app import db
from models import *

db.session.rollback()
db.drop_all()
db.create_all()

kyle = User("kyle", "kyle.mahan@gmail.com", "shakira")

db.session.add(kyle)

import os
os.chdir("/home/kmahan/Projects/kylewm.com/flask/")

from trader.page import Page

all_tags = set()
for page in Page.all():
    tags = page['tags']
    for tag in tags:
        all_tags.update(tags)

tags_by_name = {}
for name in all_tags:
    tag = Tag(name)
    tags_by_name[name] = tag
    db.session.add(tag)

for page in Page.all():
    slug = page.slug()
    title = page['title']
    body = page.body.strip()
    date = page.date()
    post = Post(title, slug, body, kyle, date)
    post.tags += [ tags_by_name[name] for name in page['tags'] ]
    db.session.add(post)

db.session.commit()
