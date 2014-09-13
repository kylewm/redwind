import json
import os
from flask.ext.login import login_user

from . import app
from . import models
from . import queue
from . import redis

if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    app.logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler('logs/queue.log', maxBytes=1048576,
                                       backupCount=5)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)


def queue_daemon(app, rv_ttl=86400):
    while True:
        msg = redis.blpop(app.config['REDIS_QUEUE_KEY'])
        blob = json.loads(msg[1].decode(encoding='UTF-8'))
        func_name = blob['func']
        key = blob['key']
        args = blob['args']
        kwargs = blob['kwargs']

        func = queue.function_name_map.get(func_name)
        app.logger.info('executing function %s (%s) with args %s, kwargs %s',
                        func_name, func, args, kwargs)
        try:
            with app.test_request_context():
                user = models.User.query.first()
                login_user(user)
                rv = func(*args, **kwargs)
        except Exception as e:
            app.logger.exception('unexpected error processing queue')
            rv = str(e)

        app.logger.debug('finished function %s. got return value %s', func_name, rv)
        if rv is not None:
            redis.set(key, json.dumps(rv))
            redis.expire(key, rv_ttl)
