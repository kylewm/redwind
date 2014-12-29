(function(global) {

    // DOM convenience functions, from Barnaby Walters (waterpigs.co.uk)
    function first(selector, context) {return (context || document).querySelector(selector);}
    function all(selector, context) {return (context || document).querySelectorAll(selector);}
    function each(els, callback) {return Array.prototype.forEach.call(els, callback);}
    function map(els, callback) {return Array.prototype.map.call(els, callback);}

    function loadJsFile(url, cb) {
        var scriptTag = document.createElement('script');
        scriptTag.type = 'text/javascript';
        scriptTag.src = url;
        scriptTag.onload = cb;
        first('head').appendChild(scriptTag);
    }

    function loadCssFile(url, cb) {
        var linkTag = document.createElement('link');
        linkTag.rel = 'stylesheet';
        linkTag.type = 'text/css'
        linkTag.href = url;
        linkTag.onload = cb;
        first('head').appendChild(linkTag);
    }

    function loadLeaflet(cb) {
        var leafletJs = '//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.js';
        var leafletCss = '//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.css';
        var complete = {};
        loadJsFile(leafletJs, function() {complete.js = true; if (complete.css) { cb(); }});
        loadCssFile(leafletCss, function() {complete.css = true; if (complete.js) { cb(); }});
    }

    global.first = first;
    global.all = all;
    global.each = each;
    global.map = map;
    global.loadLeaflet = loadLeaflet;

})(this);
