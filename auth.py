from functools import wraps
from app import db
from models import User
from flask import request, Response


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    user = db.session.query(User).filter_by(login=username).first()
    return user and user.check_password(password)

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Groomsman"'})

def is_authenticated():
    auth = request.authorization
    return auth and check_auth(auth.username, auth.password)
 
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return authenticate()
        return f(*args, **kwargs)
    return decorated
