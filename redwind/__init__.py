import sys
import os
for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
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

#toolbar = DebugToolbarExtension(app)

if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    app.logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler('app.log', maxBytes=1048576,
                                       backupCount=5)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)


from . import controllers
