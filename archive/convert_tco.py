from app import db
from models import Post
import requests
import re
import sys 

def replacer(match):
    url = match.group(0)
    response = requests.get(url)
    for history in response.history:
        if history.status_code == 301:
            dest = history.headers['location']
    return dest or url

posts = Post.query.all()
nposts = len(posts)
cpost = 0

for post in posts:
    pattern = re.compile(r'https?://(t.co|tinyurl.com|bit.ly)/[a-zA-Z0-9_]+')
    if pattern.search(post.content):
        print("Converting {}/{} posts".format(cpost, nposts))
        try:
            post.content = pattern.sub(replacer, post.content)
        except:
            print("error ", sys.exc_info()[0])
    cpost += 1
    if cpost % 100 == 0:
        db.session.commit()
        
db.session.commit()


