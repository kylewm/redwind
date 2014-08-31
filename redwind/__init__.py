import sys
import importlib

for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
#from flask_debugtoolbar import DebugToolbarExtension
from flask.ext.assets import Environment, Bundle
from werkzeug.datastructures import ImmutableDict
from redis import Redis
from config import Configuration

import logging
from logging.handlers import RotatingFileHandler


app = Flask('redwind')

app.config.from_object(Configuration)
redis = Redis()

assets = Environment(app)
assets.register(
    'css_all', Bundle('css/base.css', 'css/skeleton.css',
                      'css/layout.css', 'css/pygments.css',
                      filters='cssmin', output='css/site.css'))

app.jinja_options = ImmutableDict(
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_', 'jinja2.ext.i18n']
)


if app.config.get('PROFILE'):
    from werkzeug.contrib.profiler import ProfilerMiddleware
    f = open('logs/profiler.log', 'w')
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, f, restrictions=[30])

if app.debug:
    #toolbar = DebugToolbarExtension(app)
    app.config['SITE_URL'] = 'http://localhost:5000'


class LoggingMiddleware:
    """Sets up logging when the WSGI application is initialized. This
    allows us to set up the logger when redwind is invoked as an
    application but not when it is imported as a library (e.g. by the
    queue_daemon)
    """
    def __init__(self, logger, wsgi_app):
        self.logger = logger
        self.wrapped = wsgi_app

    def wsgi_app(self, *args, **kwargs):
        self.logger.setLevel(logging.DEBUG)
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=1048576,
                                           backupCount=5)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        return self.wrapped(*args, **kwargs)


if not app.debug:
    app.wsgi_app = LoggingMiddleware(app.wsgi_app, app.logger)

for handler in ['controllers']:
    importlib.import_module('redwind.' + handler)

for plugin in ['facebook', 'locations', 'push', 'reader', 'twitter',
               'wm_receiver', 'wm_sender']:
    app.logger.info('loading plugin module %s', plugin)
    module = importlib.import_module('redwind.plugins.' + plugin)
    try:
        module.register()
    except:
        app.logger.warn('no register method for plugin module %s', plugin)
