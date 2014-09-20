"use strict";

(function(){

    var leafletJs = '//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.js';
    var leafletCss = '//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.css';

    // DOM convenience functions, from Barnaby Walters (waterpigs.co.uk)
    var first = function(selector, context) { return (context || document).querySelector(selector); };
    var all = function(selector, context) { return (context || document).querySelectorAll(selector); };
    var each = function(els, callback) { return Array.prototype.forEach.call(els, callback); };
    var map = function(els, callback) { return Array.prototype.map.call(els, callback); };

    var loadJsFile = function(url, cb) {
        var scriptTag = document.createElement('script');
        scriptTag.type = 'text/javascript';
        scriptTag.src = url;
        scriptTag.onload = cb;
        first('head').appendChild(scriptTag);
    };

    var loadCssFile = function(url, cb) {
        var linkTag = document.createElement('link');
        linkTag.rel = 'stylesheet';
        linkTag.type = 'text/css'
        linkTag.href = url;
        linkTag.onload = cb;
        first('head').appendChild(linkTag);
    };

    var loadLeaflet = function(cb) {
        var complete = {};
        loadJsFile(leafletJs, function() {complete.js = true; if (complete.css) { cb(); }});
        loadCssFile(leafletCss, function() {complete.css = true; if (complete.js) { cb(); }});
    };

    // credit http://waterpigs.co.uk/articles/a-minimal-javascript-http-abstraction/
    var Http = (function() {
        var open = function open(method, url) {
            var xhr = new XMLHttpRequest();
            xhr.open(method.toUpperCase(), url);
            return xhr;
        };

        var send = function send(xhr, value) {
            var value = value || null;
            return new Promise(function (resolve, reject) {
                xhr.onload = function () {
                    // Success if status in 2XX.
                    if (xhr.status - 200 <= 99 && xhr.status - 200 > -1) {
                        resolve(xhr);
                    } else {
                        reject(xhr);
                    }
                };

                xhr.onerror = function () {
                    reject(xhr);
                };

                xhr.send(value);
            });
        };
        return {
            open: open,
            send: send
        };
    })();

    var Location = (function() {

        var setupAllMaps = function() {
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
        };

        var setupMap = function(element, lat, lon, loc) {
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
        };

        setupAllMaps();
        return {setupMap: setupMap};
    }());

    var Posts = (function(){
        var showPostControls = function(arrow, controls) {
            controls.style['display'] = 'inline';
            arrow.style['display'] = 'none';
        };

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
        each(all('.h-feed article'), function(article) {
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
        });

        return {};
    }());

    var Editor = (function(){

        var handleUploadButton = function(button) {
            var uploadsList = first('#uploads');

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
                        addImageLink(file);
                    });
                };
                reader.readAsDataURL(file);
            });
        };

        var expandArea = function(handle, textarea) {
            var closed = textarea.style.display == 'none';
            textarea.style.display = closed ? 'inherit' : 'none';

            handle.classList.toggle('fa-plus-square-o', !closed);
            handle.classList.toggle('fa-minus-square-o', closed);
        };

        var getCoords = function(element) {
            var latField = first('#latitude');
            var lonField = first('#longitude');
            navigator.geolocation.getCurrentPosition(function(position) {
                latField.value = position.coords.latitude;
                lonField.value = position.coords.longitude;
            });
        };

        var setupCheckinMap = function(element) {
            var checkinMap = first('#checkin-map');
            var latField = first('#latitude');
            var lonField = first('#longitude');

            if (latField && lonField && checkinMap) {
                checkinMap.textContent = 'loading...';
                loadLeaflet(function() {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        var lat = position.coords.latitude;
                        var lon = position.coords.longitude;
                        latField.value = lat;
                        lonField.value = lon;
                        Location.setupMap(checkinMap, lat, lon, 'new location');
                    });
                });
            }
        };

        var addImageLink = function(file) {
            var filename = file.name.replace(' ', '_');
            var contentField = first('#content');
            contentField.value =
                contentField.value  + '\n![' + filename + '](' + filename + ')';
        };

        setupCheckinMap()

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
                    getCoords();
                }
            });
        }

        var attachExpandListener = function(handle, textarea) {
            if (handle && textarea) {
                handle.addEventListener('click', function(event) {
                    expandArea(handle, textarea);
                });
                expandArea(handle, textarea);
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
                handleUploadButton(this);
            });
        }


        return {};
    }());

    var AddressBook = (function(){
        var fetchProfile = function() {
            var url = first('#url');
            var xhr = Http.open('GET', '/api/fetch_profile?url=' + encodeURIComponent(url.value));
            Http.send(xhr).then(function(xhr) {
                var data = JSON.parse(xhr.responseText);
                ['name', 'photo', 'twitter', 'facebook'].forEach(function(field) {
                    if (field in data) {
                        document.getElementById(field).value = data[field];
                    }
                });
            });
        };

        each(all('#addressbook_form #fetch'), function(fetchButton) {
            fetchButton.addEventListener('click', fetchProfile);
        });

        return {};
    }());

    var Twitter = (function() {
        var shortUrlLength = 22;
        var shortUrlLengthHttps = 23;
        var mediaUrlLength = 23;

        /* splits a text string into text and urls */
        var classifyText = function classifyText(text) {
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
        };

        var estimateLength = function(classified) {
            return classified.map(function(item){
                if (item.type == 'url') {
                    var urlLength = item.value.startsWith('https') ?
                        shortUrlLengthHttps : shortUrlLength;
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
        };

        var shorten = function shorten(classified, target) {
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
        };

        var classifiedToString = function classifiedToString(classified) {
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
        };

        var generateTweetPreview = function generateTweetPreview() {

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

            var classified = classifyText(fullText);

            if (useShortPermalink) {
                addShortPermalink(classified);
            } else {
                addPermalink(classified);
            }

            if (estimateLength(classified) > target) {
                if (useShortPermalink) {
                    // replace the shortlink with a full one
                    classified.pop();
                    addPermalink(classified);
                }
                shorten(classified, target);
            }

            var shortened = classifiedToString(classified);
            first('#preview').value = shortened;
            fillCharCount();
        };

        var fillCharCount = function fillCharCount() {
            var preview = first('#preview');
            if (preview) {
                var classified = classifyText(preview.value);
                var length = estimateLength(classified);
                first('#char_count').textContent = length;
            }
        };

        var previewField = first('#preview');
        if (previewField) {
            previewField.addEventListener('input', fillCharCount);
        }
        each(all('#permalink, #permashortlink, #permashortcite'), function(el) {
            el.addEventListener('click', function() { select(); });
        });
        fillCharCount();

        return {}
    }());

    // Lazy-create and return an indie-config load promise
    // The promise will be resolved with a config once the indie-config has been loaded
    /*var loadIndieConfig = function () {

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
    });*/

}());
