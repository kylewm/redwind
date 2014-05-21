(function() {

    function clearUploads() {
        $('#uploads').empty();
    }

    function appendUpload(str) {
        $('#uploads').append("<li>" + str + "</li>");
    }

    /* register events */
    $(document).ready(function() {

        $("#get_coords_button").click(function() {
            navigator.geolocation.getCurrentPosition(function(position) {
                console.log(position);
                $("#latitude").val(position.coords.latitude.toFixed(3));
                $("#longitude").val(position.coords.longitude.toFixed(3));
            });
        });

        $("#image_upload_button").change(function() {
            $('#uploads').empty();
            for (var ii = 0 ; ii < this.files.length ; ii++) {
                var file = this.files[ii];
                var reader = new FileReader();
                reader.onload = function (e) {
                    $('#uploads').append('<ul><img style="max-width: 75px; max-height: 75px;" src="' + e.target.result + '"/> ' + file.name + '</ul>')
                };
                reader.readAsDataURL(file);
            }
        });
    });

})();
