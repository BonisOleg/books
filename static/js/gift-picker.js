document.addEventListener('DOMContentLoaded', function () {
    var wizard = document.getElementById('gift-wizard');
    if (!wizard) return;

    var form = wizard.querySelector('form');
    if (!form) return;

    var groups = form.querySelectorAll('.form-group');
    var currentStep = 0;

    function showStep(step) {
        groups.forEach(function (g, i) {
            g.style.display = i === step ? 'block' : 'none';
        });

        var submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.style.display = step === groups.length - 1 ? 'block' : 'none';
        }
    }

    if (groups.length > 1) {
        showStep(0);

        groups.forEach(function (group, idx) {
            var radios = group.querySelectorAll('input[type="radio"]');
            radios.forEach(function (radio) {
                radio.addEventListener('change', function () {
                    if (idx < groups.length - 1) {
                        setTimeout(function () {
                            currentStep = idx + 1;
                            showStep(currentStep);
                        }, 300);
                    }
                });
            });
        });
    }
});
