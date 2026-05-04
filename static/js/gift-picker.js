document.addEventListener('DOMContentLoaded', function () {
    var wizard = document.getElementById('gift-wizard');
    if (!wizard) return;

    var form = wizard.querySelector('form');
    if (!form) return;

    var groups = Array.from(form.querySelectorAll('.gift-question'));
    var backBtn = form.querySelector('.gift-wizard__back');
    var submitBtn = form.querySelector('.gift-wizard__submit');
    var currentStep = 0;

    if (groups.length === 0) return;

    function showStep(step) {
        groups.forEach(function (g, i) {
            g.style.display = i === step ? 'block' : 'none';
        });

        if (backBtn) {
            backBtn.style.display = step > 0 ? 'inline-flex' : 'none';
        }
        if (submitBtn) {
            submitBtn.style.display = step === groups.length - 1 ? 'flex' : 'none';
        }
    }

    function markSelected(group, radio) {
        group.querySelectorAll('.gift-option').forEach(function (label) {
            label.classList.remove('gift-option--selected');
        });
        if (radio) {
            radio.closest('.gift-option').classList.add('gift-option--selected');
        }
    }

    // Single question — show submit immediately, no wizard behaviour
    if (groups.length === 1) {
        if (submitBtn) submitBtn.style.display = 'flex';

        groups[0].querySelectorAll('input[type="radio"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                markSelected(groups[0], radio);
            });
        });
        return;
    }

    // Multi-step wizard
    showStep(0);

    groups.forEach(function (group, idx) {
        group.querySelectorAll('input[type="radio"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                markSelected(group, radio);
                if (idx < groups.length - 1) {
                    setTimeout(function () {
                        currentStep = idx + 1;
                        showStep(currentStep);
                    }, 280);
                }
            });
        });
    });

    if (backBtn) {
        backBtn.addEventListener('click', function () {
            if (currentStep > 0) {
                currentStep -= 1;
                showStep(currentStep);
            }
        });
    }
});
