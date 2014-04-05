# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.

import sys
if 'mf2py' not in sys.path:
    sys.path.append('mf2py')

from flask import Flask
from werkzeug.datastructures import ImmutableDict

app = Flask(__name__)
app.config.from_object('config.Configuration')

app.jinja_options = ImmutableDict(
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_', 'jinja2.ext.i18n']
)


if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler('app.log', maxBytes=1048576,
                                       backupCount=5)
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)



from . import views
from . import spool
