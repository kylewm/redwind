#!/usr/bin/env python

from redwind import app, db, models

print('''\
Welcome to the Red Wind installation script. This should only be used for
to initialize a brand new database. Running this script against an existing
database could destroy your data!''')

author_domain = input('Domain name (no schema): ').strip()
twitter_username = input('Your Twitter username: ').strip()
github_username = input('Your GitHub username: ').strip()


print('creating database tables for database', app.config['SQLALCHEMY_DATABASE_URI'])
db.create_all()
print('done creating database tables')

bio = '''
<div class="p-author h-card">
<a class="p-name u-url" href="/">New User</a> is a brand new Red Wind user!
Visit <a href="/settings">Settings</a> to edit your bio.
<ul>
<li><a href="https://twitter.com/{}">Twitter</a></li>
<li><a href="https://github.com/{}">GitHub</a></li>
</ul>
</div>
'''.format(twitter_username.lstrip('@'),
           github_username)


print('setting default settings')

defaults = [
    ('Author Name',                ''),
    ('Author Image',               ''),
    ('Author Domain',              author_domain),
    ('Author Bio',                 bio),
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
