(function () {
    'use strict';

    if (typeof htmx !== 'undefined' && htmx.config) {
        htmx.config.refreshOnHistoryMiss = true;
    }

    var _submitClicked = false;

    document.addEventListener('click', function (e) {
        if (e.target.closest && e.target.closest('.filter-panel__submit')) {
            _submitClicked = true;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (!_submitClicked) {
            return;
        }
        _submitClicked = false;
        if (!e.detail || !e.detail.target || e.detail.target.id !== 'product-grid') {
            return;
        }
        var panel = document.getElementById('mobile-filters');
        if (panel && panel.classList.contains('is-open')) {
            panel.classList.remove('is-open');
            var overlay = document.getElementById('filter-overlay');
            if (overlay) {
                overlay.classList.remove('is-visible');
            }
            document.body.style.overflow = '';
        }
        var grid = document.getElementById('product-grid');
        if (grid) {
            setTimeout(function () {
                grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 50);
        }
    });
}());
