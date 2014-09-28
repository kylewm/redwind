import os


class Configuration(object):
    DEBUG = os.environ.get('REDWIND_DEBUG') == 'true'

    # do not intercept redirects when using debug toolbar
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    # Some secret key used by Flask-Login
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Color theme for pygments syntax coloring (handled by the
    # codehilite plugin for Markdown)
    PYGMENTS_STYLE = 'tango'

    # PuSH hub to notify for new posts or mentions
    PUSH_HUB = os.environ.get('PUSH_HUB')

    # Site's base URL, for generating external references
    SITE_URL = os.environ.get('URL')

    # schema to contact DB
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    REDIS_URL = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379')

    # the number of posts to display on any given page
    POSTS_PER_PAGE = 15

    TIMEZONE = os.environ.get('TIMEZONE', 'America/Los_Angeles')

    TWITTER_CONSUMER_KEY = os.environ.get('TWITTER_API_KEY')
    TWITTER_CONSUMER_SECRET = os.environ.get('TWITTER_API_SECRET')

    FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
    FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')

    PLUGINS = [
        'facebook',
        'locations',
        'push',
        'twitter',
        'wm_receiver',
        'wm_sender',
    ]
