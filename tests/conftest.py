from config import Configuration
Configuration.SECRET_KEY = 'lmnop8765309'
Configuration.DEBUG = False
Configuration.DEBUG_TB_ENABLED = False
Configuration.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
Configuration.TESTING = True
Configuration.REDIS_URL = 'redis://localhost:911'

import redwind
from flask import redirect
from flask.ext.login import login_user
import pytest
import logging

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def app(request):
    """The redwind flask app, set up with an empty database and
    some sane defaults
    """
    app = redwind.app
    db = redwind.db
    def set_setting(key, value):
        from redwind.models import Setting
        s = Setting.query.get(key)
        if not s:
            s = Setting()
            s.key = key
            db.session.add(s)
        s.value = value
        db.session.commit()

    assert str(db.engine.url)  == 'sqlite:///:memory:'
    app_context = app.app_context()
    app_context.push()
    
    db.create_all()
    set_setting('posts_per_page', '15')
    set_setting('author_domain', 'example.com')
    set_setting('site_url', 'http://example.com')
    set_setting('timezone', 'America/Los_Angeles')
    db.session.commit()

    def fin():
        app_context.pop()
        db.session.remove()
        db.drop_all()
    request.addfinalizer(fin)

    return app


@pytest.fixture
def client(app):
    """Client that can be used to send mock requests
    """
    return app.test_client()


@pytest.fixture
def auth(request, app, client):
    """Logs into the application as an administrator.
    """
    def bypass_login():
        from redwind.models import User
        user = User('example.com')
        login_user(user)
        return redirect('/')

    if not any(r.endpoint == 'bypass_login' for r in app.url_map.iter_rules()):
        app.add_url_rule('/bypass_login', 'bypass_login', bypass_login)

    client.get('/bypass_login')

    def fin():
        client.get('/logout')
    request.addfinalizer(fin)
    return True
