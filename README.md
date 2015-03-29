[![Build Status](https://travis-ci.org/kylewm/redwind.svg?branch=master)](https://travis-ci.org/kylewm/redwind)
[![Coverage Status](https://img.shields.io/coveralls/kylewm/redwind.svg)](https://coveralls.io/r/kylewm/redwind?branch=master)

# Red Wind

Red Wind is a (micro)-blogging engine used on my personal website,
kylewm.com. I have been using it to screw around with
[IndieWeb](http://indiewebcamp.com) ideas like POSSE (Twitter and
Facebook), microformats, and webmentions (sending and receiving).

# IndieWeb Support

Red Wind supports a bunch of (indie)web technologies, some better than others.

* Microformats2 (h-feed, h-entry, h-card)
* Webmention sending
* Webmention receiving
* Publish rel-me (support signing into the indiewebcamp.com wiki)
* Sign-in to Red Wind via IndieAuth
* Publish posts via Micropub
* Reply context for posts with microformats or certain silo posts.
* [POSSE](https://indiewebcamp.com/POSSE).
    * to Twitter (notes, articles, photos, likes, retweets)
    * to Facebook (notes, articles, photos)
    * likes to Instagram (API prevents us from posting anything
      else. see OwnYourGram.com for an alternative)
    * comments to Wordpress.com and Jetpack-enabled Wordpress blogs
* Check-ins (based on a local venue database, which means you have to
  create a venues the first time you check-in)
* Ping a Pubsubhubbub 0.4 hub on each update.
* Receive push notifications for mentions via Pushover

# Requirements

* **Python 3.3 or newer**. Will not work in Python 2!
* Flask (and other libraries defined in requirements.txt)
* A database supported by SQLAlchemy (Postgres, MySQL, SQLite)
* Redis (optional, recommended)
* uWSGI and nginx (other servers like gunicorn should work but are
  untested)

# Disclaimer

This is an experimental project with lots of rough edges. It is not
particularly user-friendly and requires some command-line
gymnastics to install and manage.

If you want to hack on IndieWeb stuff in Python/Flask, it might be
interesting to you! If on the other hand you want something polished
and fully-formed and with an established userbase, I can highly recommend
[Known](https://withknown.com).

Come join us in the #indiewebcamp IRC channel on Freenode (I'm kylewm)
if you have any questions, comments, concerns, or of course file an
issue here. I'd love to hear from you.


# Installation

**Create a new database.** Unless you are using SQLite, you must
create a database (and possibly database user). For Postgres, I do
something like

```
kmahan@orin:~$ createuser kmahan
kmahan@orin:~$ createdb redwind --owner=kmahan
```

**Copy config.py.template to config.py and fill in details.** At a
minimum, set the following keys:

* `SECRET_KEY`: Used for securing your session. Can be anything at all
  that is sufficiently long and unguessable.
* `SQLALCHEMY_DATABASE_URI`: specify the location of your database as
  a URI.


**Create a virtualenv and install python dependencies.**

Note: if you are not using Postgres, comment out the requirement for
psycopg2 in requirements.txt.

```
kmahan@orin:$ virtualenv --python=/usr/bin/python3 venv
Running virtualenv with interpreter /usr/bin/python3
Using base prefix '/usr'
New python executable in venv/bin/python3
Not overwriting existing python script venv/bin/python (you must use venv/bin/python3)
Installing setuptools, pip...done.
kmahan@orin:$ source venv/bin/activate
(venv)kmahan@orin:$ pip install -r requirements.txt
```

**Run unit tests with py.test.** At this point, running the unit tests
is a good sanity-check to make sure most things are set up
correctly.

```
(venv)kmahan@orin:$ py.test tests
== test session starts ==
platform linux -- Python 3.4.0 -- py-1.4.26 -- pytest-2.6.4
plugins: mock, cov
collected 26 items

tests/util_test.py .........
tests/views_test.py ...........
tests/wm_receiver_test.py ....
tests/wm_sender_test.py ..
```

**Run ./install.py from the command line to generate the database
schema.** This script will prompt you for some basic info to seed
the author bio with enough information to let you authenticate with
indieauth.com. Once authenticated,  you will be able to edit your bio
from the /settings page.

**Run a local server to test installation.** You can use `./run.py` or
`uwsgi --http :5000 --module redwind:app` to run a simple local server 
on localhost:5000 as a sanity check (or to do local development work).

In production `uwsgi uwsgi-prod.ini` will start the application server 
and qworker daemon.

Note: for development, I actually prefer to use `uwsgi uwsgi-local.ini`,
add a `/etc/hosts` entry for `redwind.dev` and configure nginx to serve the
application just like in production.

## Nginx Configuration

The nginx configuration is mostly straightforward except for the
[tricky X-Accel-File stuff](http://wiki.nginx.org/XSendfile). See
comments below for explanation.

```nginx
server {
    listen 80;
    server_name  kylewm.com;

    access_log /srv/www/kylewm.com/logs/access.log;
    error_log /srv/www/kylewm.com/logs/error.log warn;
    root /srv/www/kylewm.com/public_html;
    client_max_body_size 10M;

    # Connection to the primary application
    location / {
      include uwsgi_params;
      uwsgi_pass unix:/tmp/uwsgi.sock;
      uwsgi_param UWSGI_SCHEME $scheme;
    }

    # Serve resources directly from the static directory (won't hit
    # Python code at all)
    location /static {
      root /srv/www/kylewm.com/redwind/redwind;
      expires 30d;
    }

    # Attached files like "/2015/03/<slug>/files/photo.jpg" are stored
    # redwind/_data. Requests for them pass through the Python code
    # and then use X-Accel-File to redirect to an internal resource.
    location /internal_data/ {
        internal;
        alias /srv/www/kylewm.com/redwind/redwind/_data/;
        expires 30d;
    }

    # Remote images are proxied locally to prevent mixed content
    # warnings. This uses the same X-Accel-File trick as above.
    location /internal_imageproxy/ {
        internal;
        alias /srv/www/kylewm.com/redwind/redwind/_imageproxy/;
        expires 1d;
    }
}
```

### Nginx Configuration with SSL

To serve from HTTPS instead (recommended), modify your configuration:

```
server {
    listen 443 ssl;
    server_name  kylewm.com;

    ssl_certificate      /path/to/certificate.crt
    ssl_certificate_key  /path/to/certificate-key.pem
    ssl_prefer_server_ciphers On;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_ciphers ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+3DES:DH+3DES:RSA+AESGCM:RSA+AES:RSA+3DES:!aNULL:!MD5:!DSS;

    ...
}
```

I use a free certificate from [StartSSL](https://startssl.com). See
https://indiewebcamp.com/https for more information.

TODO: The ssl configuration above gives me an A rating on Qualys, not
A+ yet.


## First Sign-in after Installation

Because Red Wind uses IndieAuth.com as its authentication provider,
there is a bit of a chicken-egg problem with the first sign-in
&emdash; you need to configure your site to show rel-me links to
Twitter/GitHub/etc. before you can sign in, but you need to be signed
in to edit your rel-me links.

To mitigate this, the installation script will ask for the domain name
you will use to indieauth and a Twitter and GitHub account name. These
are used only to seed the Author Bio with rel-me links. If you want to
use a different authentication provider that is supported by
IndieAuth.com (SMS, Mozilla Persona, even PGP keys), edit the bio
section of the installation script, or manipulate the SETTING database
table directly with SQL (`update SETTING set value='...' where
key='author_bio';`).

For local development, you can set the `BYPASS_INDIEAUTH = True` in
your config.py. This will simply trust that whatever domain you give
it is your domain (obviously this is not a good idea in production).


## Configuring API Keys

The twitter, wordpress, facebook, and instagram plugins all require
their own API keys to work properly.

Visit the `/settings` page, and fill in any or all of:

* Twitter API Key
* Twitter API Secret
* Facebook App ID
* Facebook App Secret
* WordPress Client ID
* WordPress Client Secret
* Instagram Client ID
* Instagram Client Secret

and make sure to `Save` settings before continuing! To obtain an
access token for each of these services, use the *Authorize ...* links at the bottom
of the settings page.


# Theme Support

Theme-support is provided by
[Flask-Themes2](https://flask-themes2.readthedocs.org/en/latest/). They
live in `redwind/themes/<theme-name>`. Set the `DEFAULT_THEME` key
in config.py to use a different theme.

Admin page templates are kept separately in `redwind/templates/admin`,
which is good for maintenance (you don't have to worry about them when
creating a new theme), but arguably bad for UX &emdash; the admin
interface feels disconnected, like a CMS or Wordpress blog, where the
experience on most social sites is more integrated.


# Plugins

Plugins provide non-core functionality (like sending and receiving
webmentions and various silo integrations). To be honest the plugin
mechanism is not incredibly well thought-out and may change or go away
in the future.

For now plugins are simply modules that live under `redwind.plugins`
have a `register()` function (They are loaded at the bottom of
`redwind/__init__.py`).

## Plugin Hooks

A plugin can register itself to respond to various hooks via
`redwind.hooks.register(hook, action)`, where hook is a string and
action is a function. The currently available hooks are described
below:

* **post-saved:** Called after a Post is created or edited. The
  registered action should take two parameters: the
  `redwind.models.Post` and dict of input values.
* **venue-saved:** Called with `redwind.models.Venue` and a dict of
  input values.
* **create-context:** called with a URL. This provides plugins an
  opportunity to generate a `redwind.models.Context` reply context for
  a silo post (e.g., a tweet or instagram photo). Should return a new
  Context object if successful.

# Background Work Queue

Running a background work queue lets us respond immediately when
receiving a webmention, or when saving a post that will be syndicated
elsewhere.

The work queue is a hand-rolled solution based on
[Basic Message Queue with Redis](http://flask.pocoo.org/snippets/73/),
that supports either storing background jobs in the primary SQL
database and polling periodically for new jobs, or (recommended) in a
Redis queue.

To start the work queue, run `./qworker.py` from the commandline. If
using uWSGI, add the line `attach-daemon=qworker.py` to the ini file
to have the process managed automatically by uWSGI.

Note: this will probably be replaced by the more robust and
memory-efficient [Redis Queue](http://python-rq.org/) library in the
future. At that point, redis will become a hard requirement. Please
let me know if this will present problems for you!

# Etymology

"Red Wind" is a great Raymond Chandler short story. The first
paragraph is one my favorite things ever published:

> There was a desert wind blowing that night. It was one of those hot
> dry Santa Ana's that come down through the mountain passes and curl
> your hair and make your nerves jump and your skin itch. On nights
> like that every booze party ends in a fight. Meek little wives feel
> the edge of the carving knife and study their husbands'
> necks. Anything can happen. You can even get a full glass of beer at
> a cocktail lounge.
