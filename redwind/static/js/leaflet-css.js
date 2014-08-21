// loads leaflet's css only when needed
define(function () {
    var link = document.createElement("link");
    link.type = "text/css";
    link.rel = "stylesheet";
    link.href = "//cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.css";
    document.getElementsByTagName("head")[0].appendChild(link);
});
