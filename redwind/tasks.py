from contextlib import contextmanager
import sqlalchemy
import sqlalchemy.orm
from redis import StrictRedis
import rq

redis = StrictRedis()
queue = rq.Queue('redwind:low', connection=redis)


@contextmanager
def session_scope(app_config):
    """Provide a transactional scope around a series of operations."""

    dburi = app_config['SQLALCHEMY_DATABASE_URI']
    options = {}
    engine = sqlalchemy.create_engine(dburi, **options)
    session = sqlalchemy.orm.sessionmaker(bind=engine)()

    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
