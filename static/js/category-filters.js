document.addEventListener('DOMContentLoaded', function () {
    var openBtn = document.getElementById('open-filters');
    var closeBtn = document.getElementById('close-filters');
    var panel = document.getElementById('mobile-filters');
    var overlay = document.getElementById('filter-overlay');

    if (!panel || !overlay) {
        return;
    }

    function open() {
        panel.classList.add('is-open');
        overlay.classList.add('is-visible');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        panel.classList.remove('is-open');
        overlay.classList.remove('is-visible');
        document.body.style.overflow = '';
    }

    if (openBtn) openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', close);
});
