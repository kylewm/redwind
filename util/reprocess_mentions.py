from app import app, db
from models import Mention
from webmention_receiver import process_webmention
from views import *

mentions = (Mention.query.all())
for mention in mentions:
    if mention.post and 'snarfed' in mention.source:
        source = mention.source
        target = mention.post.permalink_url
        new_mentions = process_webmention(source, target)
        print("processing", mention)
        print("re-processed", new_mentions)
