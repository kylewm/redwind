#!/usr/bin/env python

from redwind import create_app, models
from redwind.extensions import db
from flask import current_app

app = create_app()
with app.app_context():
    print('''\
    Welcome to the Red Wind installation script. This should only be used for
    to initialize a brand new database. Running this script against an existing
    database could destroy your data!''')

    print('creating database tables for database', current_app.config['SQLALCHEMY_DATABASE_URI'])
    db.create_all()
    print('done creating database tables')
