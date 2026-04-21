document.addEventListener('DOMContentLoaded', function () {
    var rangeInputs = document.querySelectorAll('.filter-group__input[type="number"]');
    rangeInputs.forEach(function (input) {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var form = input.closest('form');
                if (form) {
                    htmx.trigger(form, 'change');
                }
            }
        });
    });
});
