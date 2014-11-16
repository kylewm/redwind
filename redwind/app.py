import sys
import importlib

sys.path.append('external')

from flask import Flask
from flask.ext.assets import Bundle

from .extensions import db, login_mgr, assets
from .models import User, get_settings
from .views import views
from .micropub import micropub
from .services import services

from werkzeug.datastructures import ImmutableDict
from config import Configuration
from logging import StreamHandler
from logging.handlers import RotatingFileHandler

import os
import logging


def create_app():
    app = Flask(__name__)
    app.config.from_object(Configuration)
    configure_extensions(app)
    configure_jinja(app)
    configure_blueprints(app)
    configure_profiler(app)
    configure_logging(app)
    load_plugins(app)
    return app


def configure_extensions(app):
    db.init_app(app)
    login_mgr.init_app(app)

    @login_mgr.user_loader
    def load_user(domain):
        return User(domain)

    assets.init_app(app)
    assets.register('css_all',
                    Bundle('css/style.css', 'css/pygments.css',
                           filters='cssmin', output='css/site.css'))

    assets.register('js_all',
                    Bundle('js/util.js', 'js/http.js', 'js/posts.js',
                           'js/twitter.js', 'js/edit_contact.js',
                           'js/edit_post.js', 'js/edit_venue.js',
                           filters='jsmin', output='js/main.js'))


def configure_jinja(app):
    app.jinja_options = ImmutableDict(
        trim_blocks=True,
        lstrip_blocks=True,
        extensions=[
            'jinja2.ext.autoescape',
            'jinja2.ext.with_',
            'jinja2.ext.i18n',
        ]
    )

    @app.context_processor
    def inject_settings_variable():
        return {
            'settings': get_settings()
        }


def configure_profiler(app):
    if app.config.get('PROFILE'):
        from werkzeug.contrib.profiler import ProfilerMiddleware
        f = open('logs/profiler.log', 'w')
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, f, restrictions=[60],
                                          sort_by=('cumtime', 'tottime',
                                                   'ncalls'))


def configure_logging(app):
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


def configure_blueprints(app):
    app.register_blueprint(views)
    app.register_blueprint(services)
    app.register_blueprint(micropub)


def load_plugins(app):
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
            module.register(app)
        except:
            app.logger.warn('no register method for plugin module %s', plugin)
