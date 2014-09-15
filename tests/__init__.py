import unittest
from redwind import app, db
from redwind.models import User
from flask import redirect
from flask.ext.login import login_user, logout_user, current_user
import re


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
        user = User('example.com')
        db.session.add(user)
        db.session.commit()

        def bypass_login():
            user = User.load('example.com')
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
        self.client.get('/logout')
        super(AuthedTestCase, self).tearDown()


class ViewsTest(AuthedTestCase):

    def test_empty_db(self):
        """Make sure there are no articles when the database is empty"""
        rv = self.client.get('/')
        self.assertNotIn('<article', rv.get_data(as_text=True))

    def test_create_post(self):
        """Create a simple post as the current user"""
        rv = self.client.post('/save_new', data={
            'post_type': 'note',
            'content': 'This is a test note'})
        self.assertEqual(302, rv.status_code)
        self.assertTrue(re.match('.*/note/\d+/\d+/\d+/1/this-is-a-test-note$',
                                 rv.location))
        # follow the redirect
        rv = self.client.get(rv.location)
        self.assertIn('This is a test note', rv.get_data(as_text=True))
