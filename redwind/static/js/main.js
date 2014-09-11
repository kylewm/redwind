requirejs.config({
    baseUrl: '/static/js',
    paths: {
        "leaflet": "//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet",
    }
});

define(function(require) {

    // DOM convenience functions, also from Barnaby Walters
    var first = function (selector, context) { return (context || document).querySelector(selector); };
    var all = function (selector, context) { return (context || document).querySelectorAll(selector); };
    var each = function (els, callback) { return Array.prototype.forEach.call(els, callback); };
    var map = function (els, callback) { return Array.prototype.map.call(els, callback); };

    // Credit http://waterpigs.co.uk/notes/4WZHhH/
    var enhanceEach = function (selector, dependencies, callback) {
        var elements = all(selector);
        if (elements.length > 0) {
            require(dependencies, function () {
                var args = Array.prototype.slice.call(arguments);
                each(elements, function (element) {
                    var innerArgs = args.slice();
                    innerArgs.unshift(element);
                    callback.apply(callback, innerArgs);
                });
            });
        }
    };

    var Location = {

        init: function() {
            this.setupAllMaps();
        },

        setupAllMaps: function() {
            var self = this;
            enhanceEach('.map', ['leaflet', 'leaflet-css'], function(map) {
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

            each(all('article'), function(article) {
                var controls = first('.admin-post-controls', article),
                arrow = first('.admin-post-controls-arrow', article);

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
            each(all('#edit_form a.top_tag'), function(tagBtn) {
                tagBtn.addEventListener('click', function(event) {
                    event.preventDefault();
                    var tagField = first('#edit_form #tags');
                    tagField.value = (tagField.value ? tagField.value + ',' : '') + tagBtn.textContent;
                });

            });

            var coordsBtn = first('#get_coords_button')
            if (coordsBtn) {
                coordsBtn.addEventListener('change', function(event) {
                    if (coordsBtn.checked) {
                        self.getCoords();
                    }
                });
            }

            var attachExpandListener = function(handle, textarea) {
                if (handle && textarea) {
                    handle.addEventListener('click', function(event) {
                        self.expandArea(handle, textarea);
                    });
                    self.expandArea(handle, textarea);
                }
            };

            attachExpandListener(
                first('#edit_form #syndication_expander'),
                first('#edit_form #syndication_textarea'));

            attachExpandListener(
                first('#edit_form #audience_expander'),
                first('#edit_form #audience_textarea'));

            var uploadBtn = first('#edit_form #image_upload_button');
            if (uploadBtn) {
                uploadBtn.addEventListener('change', function() {
                    self.handleUploadButton(this);
                });
            }
        },

        handleUploadButton: function(button) {
            var uploadsList = first('#uploads');
            var self = this;

            while (uploadsList.firstChild) {
                uploadsList.removeChild(uploadsList.firstChild);
            }

            each(button.files, function(ii, file) {
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

        getCoords: function(element) {
            var latField = first('#latitude');
            var lonField = first('#longitude');
            navigator.geolocation.getCurrentPosition(function(position) {
                latField.value = position.coords.latitude;
                lonField.value = position.coords.longitude;
            });
        },

        setupCheckinMap: function(element) {
            var checkinMap = first('#checkin-map');
            var latField = first('#latitude');
            var lonField = first('#longitude');

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
            var contentField = first('#content');
            contentField.value =
                contentField.value  + '\n![' + filename + '](' + filename + ')';
        },
    };

    var AddressBook = {

        init: function() {
            var self = this;
            each(all('#addressbook_form #fetch'), function(fetchButton) {
                fetchButton.addEventListener('click', self.fetchProfile);
            });
        },

        fetchProfile: function() {
            var url = first('#url');
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
            var previewField = first('#preview');
            if (previewField) {
                previewField.addEventListener('input', this.fillCharCount.bind(this));
            }
            each(all('#permalink, #permashortlink, #permashortcite'), function(el) {
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
            var titleField = first('#title'), contentArea = first('#content');

            var fullText, useShortPermalink;
            if (titleField.length > 0) {
                fullText = titleField.value;
                useShortPermalink = false;
            } else {
                fullText = contentArea.value;
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
            first('#preview').value = shortened;
            this.fillCharCount();
        },

        fillCharCount: function fillCharCount() {
            var preview = first('#preview');
            if (preview) {
                var classified = this.classifyText(preview.value);
                var length = this.estimateLength(classified);
                first('#char_count').textContent = length;
            }
        }
    };

    // Lazy-create and return an indie-config load promise
    // The promise will be resolved with a config once the indie-config has been loaded
    var loadIndieConfig = function () {

        // Create the Promise to return
        var loadPromise = new Promise(function (resolve) {

            // Parse the incoming messages
            var parseIndieConfig = function (message) {

                // Check if the message comes from the indieConfigFrame we added (or from some other frame)
                if (message.source !== indieConfigFrame.contentWindow) {
                    return;
                }

                var indieConfig;

                // Try to parse the config, it can be malformed
                try {
                    indieConfig = JSON.parse(message.data);
                } catch (e) {}

                // We're done – remove the frame and event listener
                window.removeEventListener('message', parseIndieConfig);
                indieConfigFrame.parentNode.removeChild(indieConfigFrame);
                indieConfigFrame = undefined;

                // And resolve the promise with the loaded indie-config
                resolve(indieConfig);
            };

            // Listen for messages from the added iframe and parse those messages
            window.addEventListener('message', parseIndieConfig);

            // Create a hidden iframe pointing to something using the web+action: protocol
            var indieConfigFrame = document.createElement('iframe');
            indieConfigFrame.src = 'web+action:load';
            document.getElementsByTagName('body')[0].appendChild(indieConfigFrame);
            indieConfigFrame.style.display = 'none';
        });

        // Ensure that subsequent invocations return the same promise
        loadIndieConfig = function () {
            return loadPromise;
        };

        return loadPromise;
    };

    loadIndieConfig().then(function(indieConfig) {
        each(all('indie-action,action'), function (action) {
            var d = action.getAttribute('do');
            var w = action.getAttribute('with');
            if (d && w && indieConfig[d]) {

                var newLink = first('a', action);
                if (!newLink) {
                    newLink = document.createElement('a');
                    action.appendChild(newLink);
                }
                newLink.textContent = 'indie-' + d;
                newLink.href = (indieConfig[d]).replace('{url}', w);
            }
        });
    });


    Location.init();
    Posts.init()
    Editor.init();
    AddressBook.init()
    Twitter.init();

});
