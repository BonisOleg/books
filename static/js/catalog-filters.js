(function () {
    'use strict';

    function closeOthers(current) {
        document.querySelectorAll('.attr-filter[open]').forEach(function (node) {
            if (node !== current) {
                node.removeAttribute('open');
            }
        });
    }

    document.addEventListener('click', function (event) {
        var inside = event.target.closest ? event.target.closest('.attr-filter') : null;
        closeOthers(inside);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeOthers(null);
        }
    });

    document.querySelectorAll('form.attr-filters').forEach(function (form) {
        form.addEventListener('submit', function () {
            var select = document.querySelector('.catalog-toolbar select[name="sort"]');
            if (!select) {
                return;
            }
            var value = select.value || '';
            if (!value || value.charAt(0) === '/' || value.charAt(0) === '?') {
                return;
            }
            var hidden = form.querySelector('input[name="sort"]');
            if (hidden) {
                hidden.value = value;
            }
        });
    });
}());
