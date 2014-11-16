from redis import Redis
from rq import Queue
from config import Configuration
from flask.ext.assets import Environment
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager


redis = Redis.from_url(Configuration.REDIS_URL)
queue = Queue(connection=redis)
db = SQLAlchemy()

# toolbar = DebugToolbarExtension(app)
login_mgr = LoginManager()
login_mgr.login_view = 'index'

assets = Environment()
