$(document).ready(function() {

    var postTypes = ['article', 'note', 'checkin', 'reply', 'share', 'like'];

    $(postTypes).each(function (i, type) {

        $('#new-' + type).click(function (event) {
            event.preventDefault();

            $.get('/admin/new?type=' + type, '',
                  function(result) {
                      $('#composition-area').empty().append(result);
                  });

        });
    });


    $('.admin-post-controls-arrow').click(function (event) {
        var arrow = $(event.currentTarget);
        var post = arrow.closest('.post');
        var controls = post.find('.admin-post-controls');

        if (controls.css('display') == 'none') {
            controls.css({
                'display': 'block',
                'left': arrow.position().left - controls.width(),
                'top': arrow.position().top + arrow.height(),
            });
        }
        else {
            controls.css('display', 'none');
        }

        return false;
    });
});
