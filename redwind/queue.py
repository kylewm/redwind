from . import app
from . import db
import time
import uuid


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())
    updated = db.Column(db.DateTime, onupdate=db.func.now())
    key = db.Column(db.String(128))
    params = db.Column(db.PickleType)
    result = db.Column(db.PickleType)
    complete = db.Column(db.Boolean)


def enqueue(func, *args, **kwargs):
    job = Job()
    job.key = str(uuid.uuid4())
    job.params = (func, args, kwargs)
    job.complete = False
    db.session.add(job)
    db.session.commit()
    return job.key


def run():
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
