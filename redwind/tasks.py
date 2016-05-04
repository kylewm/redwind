from contextlib import contextmanager
from redis import StrictRedis
import rq


_queue = None


def get_queue():
    global _queue
    if _queue is None:
        _queue = create_queue()
    return _queue


def create_queue():
    """Connect to Redis and create the RQ. Since this is not imported
    directly, it is a convenient place to mock for tests that don't
    care about the queue.
    """
    redis = StrictRedis()
    return rq.Queue('redwind:low', connection=redis)


@contextmanager
def async_app_context(app_config):
    from redwind import create_app
    app = create_app(app_config, is_queue=True)
    with app.app_context():
        yield
