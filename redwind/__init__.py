import sys
import os
for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from werkzeug.datastructures import ImmutableDict
from redis import Redis
from config import Configuration

app = Flask(
    __name__,
    template_folder=os.path.join(Configuration.THEME, 'templates'),
    static_folder=os.path.join(Configuration.THEME, 'static'))

app.config.from_object(Configuration)
redis = Redis()

app.jinja_options = ImmutableDict(
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_', 'jinja2.ext.i18n']
)

if app.debug:
    toolbar = DebugToolbarExtension(app)
    app.config['SITE_URL'] = 'http://localhost'

if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    app.logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler('app.log', maxBytes=1048576,
                                       backupCount=20)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)

    if 'ADMIN_EMAILS' in app.config:
        from logging.handlers import SMTPHandler
        mail_handler = SMTPHandler('127.0.0.1',
                                   'server-error@kylewm.com',
                                   app.config['ADMIN_EMAILS'],
                                   'Red Wind Error')
        mail_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        mail_handler.set_formatter(formatter)
        app.logger.addHandler(mail_handler)

from . import controllers
