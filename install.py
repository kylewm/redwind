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

    username = input('Your name: ').strip()
    twitter_username = input('Your Twitter username: ').strip()
    twitter_client_id = input('Twitter Client Key: ').strip()
    twitter_client_secret = input('Twitter Client Secret: ').strip()

    print('creating database tables for database',
          current_app.config['SQLALCHEMY_DATABASE_URI'])
    db.create_all()
    print('done creating database tables')

    bio = '''
    <div class="p-author h-card">
    <a class="p-name u-url" href="/">New User</a> is a brand new Red Wind user!
    Visit <a href="/settings">Settings</a> to edit your bio.
    <ul>
    <li><a rel="me" href="https://twitter.com/{}">Twitter</a></li>
    </ul>
    </div>
    '''.format(twitter_username.lstrip('@'))

    print('setting default settings')
    defaults = [
        ('Author Name',                ''),
        ('Author Image',               ''),
        ('Author Domain',              ''),
        ('Author Bio',                 bio),
        ('Site Title',                 ''),
        ('Site URL',                   ''),
        ('Shortener URL',              None),
        ('Push Hub',                   ''),
        ('Posts Per Page',             15),
        ('Twitter API Key',            twitter_client_id),
        ('Twitter API Secret',         twitter_client_secret),
        ('Twitter OAuth Token',        ''),
        ('Twitter OAuth Token Secret', ''),
        ('Facebook App ID',            ''),
        ('Facebook App Secret',        ''),
        ('Facebook Access Token',      ''),
        ('WordPress Client ID',        ''),
        ('WordPress Client Secret',    ''),
        ('WordPress Access Token',     ''),
        ('Instagram Client ID',        ''),
        ('Instagram Client Secret',    ''),
        ('Instagram Access Token',     ''),
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

    user = models.User(name=username, admin=True)
    user.credentials.append(models.Credential(type='twitter',
                            value=twitter_username))
    db.session.commit()

    print('finished setting default settings')
