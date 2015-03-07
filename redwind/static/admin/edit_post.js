$(function() {
    "use strict";

    function fetchContext(type, urls) {
        $('#context-area').empty();
        $.get('/services/fetch_context', {
            type: type,
            url: urls,
        }, function(result) {
            if (result.contexts) {
                result.contexts.forEach(function(ctx) {
                    $('#context-area').append(ctx.html);
                });
            }
        });
    }

    function handleUploadButton(button) {
        $('#uploads').empty();
        each(button.files, function(file) {
            var reader = new FileReader();
            reader.onload = function (e) {
                var li = $('#uploads').append('<li><a href="#"><img src="' + e.target.result + '" style="max-width:150px; max-height:150px"/>' + file.name + '</a></li>');

                $('a', li).click(function() {
                    $('#content').val(function(index, value) {
                        var filename = file.name.replace(' ', '_');
                        return value  + '\n![' + filename + '](' + filename + ')';
                    });
                });
            };
            reader.readAsDataURL(file);
        });
    }

    $('#edit_form #image_upload_button').change(function() {
        handleUploadButton(this);
    });


    function attachFetchContext(type, input) {
        function go() {
            var urls = input.val();
            if (urls) {
                fetchContext(type, urls.split('\n'));
            }
        }

        input.change(go);
        go();
    }

    attachFetchContext('Reply To', $('textarea[name=in_reply_to]'));
    attachFetchContext('Like Of', $('textarea[name=like_of]'));
    attachFetchContext('Repost Of', $('textarea[name=repost_of]'));
    attachFetchContext('Bookmark Of', $('input[name=bookmark_of]'));

});
