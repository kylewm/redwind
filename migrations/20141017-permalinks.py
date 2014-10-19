from redwind import app, db, util
from redwind.models import Post
import itertools

#db.engine.execute('alter table post add column historic_path varchar(256)')
#db.engine.execute('update post set historic_path = path')

for post in Post.query.all():
    print(post.historic_path)
    if not post.slug:
        post.slug = post.generate_slug()
    post.path = '{}/{:02d}/{}'.format(post.published.year,
                                      post.published.month,
                                      post.slug)

db.session.commit()
