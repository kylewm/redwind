from app import app
from models import User
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'index'


@login_mgr.user_loader
def load_user(domain):
    user = User.query.filter_by(domain=domain).first()
    return user
