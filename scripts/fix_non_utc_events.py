from redwind import create_app
from redwind.models import Post
from redwind.extensions import db
import datetime

app = create_app()

with app.app_context():
    for post in Post.query.filter(Post.post_type == 'event'):
        if (post.start_utc and post.start_utcoffset and post.end_utc
            and post.end_utcoffset):

            print('before', post.start_utc, post.end_utc, post.start_utcoffset, post.end_utcoffset)

            post.start_utc = post.start_utc\
                                 .replace(tzinfo=datetime.timezone(post.start_utcoffset))\
                                 .astimezone(datetime.timezone.utc)\
                                 .replace(tzinfo=None)

            post.end_utc = post.end_utc\
                               .replace(tzinfo=datetime.timezone(post.end_utcoffset))\
                               .astimezone(datetime.timezone.utc)\
                               .replace(tzinfo=None)

            print('after ', post.start_utc, post.end_utc)

    db.session.commit()
