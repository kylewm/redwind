var redwind = redwind || {};
redwind.location = (function() {
    function setupOpenStreeMap(element, lat, lon, loc) {
        console.log('setting up osm');
        console.log(element);

        var OpenStreetMap_Mapnik = L.tileLayer('//{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
	    attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
        });

        var OpenStreetMap_BlackAndWhite = L.tileLayer('//{s}.toolserver.org/tiles/bw-mapnik/{z}/{x}/{y}.png', {
	    attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
        });

        var map = L.map(element, {
            center: [lat, lon],
            zoom: 11,
            layers: [OpenStreetMap_Mapnik]
        });

        L.marker([lat, lon], {'title': loc}).addTo(map);
    }

    // exports
    return {
        'setupOpenStreetMap': setupOpenStreeMap
    };

}());


$(document).ready(function() {
    $('.map').each(function (idx, element) {
        var lat = $(element).data('latitude');
        var lon = $(element).data('longitude');
        var loc = $(element).data('location');
        redwind.location.setupOpenStreetMap(element, lat, lon, loc);
    });
});
