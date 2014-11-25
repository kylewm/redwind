from . import db
from .models import Setting, Post, Contact, Venue, Tag, Nick, Mention, Context
import datetime


def truncate(string, length):
    if string:
        return string[:length]

def import_all(blob):
    tags = {}
    venues = {}
    db.session.add_all([import_setting(s) for s in blob['settings']])
    db.session.add_all([import_venue(v, venues) for v in blob['venues']])
    db.session.add_all([import_contact(c) for c in blob['contacts']])
    db.session.add_all([import_post(p, tags, venues) for p in blob['posts']])
    db.session.commit()

    
def import_datetime(dt):
    if dt:
        return datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S')

def import_setting(blob):
    s = Setting()
    s.key = blob['key']
    s.name = blob['name']
    s.value = blob['value']
    return s


def import_contact(blob):
    c = Contact()
    c.name = blob['name']
    c.nicks = [Nick(name=name) for name in blob['nicks']]
    c.image = blob['image']
    c.url = blob['url']
    c.social = blob['social']
    return c


def import_venue(blob, venues):
    v = Venue()
    v.name = blob['name']
    v.location = blob['location']
    v.slug = blob['slug']
    venues[v.slug] = v
    return v


def import_post(blob, tags, venues):
    def import_tag(tag_name):
        tag = tags.get(tag_name)
        if not tag:
            tag = Tag(tag_name)
            tags[tag_name] = tag
        return tag

    def lookup_venue(slug):
        if slug:
            return venues.get(slug)

    p = Post(blob['post_type'])
    p.path = blob['path']
    p.historic_path = blob['historic_path']
    p.draft = blob['draft']
    p.deleted = blob['deleted']
    p.hidden = blob['hidden']
    p.redirect = blob['redirect']
    p.tags = [import_tag(t) for t in blob['tags']]
    p.audience = blob['audience']
    p.in_reply_to = blob['in_reply_to']
    p.repost_of = blob['repost_of']
    p.like_of = blob['like_of']
    p.bookmark_of = blob['bookmark_of']
    p.reply_contexts = [import_context(c) for c in blob['reply_contexts']]
    p.like_contexts = [import_context(c) for c in blob['like_contexts']]
    p.repost_contexts = [import_context(c) for c in blob['repost_contexts']]
    p.bookmark_contexts = [import_context(c) for c in blob['bookmark_contexts']]
    p.title = blob['title']
    p.published = import_datetime(blob['published'])
    p.slug = blob['slug']
    p.syndication = blob['syndication']
    p.location = blob['location']
    p.photos = blob['photos']
    p.venue = lookup_venue(blob['venue'])
    p.mentions = [import_mention(m) for m in blob['mentions']]
    p.content = blob['content']
    p.content_html = blob['content_html']
    return p


def import_context(blob):
    c = Context()
    c.url = blob['url']
    c.permalink = blob['permalink']
    c.author_name = truncate(blob['author_name'], 128)
    c.author_url = blob['author_url']
    c.author_image = blob['author_image']
    c.content = blob['content']
    c.content_plain = blob['content_plain']
    c.published = import_datetime(blob['published'])
    c.title = truncate(blob['title'], 512)
    c.syndication = blob['syndication']
    return c


def import_mention(blob):
    m = Mention()
    m.url = blob['url']
    m.permalink = blob['permalink']
    m.author_name = truncate(blob['author_name'], 128)
    m.author_url = blob['author_url']
    m.author_image = blob['author_image']
    m.content = blob['content']
    m.content_plain = blob['content_plain']
    m.published = import_datetime(blob['published'])
    m.title = truncate(blob['title'], 512)
    m.syndication = blob['syndication']
    m.reftype = blob['reftype']
    return m

