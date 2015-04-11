from flask import request, jsonify, Blueprint, current_app
from redwind import hooks
from redwind import views
from redwind.extensions import db
from redwind.models import Post, Venue
from redwind.tasks import get_queue, async_app_context
import json
import requests


locations = Blueprint('locations', __name__)


def register(app):
    app.register_blueprint(locations)
    hooks.register('post-saved', reverse_geocode)
    hooks.register('venue-saved', reverse_geocode_venue)


def reverse_geocode(post, args):
    get_queue().enqueue(do_reverse_geocode_post, post.id, current_app.config)


def reverse_geocode_venue(venue, args):
    get_queue().enqueue(do_reverse_geocode_venue, venue.id, current_app.config)


def do_reverse_geocode_post(postid, app_config):
    with async_app_context(app_config):
        post = Post.load_by_id(postid)
        if post.location and 'latitude' in post.location \
           and 'longitude' in post.location:
            adr = do_reverse_geocode(post.location['latitude'],
                                     post.location['longitude'])
            # copy the dict so that the ORM recognizes
            # that it changed
            post.location = dict(post.location)
            post.location.update(adr)
            db.session.commit()


def do_reverse_geocode_venue(venueid, app_config):
    with async_app_context(app_config):
        venue = Venue.query.get(venueid)
        if venue.location and 'latitude' in venue.location \
           and 'longitude' in venue.location:
            adr = do_reverse_geocode(venue.location['latitude'],
                                     venue.location['longitude'])
            # copy the dict so the ORM actually recognizes
            # that it changed
            venue.location = dict(venue.location)
            venue.location.update(adr)
            venue.update_slug(views.geo_name(venue.location))
            db.session.commit()


def do_reverse_geocode(lat, lng):
    def region(adr):
        if adr.get('country_code') == 'us':
            return adr.get('state') or adr.get('county')
        else:
            return adr.get('county') or adr.get('state')

    current_app.logger.debug('reverse geocoding with nominatum')
    r = requests.get('http://nominatim.openstreetmap.org/reverse',
                     params={
                         'lat': lat,
                         'lon': lng,
                         'format': 'json'
                     })
    r.raise_for_status()

    data = json.loads(r.text)
    current_app.logger.debug(
        'received response %s', json.dumps(data, indent=True))

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
