from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.themes2 import Themes

db = SQLAlchemy()

# toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager()
login_mgr.login_view = 'login'

themes = Themes()


def init_app(app):
    db.init_app(app)
    login_mgr.init_app(app)
    themes.init_themes(app)
