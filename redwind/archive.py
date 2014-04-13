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

from . import app
import os
import urllib
import json


def load_json_from_archive(url):
    path = os.path.join(url_to_archive_path(url), 'parsed.json')
    app.logger.debug("checking archive for %s => %s", url, path)

    if os.path.exists(path):
        app.logger.debug("path exists, loading %s", path)
        return json.load(open(path, 'r'))
    app.logger.debug("path does not exist %s", path)
    raise RuntimeError("No archive entry for url: {}".format(url))


def url_to_archive_path(url):
    parsed = urllib.parse.urlparse(url)
    path = os.path.join(parsed.scheme,
                        parsed.netloc.strip('/'),
                        parsed.path.strip('/'))
    return os.path.join(app.root_path, '_data/archive', path)
