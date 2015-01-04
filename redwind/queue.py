from . import app
from . import db
import time
import uuid
import pickle


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())
    updated = db.Column(db.DateTime, onupdate=db.func.now())
    key = db.Column(db.String(128))
    params = db.Column(db.PickleType)
    result = db.Column(db.PickleType)
    complete = db.Column(db.Boolean)


class SqlQueueImpl:
    def enqueue(self, func, *args, **kwargs):
        job = Job()
        job.key = str(uuid.uuid4())
        job.params = (func, args, kwargs)
        job.complete = False
        db.session.add(job)
        db.session.commit()
        return job.key

    def query(self, key):
        job = Job.query.filter_by(key).first()
        if job:
            if not job.complete:
                return 'queued'
            return job.result

    def run(self):
        with app.app_context():
            while True:
                for job in Job.query.filter_by(complete=False):
                    try:
                        func, args, kwargs = job.params
                        result = func(*args, **kwargs)
                    except:
                        app.logger.exception('error while processing task')
                    finally:
                        # I don't totally understand why, but in some
                        # cases, the queued job mangles the session, so it
                        # seems safest to refetch the job before modifying
                        # it
                        job = Job.query.get(job.id)
                        job.result = result
                        job.complete = True
                        db.session.commit()
                time.sleep(10)


class RedisQueueImpl:
    RV_TTL = 86400

    def __init__(self, redis_url, redis_qkey):
        import redis
        self.redis = redis.StrictRedis.from_url(redis_url)
        self.qkey = redis_qkey

    def enqueue(self, func, *args, **kwargs):
        key = '%s:result:%s' % (self.qkey, str(uuid.uuid4()))
        self.redis.rpush(
            self.qkey, pickle.dumps((func, key, args, kwargs)))
        self.redis.set(key, pickle.dumps('queued'))
        self.redis.expire(key, self.RV_TTL)
        return key

    def query(self, key):
        result = self.redis.get(key)
        if result is not None:
            return pickle.loads(result)

    def run(self):
        with app.app_context():
            while True:
                msg = self.redis.blpop(self.qkey)
                func, key, args, kwargs = pickle.loads(msg[1])
                try:
                    app.logger.debug('executing %s with args=%s kwargs=%s',
                                     func, args, kwargs)
                    rv = func(*args, **kwargs)
                except Exception as e:
                    app.logger.exception('exception while running queued task')
                    rv = e
                self.redis.set(key, pickle.dumps(rv))
                self.redis.expire(key, self.RV_TTL)


def get_impl():
    if get_impl.cached:
        return get_impl.cached
    redis_url = app.config.get('REDIS_URL')
    redis_qkey = app.config.get('REDIS_QUEUE_KEY')
    if redis_url and redis_qkey:
        app.logger.debug('started queue with RedisQueueImpl %s;%s',
                         redis_url, redis_qkey)
        get_impl.cached = impl = RedisQueueImpl(redis_url, redis_qkey)
    else:
        app.logger.debug('started queue with SqlQueueImpl')
        get_impl.cached = impl = SqlQueueImpl()
    return impl

get_impl.cached = None


def enqueue(func, *args, **kwargs):
    return get_impl().enqueue(func, *args, **kwargs)


def query(key):
    return get_impl().query(key)


def run():
    return get_impl().run()
