"""
Generate static map images
"""
from redwind import imageproxy
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

    return imageproxy.construct_url(
        'http://static-maps.kylewm.com/img.php?'
        + urllib.parse.urlencode(args))
