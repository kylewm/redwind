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

    # schema to contact DB
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    REDIS_URL = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379')
