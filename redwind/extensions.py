from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager

db = SQLAlchemy()


# toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager()
login_mgr.login_view = 'admin.login'


def init_app(app):
    db.init_app(app)
    login_mgr.init_app(app)
