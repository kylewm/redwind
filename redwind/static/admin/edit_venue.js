(function (global) {

    var marker;

    function placeLocationMarker(map, lat, lng) {
        if (marker) {
            map.removeLayer(marker);
        }
        marker = L.marker([lat, lng]).addTo(map);
    }

    function fillGeocode(lat, lng) {
        $.get(SITE_ROOT+'/services/geocode?latitude=' + lat + '&longitude=' + lng, function (addr) {
            console.log(addr);
            
            var geocodeField = first('#geocode');
            if (addr.locality && addr.region) {
                geocodeField.value = addr.locality + ', ' + addr.region;
            } else if (addr.postal_code && addr.region) {
                geocodeField.value = addr.postal_code + ', ' + addr.region;
            } else if (addr.region) {
                geocodeField.value = addr.region;
            }
        });
    }

    function setupMap(element, lat, lon, wheelZoom, zoom) {
        var tileset = L.tileLayer(
            'http://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri',
                noWrap: true,
            });

        var map = L.map(element, {
            center: [lat, lon],
            zoom: zoom || 16,
            layers: [tileset],
            touchZoom: wheelZoom,
            scrollWheelZoom: wheelZoom,
        });

        return map;
    }

    function setupMapClickPosition(map) {
        map.on('click', function (e) {
            placeLocationMarker(map, e.latlng.lat, e.latlng.lng);
            fillGeocode(e.latlng.lat, e.latlng.lng);
            $('#latitude').val(e.latlng.lat);
            $('#longitude').val(e.latlng.lng);
        });
    }

    function setupVenueMap() {
        var $venueMap = $('#venue-map');
        if ($venueMap) {
            var latField = $('#latitude');
            var lonField = $('#longitude');
            $venueMap.text('loading...');

            if (latField.val() && lonField.val()) {
                var map = setupMap($venueMap.get(0), latField.val(), lonField.val(), true);
                placeLocationMarker(map, latField.val(), lonField.val());
                setupMapClickPosition(map);
            } else {
                navigator.geolocation.getCurrentPosition(
                    function success(position) {
                        var lat, lon;
                        latField.val(lat = position.coords.latitude);
                        lonField.val(lon = position.coords.longitude);
                        var map = setupMap($venueMap.get(0), lat, lon, true);
                        setupMapClickPosition(map);
                        placeLocationMarker(map, lat, lon);
                        fillGeocode(lat, lon);
                    }, function failure(error) {
                        console.log(error);
                        var map = setupMap($venueMap.get(0), 0, 0, true);
                        setupMapClickPosition(map);
                        placeLocationMarker(map, 0, 0);
                    }, {
                        'timeout': 5000,
                    });
            }
        }
    }

    setupVenueMap();

})(this);
