from .models import Setting, Post, Contact, Venue
import datetime


def export_all():
    return {
        'settings': [export_setting(s) for s in Setting.query.all()],
        'venues': [export_venue(v) for v in Venue.query.all()],
        'contacts': [export_contact(c) for c in Contact.query.all()],
        'posts': [export_post(p) for p in Post.query.all()],
        }

def export_datetime(dt):
    if dt:
        if dt.tzinfo:
            dt = dt.astimezone(datetime.timezone.utc)
            dt = dt.replace(tzinfo=None)
        return dt.strftime('%Y-%m-%dT%H:%M:%S')

def export_setting(s):
    return { 
        'key': s.key,
        'name': s.name,
        'value': s.value,
        }


def export_contact(c):
    return {
        'name': c.name,
        'nicks': [ n.name for n in c.nicks ],
        'image': c.image,
        'url': c.url,
        'social': c.social,
        }


def export_venue(v):
    return {
        'name': v.name,
        'location': v.location,
        'slug': v.slug,
        }


def export_post(p):
    return {
        'path': p.path, 
        'historic_path': p.historic_path, 
        'post_type': p.post_type, 
        'draft': p.draft, 
        'deleted': p.deleted, 
        'hidden': p.hidden, 
        'redirect': p.redirect, 
        'tags': [t.name for t in p.tags], 
        'audience': p.audience, 
        'in_reply_to': p.in_reply_to, 
        'repost_of': p.repost_of, 
        'like_of': p.like_of, 
        'bookmark_of': p.bookmark_of, 
        'reply_contexts': [export_context(c) for c in p.reply_contexts], 
        'like_contexts': [export_context(c) for c in p.like_contexts], 
        'repost_contexts': [export_context(c) for c in p.repost_contexts], 
        'bookmark_contexts': [export_context(c) for c in p.bookmark_contexts], 
        'title': p.title, 
        'published': export_datetime(p.published), 
        'slug': p.slug, 
        'syndication': p.syndication, 
        'location': p.location, 
        'photos': p.photos, 
        'venue': p.venue.slug if p.venue else None, 
        'mentions': [export_mention(m) for m in p.mentions], 
        'content': p.content, 
        'content_html': p.content_html, 
        }


def export_context(c):
    return {
        'url': c.url, 
        'permalink': c.permalink, 
        'author_name': c.author_name, 
        'author_url': c.author_url, 
        'author_image': c.author_image, 
        'content': c.content, 
        'content_plain': c.content_plain, 
        'published': export_datetime(c.published), 
        'title': c.title, 
        'syndication': c.syndication, 
        }


def export_mention(m):
    return {
        'url': m.url, 
        'permalink': m.permalink, 
        'author_name': m.author_name, 
        'author_url': m.author_url, 
        'author_image': m.author_image, 
        'content': m.content, 
        'content_plain': m.content_plain, 
        'published': export_datetime(m.published), 
        'title': m.title, 
        'syndication': m.syndication,
        'reftype': m.reftype,
        }
