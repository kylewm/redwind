from app import app
from models import User
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'login'


@login_mgr.user_loader
def load_user(domain):
    app.logger.debug("loading user by domain %s", domain)
    user = User.query.filter_by(domain=domain).first()
    app.logger.debug("found user %s", user)
    return user
