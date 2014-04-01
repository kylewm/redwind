import os
import os.path
from models import Post, Mention

if __name__ == '__main__':
    mentions = []
    for root, dirs, files in os.walk('_data/posts'):
        for filename in files:
            post = Post.load(os.path.join(root, filename))
            for mention in post.mentions:
                mentions.append((post, mention))

    def sortkey(pair):
        post, mention = pair
        return mention.pub_date, post.pub_date

    mentions.sort(key=sortkey)
    for mention in mentions[:10]:
        print(mention)
