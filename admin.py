from app import app, db

from flask.ext.login import LoginManager, login_user, logout_user, current_user
from flask.ext.admin import Admin, BaseView, AdminIndexView, expose
from flask.ext.admin.contrib.sqlamodel import ModelView
from flask import Flask, url_for, redirect, render_template, request
from wtforms import form, fields, validators

import models

# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    login = fields.TextField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if not user.check_password(self.password.data):
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        return db.session.query(models.User).filter_by(login=self.login.data).first()


class RegistrationForm(form.Form):
    login = fields.TextField(validators=[validators.required()])
    email = fields.TextField()
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        if db.session.query(models.User).filter_by(login=self.login.data).count() > 0:
            raise validators.ValidationError('Duplicate username')


# Initialize flask-login
def init_login():
    login_manager = LoginManager()
    login_manager.setup_app(app)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(models.User).get(user_id)


class LoginView(BaseView):
    @expose('/', methods=('GET', 'POST'))
    def login_view(self):
        form = LoginForm(request.form)
        if request.method == 'POST' and form.validate():
            user = form.get_user()
            login_user(user, remember=True)
            return redirect(url_for('admin.index'))
        return self.render('form.html', form=form)

    def is_visible(self):
        return not current_user.is_authenticated()

class RegisterView(BaseView):
    @expose('/', methods=('GET', 'POST'))
    def register_view(self):
        form = RegistrationForm(request.form)
        if request.method == 'POST' and form.validate():
            user = models.User()
            form.populate_obj(user)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('admin.index'))
        return self.render('form.html', form=form)

    def is_visible(self):
        return not current_user.is_authenticated()


class LogoutView(BaseView):
    @expose('/')
    def logout_view(self):
        logout_user()
        return redirect(url_for('admin.index'))

    def is_visible(self):
        return current_user.is_authenticated()


# Create customized model view class
class AuthModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated()


# Create customized index view class
#class AuthAdminIndexView(AdminIndexView):
#    def is_accessible(self):
#        return current_user.is_authenticated()

admin = Admin(app, index_view=AdminIndexView())
admin.add_view(AuthModelView(models.Post, db.session))
admin.add_view(AuthModelView(models.Tag, db.session))
admin.add_view(AuthModelView(models.User, db.session))
admin.add_view(LoginView(name="Login"))
admin.add_view(LogoutView(name="Logout"))
admin.add_view(RegisterView(name="Register"))
