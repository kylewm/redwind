"""
"""
import os
import json
from sqlalchemy import (create_engine, Table, Column, String, Integer,
                        PickleType, Boolean, DateTime, Float, Text,
                        MetaData, select, ForeignKey, bindparam,
                        delete, and_)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from config import Configuration

from redwind import app, db, util
from redwind.models import Post
import itertools


db.engine.execute('alter table post add column short_path varchar(16)')


short_paths = set()

for post in Post.query.order_by(Post.published):
    if not post.short_path:
        short_base = '{}/{}'.format(
            util.tag_for_post_type(post.post_type),
            util.base60_encode(util.date_to_ordinal(post.published)))

        for idx in itertools.count(1):
            post.short_path = short_base + util.base60_encode(idx)
            if post.short_path not in short_paths:
                break

        short_paths.add(post.short_path)
        print(post.short_path + '\t' + post.path)

db.session.commit()
