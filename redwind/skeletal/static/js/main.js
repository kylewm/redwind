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
            checkinMap.textContent = 'loading...';
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

var AddressBook = {

    init: function() {
        var self = this;
        Util.forEach(document.querySelectorAll('#addressbook_form #fetch'), function(ii, fetchButton) {
            fetchButton.addEventListener('click', self.fetchProfile);
        });
    },

    fetchProfile: function() {
        var url = document.getElementById('url');
        require(['http'], function(http) {
            var xhr = http.open('GET', '/api/fetch_profile?url=' + encodeURIComponent(url.value));
            http.send(xhr).then(function(xhr) {
                var data = JSON.parse(xhr.responseText);
                ['name', 'photo', 'twitter', 'facebook'].forEach(function(field) {
                    if (field in data) {
                        document.getElementById(field).value = data[field];
                    }
                });
            });
        });
    },

};

var Twitter = {
    shortUrlLength: 22,
    shortUrlLengthHttps: 23,
    mediaUrlLength: 23,

    init: function() {
        var previewField = document.getElementById('preview');
        if (previewField) {
            previewField.addEventListener('input', this.fillCharCount.bind(this));
        }
        Util.forEach(document.querySelectorAll('#permalink, #permashortlink, #permashortcite'), function(ii, el) {
            el.addEventListener('click', function() { this.select(); });
        });
        this.fillCharCount();
    },

    /* splits a text string into text and urls */
    classifyText: function classifyText(text) {
        var result = [];

        var match;
        var lastIndex = 0;
        var urlRegex = /https?:\/\/[_a-zA-Z0-9.\/\-!#$%?:]+/g;
        while ((match = urlRegex.exec(text)) != null) {
            var subtext = text.substring(lastIndex, match.index);
            if (subtext.length > 0) {
                result.push({type: 'text', value: subtext});
            }
            result.push({type: 'url', value: match[0]});
            lastIndex = urlRegex.lastIndex;
        }

        var subtext = text.substring(lastIndex);
        if (subtext.length > 0) {
            result.push({type: 'text', value: subtext});
        }

        return result;
    },

    estimateLength: function estimateLength(classified) {
        var self = this;
        return classified.map(function(item){
            if (item.type == 'url') {
                var urlLength = item.value.startsWith('https') ?
                    self.shortUrlLengthHttps : self.shortUrlLength;
                if (item.hasOwnProperty('prefix')) {
                    urlLength += item.prefix.length;
                }
                if (item.hasOwnProperty('suffix')) {
                    urlLength += item.suffix.length;
                }
                return urlLength;
            }
            return item.value.length;
        }).reduce(function(a, b){ return a + b; }, 0);
    },

    shorten: function shorten(classified, target) {
        for (;;) {
            var length = estimateLength(classified);
            if (length <= target) {
                return classified;
            }

            var diff = length - target;
            var shortened = false;

            for (var ii = classified.length-1; !shortened && ii >= 0 ; ii--) {
                var item = classified[ii];
                if (item['required']) {

                }
                else if (item.type == 'url') {
                    classified.splice(ii, 1);
                    shortened = true;
                }
                else if (item.type == 'text') {
                    if (item.value.length > diff + 3) {
                        var truncated = item.value.substring(0, item.value.length-diff-4);
                        // remove .'s and spaces from the end of the truncated string
                        while ([' ', '.'].indexOf(truncated[truncated.length-1]) >= 0) {
                            truncated = truncated.substring(0, truncated.length-1);
                        }
                        classified[ii] = {type: 'text', value:  truncated + '...'};
                        shortened = true;
                    }
                    else {
                        classified.splice(ii, 1);
                        shortened = true;
                    }
                }
            }
        }
    },

    classifiedToString: function classifiedToString(classified) {
        return classified.map(function(item) {
            var result = '';
            if (item != null) {

                if (item.hasOwnProperty('prefix')) {
                    result += item.prefix;
                }
                result += item.value;
                if (item.hasOwnProperty('suffix')) {
                    result += item.suffix;
                }

            }
            return result;
        }).join('');
    },

    generateTweetPreview: function generateTweetPreview() {

        var addShortPermalink = function(classified) {
            classified.push({
                type: 'url',
                required: true,
                value: 'http://kyl.im/XXXXX',
                prefix: '\n(',
                suffix: ')'});
        };

        var addPermalink = function(classified) {
            classified.push({
                type: 'url',
                required: true,
                prefix: ' ',
                value: 'http://kylewm.com/XXXX/XX/XX/X'
            });
        };

        var target = 140;
        var titleField = $('#title'), contentArea = $('#content');

        var fullText, useShortPermalink;
        if (titleField.length > 0) {
            fullText = titleField.val();
            useShortPermalink = false;
        } else {
            fullText = contentArea.val();
            useShortPermalink = true;
        }

        var classified = this.classifyText(fullText);

        if (useShortPermalink) {
            this.addShortPermalink(classified);
        } else {
            this.addPermalink(classified);
        }

        if (this.estimateLength(classified) > target) {
            if (useShortPermalink) {
                // replace the shortlink with a full one
                classified.pop();
                this.addPermalink(classified);
            }
            this.shorten(classified, target);
        }

        var shortened = this.classifiedToString(classified);
        $('#preview').val(shortened);
        this.fillCharCount();
    },

    fillCharCount: function fillCharCount() {
        var classified = this.classifyText(document.getElementById('preview').value);
        var length = this.estimateLength(classified);
        document.getElementById('char_count').textContent = length;
    }



};


(function(){
    Location.init();
    Posts.init()
    Editor.init();
    AddressBook.init()
    Twitter.init();
}());
