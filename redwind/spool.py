import uwsgi
from . import app
from .models import User
from flask.ext.login import login_user
from pickle import loads, dumps


def spoolable(f):
    def spool(*args, **kwargs):
        uwsgi.spool({
            b'f': dumps(f),
            b'args': dumps(args),
            b'kwargs': dumps(kwargs)
        })

    f.spool = spool
    return f


def process_spool(env):
    try:
        func = loads(env[b'f'])
        args = loads(env[b'args'])
        kwargs = loads(env[b'kwargs'])

        with app.test_request_context():
            user = User.load('_data/user')
            app.logger.debug('loaded user %s', repr(user))
            login_user(user)
            func(*args, **kwargs)

    except Exception:
        app.logger.exception("exception while processing queue")

    return uwsgi.SPOOL_OK

uwsgi.spooler = process_spool
