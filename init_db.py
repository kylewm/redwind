#!/usr/bin/env python

from redwind import app, db, models
import urllib.parse

print('creating database tables')
db.create_all()

domain = urllib.parse.urlparse(app.config['SITE_URL']).netloc
user = models.User.query.first()
if not user:
    user = models.User(domain)
    db.session.add(user)
    db.session.commit()

print('done!')
