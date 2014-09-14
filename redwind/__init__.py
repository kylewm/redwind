import sys
import importlib

for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask.ext.assets import Environment, Bundle
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.datastructures import ImmutableDict
from redis import Redis
from rq import Queue
from config import Configuration

import logging


app = Flask('redwind')
app.config.from_object(Configuration)
redis = Redis()
queue = Queue(connection=redis)
db = SQLAlchemy(app)
toolbar = DebugToolbarExtension(app)


def init_db():
    db.create_all()


#@app.cli.command('initdb')
#def initdb_command():
#    """Creates the database tables."""
#    init_db()
#    print('Initialized the database.')


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
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, f, restrictions=[60],
                                      sort_by=('cumtime', 'tottime', 'ncalls'))



logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

if not app.debug:
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(logging.StreamHandler())

for handler in ['views']:
    importlib.import_module('redwind.' + handler)

for plugin in ['facebook', 'locations', 'push', 'reader', 'twitter',
               'wm_receiver', 'wm_sender']:
    #app.logger.info('loading plugin module %s', plugin)
    module = importlib.import_module('redwind.plugins.' + plugin)
    try:
        module.register()
    except:
        app.logger.warn('no register method for plugin module %s', plugin)
