import sys
import os
for module in ('mf2py', 'mf2util'):
    if module not in sys.path:
        sys.path.append(module)

from flask import Flask
from jinja2 import FileSystemLoader
from werkzeug.datastructures import ImmutableDict
from redis import Redis


class MyFlask(Flask):
    def __init__(self):
        Flask.__init__(self, __name__)
        self.config.from_object('config.Configuration')

    def jinja_loader(self):
        search_path = []
        if self.template_folder is not None:
            search_path.append(
                os.path.join(self.root_path, self.template_folder))

        theme_name = self.config.get('THEME')
        if theme_name is not None:
            search_path.append(
                os.path.join(self.root_path, 'themes', theme_name))

        return search_path and FileSystemLoader(search_path)


app = MyFlask()
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


from . import views
