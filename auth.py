from app import app
from models import User
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'login'


@login_mgr.user_loader
def load_user(userid):
    return User.query.filter_by(login=userid).first()
