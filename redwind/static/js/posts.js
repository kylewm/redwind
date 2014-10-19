(function(global) {
    "use strict";

    function setupAllMaps() {
        var maps = all('.map');
        if (maps.length > 0) {
            loadLeaflet(function() {
                each(maps,  function(map) {
                    var lat = map.dataset.latitude;
                    var lon = map.dataset.longitude;
                    var loc = map.dataset.location;
                    if (lat && lon) {
                        setupMap(map, lat, lon, loc);
                    }
                });
            });
        }
    }

    function setupMap(element, lat, lon, loc) {
        var tileset = L.tileLayer(
            'http://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri'
            });

        var map = L.map(element, {
            center: [lat, lon],
            zoom: 16,
            layers: [tileset],
            touchZoom: false,
            scrollWheelZoom: false,
        });

        L.marker([lat, lon], {'title': loc}).addTo(map);
    }

    function showPostControls(arrow, controls) {
        controls.style['display'] = 'inline';
        arrow.style['display'] = 'none';
    }

    setupAllMaps();

    each(all('article'), function(article) {
        var controls = first('.admin-post-controls', article),
        arrow = first('.admin-post-controls-arrow', article);

        if (arrow && controls) {
            arrow.addEventListener('click', function (event) {
                event.preventDefault();
                showPostControls(arrow, controls);
            });
        }
    });

    // commented out until I can figure out how not to catch events
    // that would otherwise be handled (e.g., links)
    /*each(all('.h-feed article'), function(article) {
        article.addEventListener('mouseover', function(event) {
            article.classList.add('highlight');
        });
        article.addEventListener('mouseout', function(event) {
            article.classList.remove('highlight');
        });
        article.addEventListener('click', function(event) {
            var permalink = first('.post-metadata a.u-url', article).href;
            window.location = permalink;
        });
    });*/

    global.setupMap = setupMap;

})(this);
