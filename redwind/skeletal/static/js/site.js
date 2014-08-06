var redwind = redwind || {};

redwind.location = {
    setupOpenStreetMap: function(element, lat, lon, loc) {
        // var OpenStreetMap_Mapnik = L.tileLayer('//{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
	//     attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
        // });

        // var OpenStreetMap_BlackAndWhite = L.tileLayer('//{s}.toolserver.org/tiles/bw-mapnik/{z}/{x}/{y}.png', {
	//   attribution: '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
        // });

        var Esri_WorldStreetMap = L.tileLayer('http://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012'
        });

        var map = L.map(element, {
            center: [lat, lon],
            zoom: 16,
            layers: [Esri_WorldStreetMap]
        });

        L.marker([lat, lon], {'title': loc}).addTo(map);
    },
};

redwind.posts  = {

    postTypes: [ 'note', 'checkin', 'reply', 'share', 'like', 'photo', 'bookmark'],

    showPartialEditor: function (type) {
        var self = this;
        $.get('/new/' + type + '?partial=1', '',
              function(result) {
                  $('#composition-area').empty().append(result);
                  redwind.editor.handleEvents();
              });
    },

    showPostControls: function(arrow) {
        var post = arrow.closest('article');
        var controls = post.find('.admin-post-controls');
        controls.css('display', 'inline');
        arrow.replaceWith(controls);
    },
}

redwind.editor = {

    handleEvents: function() {
        $("#edit_form a.top_tag").click(function(event) {
            event.preventDefault();
            var tagValue = $(this).html();
            $("#edit_form #tags").val(function(i, val) {
                return val + (val ? ',' : '') + tagValue;
            });
        });
    },

    setupCheckinMap: function(element) {
        navigator.geolocation.getCurrentPosition(function(position) {
            var lat = position.coords.latitude.toFixed(3);
            var lon = position.coords.longitude.toFixed(3);
            $('#latitude').val(lat);
            $('#longitude').val(lon);
            var map = $('#checkin-map').get(0);
            redwind.location.setupOpenStreetMap(map, lat, lon, 'new location');
        });
    },

    addImageLink: function(file) {
        var filename = file.name.replace(' ', '_');
        $('#content').val(
            $('#content').val() + '\n![' + filename + '](' + filename + ')');
    }
};

/* register events */
$(document).ready(function() {
    redwind.editor.handleEvents();

    $(redwind.posts.postTypes).each(function (i, type) {
        $('#new-' + type).click(function(event) {
            event.preventDefault();
            redwind.posts.showPartialEditor(type);
        });
    });

    $('.admin-post-controls-arrow').click(function (event) {
        event.preventDefault();
        redwind.posts.showPostControls($(event.currentTarget));
    });

    $('.map').each(function (idx, element) {
        var lat = $(element).data('latitude');
        var lon = $(element).data('longitude');
        var loc = $(element).data('location');
        if (lat && lon) {
            redwind.location.setupOpenStreetMap(element, lat, lon, loc);
        }
    });

    //$('#syndication_textarea').css('display','none');
    //$('#audience_textarea').css('display', 'none');

    $('#edit_form #syndication_expander').click(function(){
        var textarea = $('#syndication_textarea');
        var closed = textarea.css('display') == 'none';
        if (closed) {
            textarea.css('display', '');
        }else {
            textarea.css('display', 'none');
        }
        $(this).toggleClass('fa-plus-square-o', !closed);
        $(this).toggleClass('fa-minus-square-o', closed);
    });

    $('#edit_form #audience_expander').click(function(){
        var textarea = $('#audience_textarea');
        var closed = textarea.css('display') == 'none';
        if (closed) {
            textarea.css('display', '');
        }else {
            textarea.css('display', 'none');
        }
        $(this).toggleClass('fa-plus-square-o', !closed);
        $(this).toggleClass('fa-minus-square-o', closed);
    });

    $('#get_coords_button').change(function() {
        if (this.checked) {
            navigator.geolocation.getCurrentPosition(function(position) {
                $('#latitude').val(position.coords.latitude.toFixed(3));
                $('#longitude').val(position.coords.longitude.toFixed(3));
            });
        }
        else {
            $('#latitude').val('');
            $('#longitude').val('');
        }
    });

    $('#edit_form #image_upload_button').change(function() {
        $('#uploads').empty();
        for (var ii = 0 ; ii < this.files.length ; ii++) {
            (function(file) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    var link = $('<a>');
                    link.append('<img style="max-width: 150px; max-height: 150px;" src="' + e.target.result + '"/>' + file.name);
                    $('#uploads').append($('<ul>').append(link));
                    link.click(function(){
                        redwind.editor.addImageLink(file);
                    });
                };
                reader.readAsDataURL(file);
            })(this.files[ii]);
        }
    });

});
