from app import app, db
from models import Mention
from webmention_receiver import process_webmention

mentions = (Mention.query.all())
for mention in mentions:
    source = mention.source
    target = mention.post.permalink_url
    new_mentions = process_webmention(source, target)
    print("processing", mention)
    print("re-processed",new_mentions)
