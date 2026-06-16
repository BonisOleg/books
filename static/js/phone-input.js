(function () {
    'use strict';

    var MOBILE_CODES = {
        '39': 1, '50': 1, '63': 1, '66': 1, '67': 1, '68': 1, '73': 1, '75': 1, '77': 1,
        '91': 1, '92': 1, '93': 1, '94': 1, '95': 1, '96': 1, '97': 1, '98': 1, '99': 1
    };

    var ERROR_MSG = 'Введіть коректний український номер у форматі +380 XX XXX XX XX';

    function extractDigits(value) {
        return String(value || '').replace(/\D/g, '');
    }

    function normalizeDigits(digits) {
        if (!digits) {
            return null;
        }

        var national;

        if (digits.length === 12 && digits.indexOf('380') === 0) {
            national = digits.slice(3);
        } else if (digits.length === 10 && digits.charAt(0) === '0') {
            national = digits.slice(1);
        } else if (digits.length === 9) {
            national = digits;
        } else {
            return null;
        }

        if (national.length !== 9 || !MOBILE_CODES[national.slice(0, 2)]) {
            return null;
        }

        return '+380' + national;
    }

    function formatDisplay(digits) {
        if (!digits) {
            return '';
        }

        if (digits.indexOf('380') === 0) {
            digits = digits.slice(3);
        } else if (digits.charAt(0) === '0') {
            digits = digits.slice(1);
        }

        if (digits.length > 9) {
            digits = digits.slice(0, 9);
        }

        var formatted = '+380';
        if (digits.length > 0) {
            formatted += ' ' + digits.slice(0, 2);
        }
        if (digits.length > 2) {
            formatted += ' ' + digits.slice(2, 5);
        }
        if (digits.length > 5) {
            formatted += ' ' + digits.slice(5, 7);
        }
        if (digits.length > 7) {
            formatted += ' ' + digits.slice(7, 9);
        }

        return formatted;
    }

    function getDigitsFromInput(value) {
        var digits = extractDigits(value);

        if (digits.indexOf('380') === 0) {
            return digits.slice(0, 12);
        }
        if (digits.charAt(0) === '0') {
            return digits.slice(0, 10);
        }

        return digits.slice(0, 9);
    }

    function setError(input, message) {
        var group = input.closest('.form-group');
        if (!group) {
            return;
        }

        var existing = group.querySelector('.form-error--phone');
        if (existing) {
            existing.remove();
        }

        if (!message) {
            input.removeAttribute('aria-invalid');
            return;
        }

        var error = document.createElement('div');
        error.className = 'form-error form-error--phone';
        error.textContent = message;
        group.appendChild(error);
        input.setAttribute('aria-invalid', 'true');
    }

    function validateInput(input, showError) {
        var digits = getDigitsFromInput(input.value);

        if (digits.length === 0) {
            setError(input, '');
            return true;
        }

        var normalized = normalizeDigits(digits);

        if (showError && !normalized) {
            setError(input, ERROR_MSG);
            return false;
        }

        setError(input, '');
        return Boolean(normalized);
    }

    function bindPhoneInput(input) {
        if (!input || input.dataset.phoneBound === 'true') {
            return;
        }

        input.dataset.phoneBound = 'true';

        input.addEventListener('input', function () {
            var digits = getDigitsFromInput(input.value);
            var formatted = formatDisplay(digits);
            if (input.value !== formatted) {
                input.value = formatted;
            }
            validateInput(input, false);
        });

        input.addEventListener('blur', function () {
            validateInput(input, true);
        });

        input.addEventListener('invalid', function (event) {
            event.preventDefault();
            validateInput(input, true);
        });
    }

    function bindForm(form) {
        form.addEventListener('submit', function (event) {
            var inputs = form.querySelectorAll('[data-phone-input]');
            var valid = true;

            inputs.forEach(function (input) {
                if (!validateInput(input, true)) {
                    valid = false;
                }
            });

            if (!valid) {
                event.preventDefault();
                var firstInvalid = form.querySelector('[data-phone-input][aria-invalid="true"]');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
        });
    }

    function init(root) {
        var scope = root || document;
        scope.querySelectorAll('[data-phone-input]').forEach(bindPhoneInput);
        scope.querySelectorAll('form').forEach(bindForm);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            init(document);
        });
    } else {
        init(document);
    }

    document.body.addEventListener('htmx:afterSwap', function (event) {
        init(event.detail.target);
    });
})();
