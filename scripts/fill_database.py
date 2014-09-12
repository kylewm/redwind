from redwind import app, db
from redwind.models import Metadata, Post


db.drop_all()
db.create_all()

with app.test_request_context():
    for post in Metadata().iterate_all_posts():
        print('adding post', post.path)
        post.content = post.get_content()
        post.content_html = post.get_content_html()

        post.mentions = post.get_mentions()
        post.reply_contexts = post.get_reply_contexts()
        post.repost_contexts = post.get_repost_contexts()
        post.like_contexts = post.get_like_contexts()
        post.bookmark_contexts = post.get_bookmark_contexts()

        db.session.add(post)

    db.session.commit()
