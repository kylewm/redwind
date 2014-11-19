import redwind
from redwind.models import User, Setting
from flask import redirect
from flask.ext.login import login_user
import pytest
import logging

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope='module')
def app(request):
    """The redwind flask app, set up with an empty database and
    some sane defaults
    """
    def set_setting(key, value):
        s = Setting.query.get('key')
        if not s:
            s = Setting()
            s.key = key
            redwind.db.session.add(s)
        s.value = value

    app = redwind.app
    db = redwind.db
    app.config['DEBUG'] = False
    app.config['DEBUG_TB_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
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


@pytest.fixture(scope='module')
def client(app):
    """Client that can be used to send mock requests
    """
    return app.test_client()


@pytest.fixture(scope='module')
def auth(request, app, client):
    """Logs into the application as an administrator.
    """
    def bypass_login():
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


@pytest.fixture
def mox(request):
    from mox import Mox
    m = Mox()

    def fin():
        m.UnsetStubs()
        m.VerifyAll()
    request.addfinalizer(fin)
    return m
