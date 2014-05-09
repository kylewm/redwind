(function() {

    function clearResults() {
        $('#result').empty();
    }

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }

    function uploadCompleteHandler(data) {
        appendResult("finished uploading to " + data.original);
        appendResult("<ul><li>small " + data.small
                     + "</li><li>medium " + data.medium
                     + "</li><li>large " + data.large + "</li></ul>");

        var content_text_area = $("#content");
        var content_format = $("#content_format").val();

        content_text_area.val( content_text_area.val() + '[![](' + data.medium + ')](' + data.original + ')');
    }

    function uploadErrorHandler(data, status, errorThrown) {
        appendResult("upload failed with " + status + ", " + errorThrown);
    }

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }

    /* register events */
    $(document).ready(function() {
        $('#uploads_link').click(function(event) {
            event.preventDefault();
            var left = (screen.width-100) / 2;
            var top = (screen.height-100) / 2;

            window.open('/admin/uploads', 'width=100,height=100,top='+top+',left='+left);
        });

        $("#get_coords_button").click(function() {
            navigator.geolocation.getCurrentPosition(function(position) {
                console.log(position);
                $("#latitude").val(position.coords.latitude.toFixed(3));
                $("#longitude").val(position.coords.longitude.toFixed(3));
            });
        });

        $("#image_upload_button").change(function() {
            var file = this.files[0];
            $('#result').append("<li>uploading file " + file.name + "</li>");

            if (undefined != file) {
                var formData = new FormData();
                formData.append('file', file);

                $.ajax({
                    url: '/api/upload_image',
                    type: 'POST',
                    success: uploadCompleteHandler,
                    error: uploadErrorHandler,
                    data: formData,
                    cache: false,
                    contentType: false,
                    processData: false
                });
            }
        });
    });

})();
