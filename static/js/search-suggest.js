document.addEventListener('DOMContentLoaded', function () {
    var header = document.querySelector('.site-header');
    var toggle = document.getElementById('header-search-toggle');
    var panel = document.getElementById('header-search');
    var input = document.getElementById('header-search-input');
    var results = document.getElementById('header-search-results');
    var clearBtn = document.getElementById('header-search-clear');
    var burger = document.getElementById('burger-btn');
    var mobileClose = document.getElementById('mobile-close');
    var activeIndex = -1;
    var mobileQuery = window.matchMedia('(max-width: 767px)');

    if (!header || !panel || !input || !results) return;

    function isMobile() {
        return mobileQuery.matches;
    }

    function options() {
        return results.querySelectorAll('[role="option"]');
    }

    function closeResults() {
        results.innerHTML = '';
        results.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        activeIndex = -1;
    }

    function markActive(index) {
        var items = options();
        activeIndex = index;
        items.forEach(function (item, i) {
            item.classList.toggle('is-active', i === index);
        });
        if (items[index]) items[index].scrollIntoView({ block: 'nearest' });
    }

    function setSearchOpen(open) {
        if (!isMobile()) {
            header.classList.remove('is-search-open');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
            return;
        }
        header.classList.toggle('is-search-open', open);
        if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
            if (mobileClose) mobileClose.click();
            input.focus();
        } else {
            closeResults();
        }
    }

    function syncClear() {
        if (!clearBtn) return;
        clearBtn.hidden = !input.value;
    }

    if (toggle) {
        toggle.addEventListener('click', function () {
            setSearchOpen(!header.classList.contains('is-search-open'));
        });
    }

    if (burger) {
        burger.addEventListener('click', function () {
            setSearchOpen(false);
        });
    }

    document.addEventListener('pointerdown', function (event) {
        if (panel.contains(event.target) || (toggle && toggle.contains(event.target))) return;
        if (isMobile() && header.classList.contains('is-search-open')) {
            setSearchOpen(false);
            return;
        }
        closeResults();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        if (isMobile() && header.classList.contains('is-search-open')) {
            setSearchOpen(false);
            if (toggle) toggle.focus();
            event.preventDefault();
            return;
        }
        if (!results.hidden) {
            closeResults();
            event.preventDefault();
        }
    });

    input.addEventListener('input', syncClear);

    input.addEventListener('keydown', function (event) {
        var items = options();
        if (!items.length || results.hidden) return;
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            markActive(Math.min(activeIndex + 1, items.length - 1));
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            markActive(Math.max(activeIndex - 1, 0));
        } else if (event.key === 'Enter' && activeIndex >= 0 && items[activeIndex]) {
            event.preventDefault();
            window.location.href = items[activeIndex].href;
        }
    });

    input.addEventListener('htmx:beforeRequest', function (event) {
        if (input.value.trim().length < 2) {
            event.preventDefault();
            closeResults();
        }
    });

    results.addEventListener('htmx:afterSwap', function () {
        var hasText = results.textContent.trim().length > 0;
        results.hidden = !hasText;
        input.setAttribute('aria-expanded', hasText ? 'true' : 'false');
        activeIndex = -1;
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            input.value = '';
            syncClear();
            closeResults();
            input.focus();
        });
    }

    syncClear();
});
