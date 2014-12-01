"""
"""
import os
import json
from sqlalchemy import (create_engine, Table, Column, String, Integer,
                        Float, Text, MetaData, select, ForeignKey,
                        bindparam, delete, and_)
from config import Configuration

engine = create_engine(Configuration.SQLALCHEMY_DATABASE_URI, echo=True)

metadata = MetaData()

tags = Table(
    'tag', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
)

posts = Table(
    'post', metadata,
    Column('id', Integer, primary_key=True),
)

posts_to_tags = Table(
    'posts_to_tags', metadata,
    Column('tag_id', Integer, ForeignKey('tag.id')),
    Column('post_id', Integer, ForeignKey('post.id')),
)


def eliminate_duplicates(conn):
    tag_map = {}
    update_batch = []
    delete_batch = []

    for row in conn.execute(
            select([posts, tags]).select_from(
                posts.join(posts_to_tags).join(tags)
            ).order_by(tags.c.id)):
        post_id = row[0]
        tag_id = row[1]
        tag_name = row[2]

        # possible duplicate
        if tag_name in tag_map:
            preexisting_tag_id = tag_map.get(tag_name)
            if preexisting_tag_id != tag_id:
                update_batch.append({
                    'the_post_id': post_id,
                    'old_tag_id': tag_id,
                    'new_tag_id': preexisting_tag_id,
                })
                delete_batch.append({
                    'the_tag_id': tag_id,
                })
        else:
            tag_map[tag_name] = tag_id

    print('update batch', update_batch)
    if update_batch:
        update_stmt = posts_to_tags.update().where(
            and_(
                posts_to_tags.c.post_id == bindparam('the_post_id'),
                posts_to_tags.c.tag_id == bindparam('old_tag_id')
            )
        ).values(tag_id=bindparam('new_tag_id'))
        # print(update_stmt)
        # print(update_batch)
        conn.execute(update_stmt, update_batch)

    print('delete batch', delete_batch)
    if delete_batch:
        delete_stmt = tags.delete().where(tags.c.id == bindparam('the_tag_id'))
        # print(delete_stmt)
        conn.execute(delete_stmt, delete_batch)


with engine.begin() as conn:
    eliminate_duplicates(conn)
