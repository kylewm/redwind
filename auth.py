from functools import wraps
from app import app, db
from models import User
from flask import request, Response
from flask.ext.login import LoginManager

login_mgr = LoginManager(app)
login_mgr.login_view = 'login'


@login_mgr.user_loader
def load_user(userid):
    return User.query.filter_by(login=userid).first()
