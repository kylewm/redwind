import os
from . import app
from .models import User
from flask.ext.login import login_user
from pickle import loads, dumps


def init():
    try:
        import uwsgi
        uwsgi.spooler = process_spool
    except:
        app.logger.warn("Running outside of uwsgi, spooler disabled")


def spoolable(f):
    def spool(*args, **kwargs):
        import uwsgi
        uwsgi.spool({
            b'f': dumps(f),
            b'args': dumps(args),
            b'kwargs': dumps(kwargs)
        })

    f.spool = spool
    return f


def process_spool(env):
    import uwsgi
    try:
        func = loads(env[b'f'])
        args = loads(env[b'args'])
        kwargs = loads(env[b'kwargs'])

        with app.test_request_context():
            user = User.load(os.path.join(app.root_path, '_data/user'))
            app.logger.debug('loaded user %s', repr(user))
            login_user(user)
            func(*args, **kwargs)

    except Exception:
        app.logger.exception("exception while processing queue")

    return uwsgi.SPOOL_OK
