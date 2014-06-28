from . import app
import os
from .models import User
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'index'


@login_mgr.user_loader
def load_user(domain):
    domain = domain.rstrip('/')
    user = User.load(os.path.join(app.root_path, '_data/user.json'))
    user.authenticated = True
    if user.domain.strip('/') == domain:
        return user
    else:
        # guest user
        return User(domain)
