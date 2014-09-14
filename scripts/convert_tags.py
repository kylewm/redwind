from redwind import db
from redwind.models import Post, Tag

db.create_all()

for post in Post.query.all():
    print('processing post', post.path, post.tags)
    newtags = []
    for tag in post.tags:
        newtag = Tag.query.filter_by(name=tag).first()
        if not newtag:
            newtag = Tag(tag)
            db.session.add(newtag)
        newtags.append(newtag)

    print('setting tags', newtags)
    post.newtags = newtags

db.session.commit()
