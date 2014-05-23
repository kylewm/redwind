from . import app
from . import redis

import json
import uuid


function_name_map = {}


class DelayedResult(object):
    def __init__(self, key):
        self.key = key
        self._rv = None

    @property
    def return_value(self):
        if self._rv is None:
            rv = redis.get(self.key)
            if rv is not None:
                self._rv = json.loads(rv.decode(encoding='UTF-8'))
        return self._rv


def queueable(f):
    def delay(*args, **kwargs):
        qkey = app.config['REDIS_QUEUE_KEY']
        key = '%s:result:%s' % (qkey, str(uuid.uuid4()))
        s = json.dumps({
            'func': f.__name__,
            'key': key,
            'args': args,
            'kwargs': kwargs
        }).encode(encoding='UTF-8')
        redis.rpush(app.config['REDIS_QUEUE_KEY'], s)
        return DelayedResult(key)

    function_name_map[f.__name__] = f
    f.delay = delay
    return f
