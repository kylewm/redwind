(function(global) {
    "use strict";

    function fetchProfile() {
        var url = first('input[name="url"]');
        var xhr = Http.get(SITE_ROOT+'/services/fetch_profile?url=' + encodeURIComponent(url.value));
        Http.send(xhr).then(function(xhr) {
            var data = JSON.parse(xhr.responseText);
            if (data.name) {
                first('input[name="name"]').value = data.name;
            }
            if (data.image) {
                first('input[name="image"]').value = data.image;
            }
            if (data.twitter) {
                first('input[name="twitter"]').value = data.twitter;
                if (!first('input[name="nicks"]').value) {
                    first('input[name="nicks"]').value = data.twitter;
                }
            }
            if (data.facebook) {
                first('input[name="facebook"]').value = data.facebook;
            }
        });
    }

    each(all('#fetch_profile'), function(fetchButton) {
        fetchButton.addEventListener('click', fetchProfile);
    });

})(this);
