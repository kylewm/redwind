from app import app, db
from auth import *

from flask.ext.admin import Admin, BaseView, AdminIndexView, expose
from flask.ext.admin.contrib.sqla import ModelView

import models

# Create customized model view class
class AuthModelView(ModelView):
    def is_accessible(self):
        return is_authenticated()
        
    def _handle_view(self, name, *args, **kwargs):
        if not self.is_accessible():
            return authenticate()

# Create customized index view class
class AuthAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not is_authenticated():
            return authenticate()
        return super(AuthAdminIndexView, self).index()


admin = Admin(app, index_view=AuthAdminIndexView())
admin.add_view(AuthModelView(models.Post, db.session))
admin.add_view(AuthModelView(models.Tag, db.session))
admin.add_view(AuthModelView(models.User, db.session))
