#!/usr/bin/env python

from redwind import create_app
from redwind.extensions import db
from flask import current_app

app = create_app()
with app.app_context():
    print('creating database tables for database',
          current_app.config['SQLALCHEMY_DATABASE_URI'])
    db.create_all()
    print('done creating database tables')
