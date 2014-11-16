(function (global) {

    var marker;

    function placeLocationMarker(map, lat, lng) {
        if (marker) {
            map.removeLayer(marker);
        }
        marker = L.marker([lat, lng]).addTo(map);
    }

    function fillGeocode(lat, lng) {
        var xhr = Http.get(SITE_ROOT+'/services/geocode?latitude=' + lat + '&longitude=' + lng);
        Http.send(xhr).then(
            function (xhr) {
                var addr = JSON.parse(xhr.responseText);
                console.log(addr);

                var geocodeField = first('#geocode');
                if (addr.locality && addr.region) {
                    geocodeField.value = addr.locality + ', ' + addr.region;
                } else if (addr.postal_code && addr.region) {
                    geocodeField.value = addr.postal_code + ', ' + addr.region;
                } else if (addr.region) {
                    geocodeField.value = addr.region;
                }
            },
            function (xhr) {
                console.log('geocode request failed ' + xhr);
            }
        )
    }

    function setupMapClickPosition(map, latField, lonField) {
        map.on('click', function (e) {
            placeLocationMarker(map, e.latlng.lat, e.latlng.lng);
            fillGeocode(e.latlng.lat, e.latlng.lng);
            latField.value = e.latlng.lat;
            lonField.value = e.latlng.lng;
        });
    }

    function setupVenueMap() {
        var venueMap = first('#venue-map');
        if (venueMap) {
            var latField = first('#latitude');
            var lonField = first('#longitude');
            venueMap.textContent = 'loading...';
            loadLeaflet(function () {
                if (latField.value && lonField.value) {
                    var map = setupMap(venueMap, latField.value, lonField.value, true);
                    placeLocationMarker(map, latField.value, lonField.value);
                    setupMapClickPosition(map, latField, lonField);
                } else {
                    navigator.geolocation.getCurrentPosition(function (position) {
                        var lat, lon;
                        latField.value = lat = position.coords.latitude;
                        lonField.value = lon = position.coords.longitude;
                        var map = setupMap(venueMap, lat, lon, true);
                        setupMapClickPosition(map, latField, lonField);
                        placeLocationMarker(map, lat, lon);
                        fillGeocode(lat, lon);
                    });
                }
            });
        }
    }

    setupVenueMap();

})(this);
