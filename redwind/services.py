from . import app
from .models import Venue
from .views import geo_name
from flask import request, jsonify, redirect, url_for
import datetime
import mf2py
import mf2util


@app.route('/api/mf2')
def old_convert_mf2():
    return redirect(url_for('convert_mf2'))


@app.route('/services/mf2')
def convert_mf2():
    url = request.args.get('url')
    if url:
        p = mf2py.Parser(url=url)
        json = p.to_dict()
        return jsonify(json)
    return """
<html><body>
<h1>mf2py</h1>
<form><label>URL to parse: <input name="url"></label>
<input type="Submit">
</form></body></html> """


@app.route('/api/mf2util')
def old_convert_mf2util():
    return redirect(url_for('convert_mf2util'))


@app.route('/services/mf2util')
def convert_mf2util():
    def dates_to_string(json):
        if isinstance(json, dict):
            return {k: dates_to_string(v) for (k, v) in json.items()}
        if isinstance(json, list):
            return [dates_to_string(v) for v in json]
        if isinstance(json, datetime.date) or isinstance(json, datetime.datetime):
            return json.isoformat()
        return json

    url = request.args.get('url')
    if url:
        d = mf2py.Parser(url=url).to_dict()
        if mf2util.find_first_entry(d, ['h-feed']):
            json = mf2util.interpret_feed(d, url)
        else:
            json = mf2util.interpret(d, url)
        return jsonify(dates_to_string(json))
    return """
<html><body>
<h1>mf2util</h1>
<form><label>URL to parse: <input name="url"></label>
<input type="Submit">
</form></body></html>"""


@app.route('/services/fetch_profile')
def fetch_profile():
    url = request.args.get('url')
    if not url:
        return """
<html><body>
<h1>Fetch Profile</h1>
<form><label>URL to fetch: <input name="url"></label>
<input type="Submit">
</form></body></html>"""

    from .util import TWITTER_PROFILE_RE, FACEBOOK_PROFILE_RE
    try:
        name = None
        twitter = None
        facebook = None
        image = None

        d = mf2py.Parser(url=url).to_dict()

        relmes = d['rels'].get('me', [])
        for alt in relmes:
            m = TWITTER_PROFILE_RE.match(alt)
            if m:
                twitter = m.group(1)
            else:
                m = FACEBOOK_PROFILE_RE.match(alt)
                if m:
                    facebook = m.group(1)

        # check for h-feed
        hfeed = next((item for item in d['items']
                      if 'h-feed' in item['type']), None)
        if hfeed:
            authors = hfeed.get('properties', {}).get('author')
            images = hfeed.get('properties', {}).get('photo')
            if authors:
                if isinstance(authors[0], dict):
                    name = authors[0].get('properties', {}).get('name')
                    image = authors[0].get('properties', {}).get('photo')
                else:
                    name = authors[0]
            if images and not image:
                image = images[0]

        # check for top-level h-card
        for item in d['items']:
            if 'h-card' in item.get('type', []):
                if not name:
                    name = item.get('properties', {}).get('name')
                if not image:
                    image = item.get('properties', {}).get('photo')

        return jsonify({
            'name': name,
            'image': image,
            'twitter': twitter,
            'facebook': facebook,
        })

    except BaseException as e:
        resp = jsonify({'error': str(e)})
        resp.status_code = 400
        return resp


@app.route('/services/nearby')
def nearby_venues():
    lat = float(request.args.get('latitude'))
    lng = float(request.args.get('longitude'))
    venues = Venue.query.all()

    venues.sort(key=lambda venue: (venue.location['latitude'] - lat) ** 2
                + (venue.location['longitude'] - lng) ** 2)

    return jsonify({
        'venues': [{
            'id': venue.id,
            'name': venue.name,
            'latitude': venue.location['latitude'],
            'longitude': venue.location['longitude'],
            'geocode': geo_name(venue.location),
        } for venue in venues[:10]]
    })
