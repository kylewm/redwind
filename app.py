from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension

app = Flask(__name__)
app.config.from_object('config.Configuration')
app.jinja_env.add_extension('jinja2.ext.i18n')

db = SQLAlchemy(app)
toolbar = DebugToolbarExtension(app)
