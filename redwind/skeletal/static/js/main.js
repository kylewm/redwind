requirejs.config({
    baseUrl: 'static/js',
    paths: {
        "leaflet": "//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet"
    }
});

var Util = {

    forEach: function (array, callback, scope) {
        for (var i = 0; i < array.length; i++) {
            callback.call(scope, i, array[i]); // passes back stuff we need
        }
    },

    // Credit http://waterpigs.co.uk/notes/4WZHhH/
    enhanceEach: function (selector, dependencies, callback) {
        var elements = document.querySelectorAll(selector);
        if (elements.length > 0) {
            require(dependencies, function () {
                var args = Array.prototype.slice.call(arguments);
                Array.prototype.forEach.call(elements, function (element) {
                    var innerArgs = args.slice();
                    innerArgs.unshift(element);
                    callback.apply(callback, innerArgs);
                });
            });
        }
    },
};

var Location = {

    init: function() {
        this.setupAllMaps();
    },

    setupAllMaps: function() {
        var self = this;
        Util.enhanceEach('.map', ['leaflet'], function(map) {
            //Util.forEach(document.getElementsByClassName('map'), function(ii, map) {
            var lat = map.dataset.latitude;
            var lon = map.dataset.longitude;
            var loc = map.dataset.location;
            if (lat && lon) {
                self.setupMap(map, lat, lon, loc);
            }
        });
    },

    setupMap: function(element, lat, lon, loc) {
        var tileset = L.tileLayer(
            'http://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri'
            });

        var map = L.map(element, {
            center: [lat, lon],
            zoom: 16,
            layers: [tileset]
        });

        L.marker([lat, lon], {'title': loc}).addTo(map);
    },
};

var Posts = {

    postTypes: [ 'note', 'checkin', 'reply', 'share', 'like', 'photo', 'bookmark'],

    init: function() {
        var self = this;

        Util.forEach(document.getElementsByTagName('article'), function(ii, article) {
            var controls = article.getElementsByClassName('admin-post-controls')[0],
                arrow = article.getElementsByClassName('admin-post-controls-arrow')[0];

            if (arrow && controls) {
                arrow.addEventListener('click', function (event) {
                    event.preventDefault();
                    self.showPostControls(arrow, controls);
                });
            }
        });
    },

    showPostControls: function(arrow, controls) {
        controls.style['display'] = 'inline';
        arrow.style['display'] = 'none';
    },
};

var Editor = {

    init: function() {
        this.setupCheckinMap()

        var self = this;
        Util.forEach(document.querySelectorAll('#edit_form a.top_tag'), function(ii, tagBtn) {
            tagBtn.addEventListener('click', function(event) {
                event.preventDefault();
                var tagField = document.querySelector('#edit_form #tags');
                tagField.value = (tagField.value ? tagField.value + ',' : '') + tagBtn.textContent;
            });

        });

        var attachExpandListener = function(handle, textarea) {
            if (handle && textarea) {
                handle.addEventListener('click', function(event) {
                    self.expandArea(handle, textarea);
                });
            }
        };

        attachExpandListener(
            document.querySelector('#edit_form #syndication_expander'),
            document.querySelector('#edit_form #syndication_textarea'));

        attachExpandListener(
            document.querySelector('#edit_form #audience_expander'),
            document.querySelector('#edit_form #audience_textarea'));

        var uploadBtn = document.querySelector('#edit_form #image_upload_button');
        if (uploadBtn) {
            uploadBtn.addEventListener('change', function() {
                self.handleUploadButton(this);
            });
        }
    },

    handleUploadButton: function(button) {
        var uploadsList = document.getElementById('uploads');
        var self = this;

        while (uploadsList.firstChild) {
            uploadsList.removeChild(uploadsList.firstChild);
        }

        forEach(button.files, function(ii, file) {
            var reader = new FileReader();
            reader.onload = function (e) {
                var img = document.createElement('img');
                img.style.maxWidth = '150px';
                img.style.maxHeight = '150px'
                img.src = e.target.result;

                var link = document.createElement('a');
                link.appendChild(img);
                link.appendChild(document.createTextNode(file.name));

                var li = document.createElement('li');
                uploadsList.appendChild(li);

                link.addEventListener('click', function() {
                    self.addImageLink(file);
                });
            };
            reader.readAsDataURL(file);
        });
    },

    expandArea: function(handle, textarea) {
        var closed = textarea.style.display == 'none';
        textarea.style.display = closed ? 'inherit' : 'none';

        handle.classList.toggle('fa-plus-square-o', !closed);
        handle.classList.toggle('fa-minus-square-o', closed);
    },

    setupCheckinMap: function(element) {
        var checkinMap = document.getElementById('checkin-map');
        var latField = document.getElementById('latitude');
        var lonField = document.getElementById('longitude');

        if (latField && lonField && checkinMap) {
            map.textContent = 'loading...';
            require(['leaflet'], function() {
                navigator.geolocation.getCurrentPosition(function(position) {
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    latField.value = lat;
                    lonField.value = lon;
                    Location.setupMap(checkinMap, lat, lon, 'new location');
                });
            })
        }
    },

    addImageLink: function(file) {
        var filename = file.name.replace(' ', '_');
        var contentField = document.getElementById('content');
        contentField.value =
            contentField.value  + '\n![' + filename + '](' + filename + ')';
    },
};

(function(){
    Location.init();
    Posts.init()
    Editor.init();
}());
