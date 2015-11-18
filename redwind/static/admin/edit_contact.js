(function(global) {
    "use strict";

    function fetchProfile() {
        var url = first('input[name="url"]');
        var xhr = Http.get(SITE_ROOT+'/services/fetch_profile?url=' + encodeURIComponent(url.value));
        Http.send(xhr).then(function(xhr) {
            var data = JSON.parse(xhr.responseText);
            if (data.name) {
                first('[name="name"]').value = data.name;
            }
            if (data.image) {
                first('[name="image"]').value = data.image;
            }
            if (data.social) {
                first('[name="social"]').value = data.social.join('\n');
            }
        });
    }

    each(all('#fetch_profile'), function(fetchButton) {
        fetchButton.addEventListener('click', fetchProfile);
    });

})(this);
