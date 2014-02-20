
from app import app, db

from models import *
from views import *


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
