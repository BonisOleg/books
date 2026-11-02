(function () {
    'use strict';

    var modal = document.getElementById('consult-modal');
    if (!modal) {
        return;
    }

    var locked = false;
    var scrollY = 0;
    var submitting = false;
    var pushedHash = false;

    function lockScroll() {
        if (locked) {
            return;
        }
        scrollY = window.scrollY || document.documentElement.scrollTop || 0;
        document.documentElement.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.top = '-' + scrollY + 'px';
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        locked = true;
    }

    function unlockScroll() {
        if (!locked) {
            return;
        }
        document.documentElement.style.overflow = '';
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        locked = false;
        window.scrollTo(0, scrollY);
    }

    function focusField() {
        var field = modal.querySelector(
            'input:not([type="hidden"]):not(.u-hp__input), textarea'
        );
        if (!field) {
            return;
        }
        window.setTimeout(function () {
            try {
                field.focus({ preventScroll: true });
            } catch (error) {
                field.focus();
            }
        }, 0);
    }

    function openModal() {
        if (modal.classList.contains('is-open')) {
            return;
        }
        modal.classList.add('is-open');
        lockScroll();
        focusField();
    }

    function rememberHash() {
        if (window.location.hash === '#consult-modal') {
            return;
        }
        window.history.pushState({ consult: 1 }, '', '#consult-modal');
        pushedHash = true;
    }

    function hideModal(updateHash) {
        modal.classList.remove('is-open');
        unlockScroll();
        if (updateHash === false) {
            pushedHash = false;
            return;
        }
        if (window.location.hash !== '#consult-modal') {
            pushedHash = false;
            return;
        }
        if (pushedHash) {
            pushedHash = false;
            window.history.back();
            return;
        }
        window.history.replaceState(
            null,
            '',
            window.location.pathname + window.location.search
        );
    }

    function clearErrors(form) {
        var status = form.querySelector('[data-consult-status]');
        if (status) {
            status.hidden = true;
            status.textContent = '';
        }
        form.querySelectorAll('[data-error-for]').forEach(function (node) {
            node.hidden = true;
            node.textContent = '';
        });
        form.querySelectorAll('[aria-invalid="true"]').forEach(function (field) {
            field.removeAttribute('aria-invalid');
        });
    }

    function showStatus(form, message) {
        var status = form.querySelector('[data-consult-status]');
        if (!status || !message) {
            return;
        }
        status.hidden = false;
        status.textContent = message;
    }

    function showErrors(form, data) {
        var errors = data.errors || {};
        var hasField = false;
        Object.keys(errors).forEach(function (key) {
            if (key === '__all__') {
                return;
            }
            var node = form.querySelector('[data-error-for="' + key + '"]');
            var text = (errors[key] || []).join(' ');
            if (!node || !text) {
                return;
            }
            node.hidden = false;
            node.textContent = text;
            hasField = true;
            var field = form.querySelector('[name="' + key + '"]');
            if (field) {
                field.setAttribute('aria-invalid', 'true');
            }
        });
        var general = (errors.__all__ || []).join(' ');
        if (general) {
            showStatus(form, general);
            return;
        }
        if (!hasField) {
            showStatus(form, data.message || modal.getAttribute('data-error-text') || '');
        }
    }

    function showSuccess(message) {
        var form = modal.querySelector('[data-consult-form]');
        var success = modal.querySelector('[data-consult-success]');
        if (form) {
            form.hidden = true;
        }
        if (success) {
            success.hidden = false;
            success.textContent = message || '';
        }
    }

    function bindForm() {
        var form = modal.querySelector('[data-consult-form]');
        if (!form || typeof window.fetch !== 'function') {
            return;
        }
        form.addEventListener('submit', function (event) {
            if (event.defaultPrevented || submitting) {
                return;
            }
            event.preventDefault();
            submitting = true;
            clearErrors(form);
            var submit = form.querySelector('[type="submit"]');
            if (submit) {
                submit.disabled = true;
            }
            var headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            };
            var csrfInput = form.querySelector('[name="csrfmiddlewaretoken"]');
            if (csrfInput && csrfInput.value) {
                headers['X-CSRFToken'] = csrfInput.value;
            }
            window.fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: headers,
                credentials: 'same-origin'
            }).then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            }).then(function (result) {
                if (result.data && result.data.ok) {
                    showSuccess(result.data.message);
                    return;
                }
                showErrors(form, result.data || {});
            }).catch(function () {
                showStatus(form, modal.getAttribute('data-error-text') || '');
            }).then(function () {
                submitting = false;
                if (submit && !form.hidden) {
                    submit.disabled = false;
                }
            });
        });
    }

    document.addEventListener('click', function (event) {
        if (event.target.closest('[data-consult-open]')) {
            event.preventDefault();
            openModal();
            rememberHash();
            return;
        }
        var close = event.target.closest('[data-consult-close]');
        if (close && modal.contains(close)) {
            event.preventDefault();
            hideModal();
            return;
        }
        if (event.target === modal) {
            hideModal();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || !modal.classList.contains('is-open')) {
            return;
        }
        hideModal();
    });

    window.addEventListener('hashchange', function () {
        if (window.location.hash === '#consult-modal') {
            openModal();
            return;
        }
        hideModal(false);
    });

    function init() {
        bindForm();
        if (window.location.hash === '#consult-modal') {
            openModal();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
