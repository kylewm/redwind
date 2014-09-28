from redwind.models import Contact, Nick, AddressBook
from redwind import db
from redwind.util import filter_empty_keys


for name, entry in AddressBook().entries.items():
    contact = Contact()
    contact.name = name
    contact.image = entry.get('photo')
    contact.url = entry.get('url')
    contact.social = filter_empty_keys(
        {'twitter': entry.get('twitter'), 'facebook': entry.get('facebook')})
    if 'twitter' in entry:
        nick = Nick()
        nick.name = entry.get('twitter')
        contact.nicks = [nick]
        db.session.add(nick)
    db.session.add(contact)

db.session.commit()
