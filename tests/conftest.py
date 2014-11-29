import imp
import sys


class Configuration:
    pass

config = imp.new_module('config')
config.Configuration = Configuration
sys.modules['config'] = config

Configuration.SECRET_KEY = 'lmnop8765309'
Configuration.DEBUG = True
Configuration.DEBUG_TB_ENABLED = False
Configuration.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
Configuration.TESTING = True
Configuration.REDIS_URL = 'redis://localhost:911'
Configuration.BYPASS_INDIEAUTH = False

from redwind import app as rw_app, db as rw_db
import pytest


@rw_app.route('/bypass_login')
def bypass_login():
    from redwind.models import User
    from flask.ext.login import login_user
    from flask import redirect
    login_user(User('example.com'))
    return redirect('/')


@pytest.yield_fixture
def app(request):
    """The redwind flask app, set up with an empty database and
    some sane defaults
    """
    import tempfile
    import shutil

    def set_setting(key, value):
        from redwind.models import Setting
        s = Setting.query.get(key)
        if not s:
            s = Setting()
            s.key = key
            rw_db.session.add(s)
        s.value = value
        rw_db.session.commit()

    assert str(rw_db.engine.url) == 'sqlite:///:memory:'
    app_context = rw_app.app_context()
    app_context.push()
    rw_db.create_all()
    temp_image_path = tempfile.mkdtemp()
    rw_app.config['IMAGE_ROOT_PATH'] = temp_image_path

    set_setting('posts_per_page', '15')
    set_setting('author_domain', 'example.com')
    set_setting('site_url', 'http://example.com')
    set_setting('timezone', 'America/Los_Angeles')
    rw_db.session.commit()

    yield rw_app

    app_context.pop()
    shutil.rmtree(temp_image_path)
    assert str(rw_db.engine.url) == 'sqlite:///:memory:'
    rw_db.session.remove()
    rw_db.drop_all()


@pytest.fixture
def client(app):
    """Client that can be used to send mock requests
    """
    return app.test_client()


@pytest.yield_fixture
def auth(request, app, client):
    """Logs into the application as an administrator.
    """
    client.get('/bypass_login')
    yield
    client.get('/logout')
