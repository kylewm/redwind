import unittest
from redwind import app, db
from redwind.models import User
from flask import redirect
from flask.ext.login import login_user, logout_user, current_user


class AppTestCase(unittest.TestCase):

    def setUp(self):
        app.config['DEBUG'] = False
        app.config['DEBUG_TB_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        db.create_all()

    def tearDown(self):
        self.app_context.pop()
        db.session.remove()
        db.drop_all()


class AuthedTestCase(AppTestCase):

    def _register_bypass_login(self):
        def bypass_login():
            user = User('example.com')
            user.authenticated = True
            login_user(user)
            return redirect('/')

        if not any(r.endpoint == 'bypass_login' for r in app.url_map.iter_rules()):
            app.add_url_rule('/bypass_login', 'bypass_login', bypass_login)

    def setUp(self):
        super(AuthedTestCase, self).setUp()
        self._register_bypass_login()
        self.client.get('/bypass_login')

    def tearDown(self):
        super(AuthedTestCase, self).tearDown()
        self.client.get('/logout')


class ViewsTest(AuthedTestCase):

    def test_empty_db(self):
        rv = self.client.get('/')
        self.assertTrue('<article' not in rv.get_data(as_text=True))

    def test_create_post(self):
        print('current_user', current_user)
        print('is authed', current_user.is_authenticated())

        rv = self.client.post('/save_new', data={
            'post_type': 'note',
            'content': 'This is a test note'})
        self.assertEqual(302, rv.status_code)

        rv = self.client.get(rv.location)
        print(rv.get_data(as_text=True))
        self.assertFalse(True)
