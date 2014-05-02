(function(){
    $(document).ready(function() {
        console.log('ready');

        $('.admin-post-controls-arrow').mouseenter(function (event) {
            var arrow = $(event.currentTarget);
            var post = arrow.closest('.post');
            var controls = post.find('.admin-post-controls');

            if (controls.css('display') == 'none') {
                controls.css({
                    'display': 'block',
                    'left': arrow.position().left - controls.width(),
                    'top': arrow.position().top,
                });
            }

            return false;
        });
    });

    $('.admin-post-controls').mouseleave(function (event) {
        $(event.currentTarget).css('display', 'none');
    });

})();
