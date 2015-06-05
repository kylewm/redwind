#!/usr/bin/env python

from redwind import db, models

s = models.Setting.query.get('avatar_suffix')
if not s:
    print('Adding Avatar Suffix settings')
    s = models.Setting()
    s.key = 'avatar_suffix'
    s.name = 'Avatar Suffix'
    s.value = 'jpg'
    db.session.add(s)
    db.session.commit()
else:
    print('Found Avatar Suffix settings. Skipping.')

print('Done.')
