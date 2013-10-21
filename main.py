
from app import app, db

from admin import admin
from api import *
from models import *
from views import *


if __name__ == '__main__':
    app.run()
