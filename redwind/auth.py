from .extensions import login_mgr
from .models import User
from flask import current_app


@login_mgr.user_loader
def load_user(id):
    try:
        return User.query.get(id)
    except:
        current_app.logger.exception('loading current user')
