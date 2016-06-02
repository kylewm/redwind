import sys
import os
import tempfile
import shutil

from redwind import create_app
from redwind.extensions import db as rw_db
import pytest


CONFIG_FILE_CONTENT = """\
SECRET_KEY = 'lmnop8765309'
DEBUG = True
TESTING = True,
DEBUG_TB_ENABLED = False
SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
REDIS_URL = 'redis://localhost:911'
BYPASS_INDIEAUTH = False
PILBOX_URL = '/imageproxy'
"""


@pytest.yield_fixture
def app(request):
    """The redwind flask app, set up with an empty database and
    some sane defaults
    """

    def set_setting(key, value):
        from redwind.models import Setting
        s = Setting.query.get(key)
        if not s:
            s = Setting()
            s.key = key
            rw_db.session.add(s)
        s.value = value
        rw_db.session.commit()

    def bypass_login():
        from redwind.models import User
        from flask.ext.login import login_user
        from flask import redirect
        login_user(User('example.com'))
        return redirect('/')

    _, cfg_path = tempfile.mkstemp('redwind.cfg')
    with open(cfg_path, 'w') as f:
        f.write(CONFIG_FILE_CONTENT)

    rw_app = create_app(cfg_path)
    rw_app.add_url_rule('/', 'bypass_login', bypass_login)

    app_context = rw_app.app_context()
    app_context.push()
    assert str(rw_db.engine.url) == 'sqlite:///:memory:'

    rw_db.create_all()
    temp_upload_path = tempfile.mkdtemp()
    temp_imageproxy_path = tempfile.mkdtemp()
    rw_app.config['UPLOAD_PATH'] = temp_upload_path
    #rw_app.config['IMAGEPROXY_PATH'] = temp_imageproxy_path

    set_setting('posts_per_page', '15')
    set_setting('author_domain', 'example.com')
    set_setting('site_url', 'http://example.com')
    set_setting('timezone', 'America/Los_Angeles')
    rw_db.session.commit()

    yield rw_app

    assert str(rw_db.engine.url) == 'sqlite:///:memory:'
    shutil.rmtree(temp_upload_path)
    shutil.rmtree(temp_imageproxy_path)

    rw_db.session.remove()
    rw_db.drop_all()
    app_context.pop()


@pytest.fixture
def db(app):
    return rw_db


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
