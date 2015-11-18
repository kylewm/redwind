from redwind import create_app
from redwind.models import Contact
from redwind.extensions import db

app = create_app()
with app.app_context():
    for contact in Contact.query.all():
        urls = []
        if 'twitter' in contact.social:
            urls.append('https://twitter.com/%s' % contact.social['twitter'])
        if 'facebook' in contact.social:
            urls.append('https://www.facebook.com/%s' % contact.social['facebook'])
        print(urls)
        contact.social = urls
    db.session.commit()
                                                            
