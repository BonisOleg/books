document.addEventListener('DOMContentLoaded', function () {
    var links = document.querySelectorAll('a.viewsitelink');
    links.forEach(function (link) {
        link.target = '_blank';
        link.rel = 'noopener';
    });
});
