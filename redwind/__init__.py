import sys
import importlib

sys.path.append('external')

from flask import Flask
# from flask_debugtoolbar import DebugToolbarExtension
from flask.ext.assets import Environment, Bundle
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager

from werkzeug.datastructures import ImmutableDict
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from config import Configuration

import os
import logging


app = Flask(__name__)
app.config.from_object(Configuration)

db = SQLAlchemy(app)

# toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager(app)
login_mgr.login_view = 'index'

assets = Environment(app)

assets.register('css_all',
                Bundle('css/style.css', 'css/pygments.css',
                       filters='cssmin', output='css/site.css'))

assets.register('js_all',
                Bundle('js/util.js', 'js/http.js', 'js/posts.js',
                       'js/twitter.js', 'js/edit_contact.js',
                       'js/edit_post.js', 'js/edit_venue.js', filters='jsmin',
                       output='js/main.js'))

app.jinja_options = ImmutableDict(
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=[
        'jinja2.ext.autoescape',
        'jinja2.ext.with_',
        'jinja2.ext.i18n',
    ]
)

if app.config.get('PROFILE'):
    from werkzeug.contrib.profiler import ProfilerMiddleware
    f = open('logs/profiler.log', 'w')
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, f, restrictions=[60],
                                      sort_by=('cumtime', 'tottime', 'ncalls'))


# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
if not app.debug:
    app.logger.setLevel(logging.DEBUG)
    if not os.path.exists('logs'):
        os.makedirs('logs')
    file_handler = RotatingFileHandler(
        'logs/app.log', maxBytes=1048576, backupCount=5)
    stream_handler = StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(stream_handler)


for handler in ['views', 'services', 'micropub']:
    importlib.import_module('redwind.' + handler)


# register blueprints
from .imageproxy import imageproxy
app.register_blueprint(imageproxy, url_prefix='/imageproxy')


for plugin in [
        'facebook',
        'locations',
        'push',
        'twitter',
        'wm_receiver',
        'wm_sender',
]:
    # app.logger.info('loading plugin module %s', plugin)
    module = importlib.import_module('redwind.plugins.' + plugin)
    try:
        module.register()
    except:
        app.logger.warn('no register method for plugin module %s', plugin)
