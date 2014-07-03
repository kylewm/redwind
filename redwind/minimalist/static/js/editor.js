(function() {

    function add_img_link(file) {
        var filename = file.name.replace(' ', '_');
        $('#content').val(
            $('#content').val() + '\n![' + filename + '](' + filename + ')');
    }

    /* register events */
    $(document).ready(function() {
        $('#syndication_textarea').css('display','none');
        $('#audience_textarea').css('display', 'none');

        $('#syndication_expander').click(function(){
            var textarea = $('#syndication_textarea');
            var closed = textarea.css('display') == 'none';
            if (closed) {
                textarea.css('display', '');
            }else {
                textarea.css('display', 'none');
            }
            $(this).toggleClass('fa-plus-square-o', !closed);
            $(this).toggleClass('fa-minus-square-o', closed);
        });

        $('#audience_expander').click(function(){
            var textarea = $('#audience_textarea');
            var closed = textarea.css('display') == 'none';
            if (closed) {
                textarea.css('display', '');
            }else {
                textarea.css('display', 'none');
            }
            $(this).toggleClass('fa-plus-square-o', !closed);
            $(this).toggleClass('fa-minus-square-o', closed);
        });


        $('#get_coords_button').change(function() {
            console.log('changed');
            console.log(this);
            console.log(this.checked);
            if (this.checked) {
                navigator.geolocation.getCurrentPosition(function(position) {
                    console.log(position);
                    $('#latitude').val(position.coords.latitude.toFixed(3));
                    $('#longitude').val(position.coords.longitude.toFixed(3));
                });
            }
            else {
                $('#latitude').val('');
                $('#longitude').val('');
            }
        });

        $('#image_upload_button').change(function() {
            $('#uploads').empty();
            for (var ii = 0 ; ii < this.files.length ; ii++) {
                (function(file) {
                    var reader = new FileReader();
                    reader.onload = function (e) {
                        var link = $('<a>');
                        link.append('<img style="max-width: 75px; max-height: 75px;" src="' + e.target.result + '"/>' + file.name);
                        $('#uploads').append($('<ul>').append(link));
                        link.click(function(){
                            add_img_link(file);
                        });
                    };
                    reader.readAsDataURL(file);
                })(this.files[ii]);
            }
        });
    });

})();
