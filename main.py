
from app import app, db

from admin import admin, init_login
from models import *
from views import *

init_login()


if __name__ == '__main__':
    app.run()
