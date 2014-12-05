"""
Generate static map images
"""
from flask import url_for
from redwind import app
from redwind import util
import hashlib
import os
import urllib.parse

# get_map_image(600, 400, 33, -88, 13, [])
# get_map_image(600, 400, 33, -88, 13, [Marker(33, -88)])


class Marker:
    def __init__(self, lat, lng, icon='dot-small-blue'):
        self.lat = lat
        self.lng = lng
        self.icon = icon


def get_map_image(width, height, maxzoom, markers):
    # create the URL
    args = [
        ('width', width),
        ('height', height),
        ('maxzoom', maxzoom),
        ('basemap', 'streets'),
    ] + [
        ('marker[]', 'lat:{};lng:{};icon:{}'.format(m.lat, m.lng, m.icon))
        for m in markers
    ]

    query = urllib.parse.urlencode(args)

    m = hashlib.md5()
    m.update(bytes(query, 'utf-8'))
    hash = m.hexdigest()

    relpath = os.path.join('map', hash + '.png')
    abspath = os.path.join(util.image_root_path(), app.static_folder, relpath)

    if not os.path.exists(abspath):
        map_url = 'http://static-maps.kylewm.com/img.php?' + query
        util.download_resource(map_url, abspath)

    return url_for('static', filename=relpath)
