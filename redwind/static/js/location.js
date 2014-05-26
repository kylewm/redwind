(function(){
    $(document).ready(function() {
        $('.map').each(function (idx, element) {

            var lat = $(element).data('latitude');
            var lon = $(element).data('longitude');
            var loc = $(element).data('location');

            var OpenStreetMap_Mapnik = L.tileLayer('http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
	        attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
            });

            var OpenStreetMap_BlackAndWhite = L.tileLayer('http://{s}.www.toolserver.org/tiles/bw-mapnik/{z}/{x}/{y}.png', {
	        attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
            });


            var map = L.map(element, {
                center: [lat, lon],
                zoom: 13,
                layers: [OpenStreetMap_BlackAndWhite]
            });

            L.marker([lat, lon], {'title': loc}).addTo(map);

        });
    });
})();
