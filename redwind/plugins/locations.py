import requests
import json
from .. import hooks
from ..models import Post, Venue
from ..tasks import queue, session_scope
from .. import views
from flask import request, jsonify, Blueprint, current_app
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

locations = Blueprint('locations', __name__)


def register(app):
    app.register_blueprint(locations)
    hooks.register('post-saved', reverse_geocode)
    hooks.register('venue-saved', reverse_geocode_venue)


def reverse_geocode(post, args):
    queue.enqueue(do_reverse_geocode_post, post.id)


def reverse_geocode_venue(venue, args):
    queue.enqueue(do_reverse_geocode_venue, venue.id, current_app.config)


def do_reverse_geocode_post(postid, app_config):
    with session_scope(app_config) as session:
        post = Post.load_by_id(postid, session)
        if post.location and 'latitude' in post.location \
           and 'longitude' in post.location:
            adr = do_reverse_geocode(post.location['latitude'],
                                     post.location['longitude'])
            # copy the dict so that the ORM recognizes
            # that it changed
            post.location = dict(post.location)
            post.location.update(adr)
            session.commit()


def do_reverse_geocode_venue(venueid, app_config):
    with session_scope(app_config) as session:
        venue = session.query(Venue).get(venueid)
        if venue.location and 'latitude' in venue.location \
           and 'longitude' in venue.location:
            adr = do_reverse_geocode(venue.location['latitude'],
                                     venue.location['longitude'])
            # copy the dict so the ORM actually recognizes
            # that it changed
            venue.location = dict(venue.location)
            venue.location.update(adr)
            venue.update_slug(views.geo_name(venue.location))
            session.commit()


def do_reverse_geocode(lat, lng):
    def region(adr):
        if adr.get('country_code') == 'us':
            return adr.get('state') or adr.get('county')
        else:
            return adr.get('county') or adr.get('state')

    logger.debug('reverse geocoding with nominatum')
    r = requests.get('http://nominatim.openstreetmap.org/reverse',
                     params={
                         'lat': lat,
                         'lon': lng,
                         'format': 'json'
                     })
    r.raise_for_status()

    data = json.loads(r.text)
    logger.debug('received response %s', json.dumps(data, indent=True))

    adr = data.get('address', {})

    # hat-tip https://gist.github.com/barnabywalters/8318401
    return {
        'street_address': adr.get('road'),
        'extended_address': adr.get('suburb'),
        'locality': (adr.get('hamlet')
                     or adr.get('village')
                     or adr.get('town')
                     or adr.get('city')
                     or adr.get('locality')
                     or adr.get('suburb')
                     or adr.get('county')),
        'region': region(adr),
        'country_name': adr.get('country'),
        'postal_code': adr.get('postcode'),
        'country_code': adr.get('country_code'),
    }


@locations.route('/services/geocode')
def reverse_geocode_service():
    lat = request.args.get('latitude')
    lng = request.args.get('longitude')
    return jsonify(do_reverse_geocode(lat, lng))
