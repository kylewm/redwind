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
from .models import User
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'index'


@login_mgr.user_loader
def load_user(domain):
    user = User.load(os.path.join(app.root_path, '_data/user.json'))
    user.authenticated = True
    if user.domain == domain:
        return user
    else:
        # guest user
        return User(domain)
