import sys

sys.path.append('external')

from flask import Flask

#from config import Configuration
from logging import StreamHandler
import logging
import importlib


def create_app(config_path):
    from redwind import extensions
    from redwind.views import views
    from redwind.admin import admin
    from redwind.services import services
    from redwind.micropub import micropub
    from redwind.imageproxy import imageproxy

    app = Flask(__name__)
    app.config.from_pyfile(config_path)

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.add_extension('jinja2.ext.autoescape')
    app.jinja_env.add_extension('jinja2.ext.with_')
    app.jinja_env.add_extension('jinja2.ext.i18n')

    extensions.init_app(app)

    if app.config.get('PROFILE'):
        from werkzeug.contrib.profiler import ProfilerMiddleware
        f = open('logs/profiler.log', 'w')
        app.wsgi_app = ProfilerMiddleware(
            app.wsgi_app, f, restrictions=[60],
            sort_by=('cumtime', 'tottime', 'ncalls'))

    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    if not app.debug:
        app.logger.setLevel(logging.DEBUG)
        stream_handler = StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)

    app.register_blueprint(views)
    app.register_blueprint(admin)
    app.register_blueprint(services)
    app.register_blueprint(micropub)
    app.register_blueprint(imageproxy)

    for plugin in [
            'facebook',
            'instagram',
            'locations',
            'push',
            'twitter',
            'wm_receiver',
            'wm_sender',
            'wordpress',
    ]:
        # app.logger.info('loading plugin module %s', plugin)
        module = importlib.import_module('redwind.plugins.' + plugin)
        try:
            module.register(app)
        except:
            app.logger.warn('no register method for plugin module %s', plugin)

    return app
