from . import contexts
from . import util
from .models import Venue
from .views import geo_name

from bs4 import BeautifulSoup
from flask import request, jsonify, redirect, url_for, Blueprint, current_app, render_template
import datetime
import mf2py
import mf2util
import requests
import sys
import urllib

services = Blueprint('services', __name__)

USER_AGENT = 'Red Wind (https://github.com/kylewm/redwind)'

@services.route('/services/fetch_profile')
def fetch_profile():
    url = request.args.get('url')
    if not url:
        return """
<html><body>
<h1>Fetch Profile</h1>
<form><label>URL to fetch: <input name="url"></label>
<input type="Submit">
</form></body></html>"""

    try:
        name = None
        image = None

        d = mf2py.Parser(url=url).to_dict()

        relmes = d['rels'].get('me', [])

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
            'social': relmes,
        })

    except BaseException as e:
        resp = jsonify({'error': str(e)})
        resp.status_code = 400
        return resp


@services.route('/services/nearby')
def nearby_venues():
    lat = float(request.args.get('latitude'))
    lng = float(request.args.get('longitude'))
    venues = Venue.query.all()

    venues.sort(key=lambda venue: (float(venue.location['latitude']) - lat) ** 2
                + (float(venue.location['longitude']) - lng) ** 2)

    return jsonify({
        'venues': [{
            'id': venue.id,
            'name': venue.name,
            'latitude': venue.location['latitude'],
            'longitude': venue.location['longitude'],
            'geocode': geo_name(venue.location),
        } for venue in venues[:10]]
    })


@services.route('/services/fetch_context')
def fetch_context_service():
    results = []
    for url in request.args.getlist('url[]'):
        ctx = contexts.create_context(url)
        results.append({
            'title': ctx.title,
            'permalink': ctx.permalink,
            'html': render_template(
                'admin/_context.jinja2', type=request.args.get('type'),
                context=ctx),
        })

    return jsonify({'contexts': results})


@services.route('/yt/<video>/<slug>/')
def youtube_shortener(video, slug):
    return redirect('https://youtube.com/watch?v={}'.format(video))


@services.route('/services/youtube/')
def create_youtube_link():
    url = request.args.get('url')
    if url:
        m = util.YOUTUBE_RE.match(url)
        if m:
            video_id = m.group(1)
            resp = requests.get(url)
            soup = BeautifulSoup(resp.text)
            title = soup.find('meta', {'property':'og:title'}).get('content')
            if title:
                url = url_for('.youtube_shortener', video=video_id, slug=util.slugify(title), _external=True)
                return """<a href="{}">{}</a>""".format(url, url)

    return """<form><input name="url"/><input type="submit"/></form>"""
