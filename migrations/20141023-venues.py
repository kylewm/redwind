from redwind import db
from redwind.models import Venue

db.create_all()
db.engine.execute(
    'ALTER TABLE location ADD COLUMN venue_id INTEGER REFERENCES venue(id)')
db.engine.execute(
    'ALTER TABLE post ADD COLUMN venue_id INTEGER REFERENCES venue(id)')
