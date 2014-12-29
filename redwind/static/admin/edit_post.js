(function(global){
    "use strict";

    function handleUploadButton(button) {
        var uploadsList = first('#uploads');

        while (uploadsList.firstChild) {
            uploadsList.removeChild(uploadsList.firstChild);
        }

        each(button.files, function(file) {
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

                li.appendChild(link);
            };
            reader.readAsDataURL(file);
        });
    }

    function expandArea(handle, textarea) {
        var closed = textarea.style.display == 'none';
        textarea.style.display = closed ? 'inherit' : 'none';

        handle.classList.toggle('fa-plus-square-o', !closed);
        handle.classList.toggle('fa-minus-square-o', closed);
    }

    function showLocationFields(show) {
        var div = first('#location_fields')
        if (div) {
            div.style.display = show ? 'inherit' : 'none';
        }
    }

    function getCoords() {
        var latField = first('#latitude');
        var lonField = first('#longitude');
        if (latField && lonField) {
            navigator.geolocation.getCurrentPosition(function (position) {
                latField.value = position.coords.latitude;
                lonField.value = position.coords.longitude;
            });
        }
    }

    function clearCoords() {
        each(all('#latitude,#longitude,#location_name'), function (element) {
            element.value = '';
        });
    }

    function setupCheckinMap() {
        var checkinMap = first('#checkin-map');
        var latField = first('#latitude');
        var lonField = first('#longitude');

        if (latField && lonField && checkinMap) {
            checkinMap.textContent = 'loading...';
            loadLeaflet(function () {
                navigator.geolocation.getCurrentPosition(function (position) {
                    var lat = position.coords.latitude;
                    var lon = position.coords.longitude;
                    latField.value = lat;
                    lonField.value = lon;
                    var map = setupMap(checkinMap, lat, lon);
                    L.marker([lat, lon]).addTo(map);
                });
            });
        }
    }

    function addImageLink(file) {
        var filename = file.name.replace(' ', '_');
        var contentField = first('#content');
        contentField.value =
            contentField.value  + '\n![' + filename + '](' + filename + ')';
    }

    setupCheckinMap();

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
            showLocationFields(coordsBtn.checked);
            if (coordsBtn.checked) {
                getCoords();
            } else {
                clearCoords();
            }
        });
    }
    var latField = first('#latitude');
    showLocationFields(latField && latField.value !== '');

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

})(this);
