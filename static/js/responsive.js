

$(document).ready(function() {
    
    function doneResizing() {
        var leftCol = $(".span_2_of_3");
        var rightCol = $(".span_1_of_3");
        var nav = $("nav");

        var width = parseFloat(rightCol.css('width')) / parseFloat(rightCol.parent().css('width'));

        if (width > 0.99) {
            //if (nav.parent() != leftCol) {
                leftCol.prepend(nav);
            //}
        } else {
            //if (nav.parent() != rightCol) {
                rightCol.prepend(nav);
            //}
        }
        
    }

    var id;
    $(window).resize(function () {
        clearTimeout(id);
        id = setTimeout(doneResizing, 0);
    });
    doneResizing();

});
