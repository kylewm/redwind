import sys
import importlib

for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask.ext.assets import Environment, Bundle
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from werkzeug.datastructures import ImmutableDict
from redis import Redis
from rq import Queue
from config import Configuration
from logging.handlers import RotatingFileHandler

import os
import logging


app = Flask(__name__)
app.config.from_object(Configuration)

redis = Redis.from_url(app.config['REDIS_URL'])

queue = Queue(connection=redis)
db = SQLAlchemy(app)
toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager(app)
login_mgr.login_view = 'index'

assets = Environment(app)
assets.register('css_all', Bundle('css/style.css', 'css/pygments.css',
                                  output='css/site.css'))


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


#logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
if not app.debug:
    app.logger.setLevel(logging.DEBUG)
    if not os.path.exists('logs'):
        os.makedirs('logs')
    file_handler = RotatingFileHandler(
        'logs/app.log', maxBytes=1048576, backupCount=5)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)


class Settings:
    def all(self):
        from .models import Setting
        return Setting.query.order_by(Setting.key).all()

    def __getattr__(self, key):
        from .models import Setting
        s = Setting.query.get(key)
        return s.value

    def __setattr__(self, key, value):
        from .models import Setting
        s = Setting.query.get(key)
        s.value = value
        db.session.commit()

settings = Settings()


for handler in ['views']:
    importlib.import_module('redwind.' + handler)


for plugin in [
        'facebook',
        'locations',
        'push',
        'twitter',
        'wm_receiver',
        'wm_sender',
]:
    #app.logger.info('loading plugin module %s', plugin)
    module = importlib.import_module('redwind.plugins.' + plugin)
    try:
        module.register()
    except:
        app.logger.warn('no register method for plugin module %s', plugin)
