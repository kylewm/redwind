from .extensions import login_mgr
from .models import User, Credential
from flask import current_app


@login_mgr.user_loader
def load_user(id):
    try:
        if isinstance(id, int):
            return User.query.get(id)
        else:
            cred = Credential.query.filter_by(type='indieauth', value=id).first()
            return cred and cred.user
    except:
        current_app.logger.exception('loading current user')
