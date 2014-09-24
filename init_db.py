#!/usr/bin/env python

from redwind import db, models

print('creating database tables')
db.create_all()
print('done!')
