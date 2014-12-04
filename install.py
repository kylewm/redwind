#!/usr/bin/env python

from redwind import db, models

print('creating database tables')
db.create_all()

print('done creating database tables')
print('setting default settings')

defaults = [
    ('Author Name',                ''),
    ('Author Image',               ''),
    ('Author Domain',              ''),
    ('Author Bio',                 ''),
    ('Site Title',                 ''),
    ('Site URL',                   ''),
    ('Shortener URL',              None),
    ('Push Hub',                   ''),
    ('Posts Per Page',             15),
    ('Twitter API Key',            ''),
    ('Twitter API Secret',         ''),
    ('Twitter OAuth Token',        ''),
    ('Twitter OAuth Token Secret', ''),
    ('Facebook App ID',            ''),
    ('Facebook App Secret',        ''),
    ('Facebook Access Token',      ''),
    ('PGP Key URL',                ''),
    ('Avatar Prefix',              'nobody'),
    ('Avatar Suffix',              'png'),
    ('Timezone',                   'America/Los_Angeles'),
]

for name, default in defaults:
    key = name.lower().replace(' ', '_')
    s = models.Setting.query.get(key)
    if not s:
        s = models.Setting()
        s.key = key
        s.name = name
        s.value = default
        db.session.add(s)
db.session.commit()

print('finished setting default settings')
