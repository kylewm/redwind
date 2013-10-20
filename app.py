from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flaskext.markdown import Markdown

app = Flask(__name__)
app.config.from_object('config.Configuration')

db = SQLAlchemy(app)

Markdown(app, extensions=['codehilite'])
