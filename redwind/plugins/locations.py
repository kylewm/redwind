import requests
import json
from .. import app
from .. import db
from .. import hooks
from .. import models
from .. import queue


def register():
    hooks.register('post-saved', reverse_geocode)


def reverse_geocode(post, args):
    queue.enqueue(do_reverse_geocode, post.shortid)


def do_reverse_geocode(postid):
    def region(adr):
        if adr.get('country_code') == 'us':
            return adr.get('state') or adr.get('county')
        else:
            return adr.get('county') or adr.get('state')

    with app.app_context():
        post = models.Post.load_by_shortid(postid)
        if post.location and post.location.latitude \
           and post.location.longitude:
            app.logger.debug('reverse geocoding with nominatum')
            r = requests.get('http://nominatim.openstreetmap.org/reverse',
                             params={
                                 'lat': post.location.latitude,
                                 'lon': post.location.longitude,
                                 'format': 'json'
                             })
            r.raise_for_status()

            data = json.loads(r.text)
            app.logger.debug('received response %s',
                             json.dumps(data, indent=True))

            # hat-tip https://gist.github.com/barnabywalters/8318401
            adr = data.get('address', {})

            post.location.street_address = adr.get('road')
            post.location.extended_address = adr.get('suburb')
            post.location.locality = (adr.get('hamlet') or adr.get('village') or adr.get('town')
                                      or adr.get('city') or adr.get('locality'))
            post.location.region = region(adr)
            post.location.country_name = adr.get('country')
            post.location.postal_code = adr.get('postcode')
            post.location.country_code = adr.get('country_code')

            db.session.commit()
