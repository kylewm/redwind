import json
blob = json.load(open('kylewm.com.json'))
from config import Configuration
Configuration.SQLALCHEMY_DATABASE_URI = 'postgres:///redwind'
from redwind import db
from redwind.importer import *

db.drop_all()
db.create_all()
import_all(blob)
