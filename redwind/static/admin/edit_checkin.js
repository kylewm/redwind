$(function() {
    "use strict";

    $('#new_venue_holder').hide();
    $('#new_venue_expander').click(function(event) {
        event.preventDefault();
        $('#select_venue_holder').hide();
        $('#new_venue_holder').show();

        var prevLat = $('#previous_venue_info').data('latitude');
        var prevLng = $('#previous_venue_info').data('longitude');
        if (prevLat && prevLng) {
            $('#new_venue_latitude').val(prevLat);
            $('#new_venue_longitude').val(prevLng);
        } else {
            navigator.geolocation.getCurrentPosition(function (position) {
                $('#new_venue_latitude').val(position.coords.latitude);
                $('#new_venue_longitude').val(position.coords.longitude);
            });
        }
    });

    $('select#venue').each(function (idx, venueList) {
        function updateVenueList(lat, lng) {
            $.getJSON(
                '/services/nearby?latitude=' + lat + '&longitude=' + lng,
                function appendToVenueList(blob) {
                    blob.venues.forEach(function (venue) {
                        $('<option value="' + venue.id + '">' + venue.name + ': ' + venue.geocode + '</option>').appendTo(venueList);
                    });
                }
            );
        }

        var prevLat = $('#previous_venue_info').data('latitude');
        var prevLng = $('#previous_venue_info').data('longitude');
        if (prevLat && prevLng) {
            updateVenueList(prevLat, prevLng);
        }
        else {
            navigator.geolocation.getCurrentPosition(function (position) {
                updateVenueList(
                    position.coords.latitude,
                    position.coords.longitude);
            });
        }
    });
});
