from models import Post
from app import db

db.engine.execute("alter table post add date_str varchar(8)")
db.engine.execute("alter table post add date_index integer")

for post in Post.query.order_by(Post.pub_date).all():
    print("processing", post.content)
    post.date_str = post.pub_date.strftime('%y%m%d')
    count = Post.query.filter_by(date_str=post.date_str).count()
    post.date_index = count+1
    db.session.commit()
