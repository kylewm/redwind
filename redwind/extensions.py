from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.themes2 import Themes
from flask.ext.migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


# toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager()
login_mgr.login_view = 'admin.login'

themes = Themes()


def init_app(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_mgr.init_app(app)
    themes.init_themes(app)
