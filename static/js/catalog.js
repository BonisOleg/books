document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('select.js-sort-redirect').forEach(function (sel) {
        sel.addEventListener('change', function () {
            if (sel.value) {
                window.location.href = sel.value;
            }
        });
    });
});
