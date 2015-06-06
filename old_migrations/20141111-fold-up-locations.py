"""convert all Locations and Photos to JSON blobs and save them
inside their owner
"""
import os
import json
from sqlalchemy import (create_engine, Table, Column, String, Integer,
                        Float, Text, MetaData, select, ForeignKey,
                        bindparam)


engine = create_engine(os.environ.get('DATABASE_URL'), echo=True)

# modify schema
try:
    engine.execute('ALTER TABLE POST ADD COLUMN LOCATION TEXT')
except:
    pass

try:
    engine.execute('ALTER TABLE VENUE ADD COLUMN LOCATION TEXT')
except:
    pass

try:
    engine.execute('ALTER TABLE POST ADD COLUMN PHOTOS TEXT')
except:
    pass


conn = engine.connect()
metadata = MetaData()

locations = Table(
    'Location', metadata,
    Column('id', Integer, primary_key=True),
    Column('latitude', Float),
    Column('longitude', Float),
    Column('name', String),
    Column('street_address', String),
    Column('extended_address', String),
    Column('locality', String),
    Column('region', String),
    Column('country_name', String),
    Column('postal_code', String),
    Column('country_code', String),
    Column('post_id', Integer, ForeignKey('post.id')),
    Column('venue_id', Integer, ForeignKey('venue.id')),
)

photos = Table(
    'photo', metadata,
    Column('id', Integer, primary_key=True),
    Column('filename', String),
    Column('caption', Text),
    Column('post_id', Integer, ForeignKey('post.id')),
)

posts = Table(
    'post', metadata,
    Column('id', Integer, primary_key=True),
    Column('location', Text),
    Column('photos', Text),
)

venues = Table(
    'venue', metadata,
    Column('id', Integer, primary_key=True),
    Column('location', Text),
)

loc_attrs = [
    locations.c.latitude,
    locations.c.longitude,
    locations.c.name,
    locations.c.street_address,
    locations.c.extended_address,
    locations.c.locality,
    locations.c.region,
    locations.c.country_name,
    locations.c.postal_code,
    locations.c.country_code,
]


def migrate_post_locations():
    posts_batch = []
    for row in conn.execute(
            select([posts, locations], use_labels=True).select_from(
                posts.join(locations))):
        loc = json.dumps({
            attr.name: row[attr] for attr in loc_attrs if row[attr]
        })
        posts_batch.append({
            'post_id': row[posts.c.id],
            'location': loc,
        })

    update_posts = posts.update()\
                        .where(posts.c.id == bindparam('post_id'))\
                        .values(location=bindparam('location'))

    conn.execute(update_posts, posts_batch)


def migrate_venue_locations():
    venues_batch = []
    for row in conn.execute(
            select([venues, locations], use_labels=True).select_from(
                venues.join(locations))):
        loc = json.dumps({
            attr.name: row[attr] for attr in loc_attrs if row[attr]
        })
        venues_batch.append({
            'venue_id': row[venues.c.id],
            'location': loc,
        })

    update_posts = venues.update()\
                         .where(venues.c.id == bindparam('venue_id'))\
                         .values(location=bindparam('location'))

    conn.execute(update_posts, venues_batch)


def migrate_post_photos():
    photo_map = {}
    photo_attrs = [
        photos.c.caption,
        photos.c.filename,
    ]

    for row in conn.execute(
            select([posts, photos], use_labels=True).select_from(
                posts.join(photos))):
        post_id = row[posts.c.id]
        photo_json = {
            attr.name: row[attr] for attr in photo_attrs if row[attr]
        }
        photo_map.setdefault(post_id, []).append(photo_json)

    photo_batch = []
    for post_id, photo_blob in photo_map.items():
        photo_batch.append({
            'post_id': post_id,
            'photos': json.dumps(photo_blob),
        })

    update_photos = posts.update()\
                         .where(posts.c.id == bindparam('post_id'))\
                         .values(photos=bindparam('photos'))

    conn.execute(update_photos, photo_batch)


migrate_post_locations()
migrate_venue_locations()
migrate_post_photos()
