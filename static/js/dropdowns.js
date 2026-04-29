(function () {
    'use strict';

    var openWrap = null;

    function closeAll() {
        if (openWrap) {
            openWrap.classList.remove('is-open');
            var trigger = openWrap.querySelector('.cs-trigger');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
            openWrap = null;
        }
    }

    function buildCustomSelect(nativeSelect) {
        var isLang = nativeSelect.classList.contains('header__lang-select');

        var wrap = document.createElement('div');
        wrap.className = 'cs-wrap' + (isLang ? ' cs-wrap--lang' : '');

        var trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'cs-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        var labelSpan = document.createElement('span');
        labelSpan.className = 'cs-trigger__label';

        var arrowSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        arrowSvg.setAttribute('viewBox', '0 0 24 24');
        arrowSvg.setAttribute('fill', 'none');
        arrowSvg.setAttribute('stroke', 'currentColor');
        arrowSvg.setAttribute('stroke-width', '2');
        arrowSvg.setAttribute('aria-hidden', 'true');
        arrowSvg.classList.add('cs-trigger__arrow');

        var polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        polyline.setAttribute('points', '6 9 12 15 18 9');
        arrowSvg.appendChild(polyline);

        trigger.appendChild(labelSpan);
        trigger.appendChild(arrowSvg);

        var dropdown = document.createElement('div');
        dropdown.className = 'cs-dropdown';
        dropdown.setAttribute('role', 'listbox');

        var selectedOpt = nativeSelect.options[nativeSelect.selectedIndex];
        labelSpan.textContent = selectedOpt ? selectedOpt.text : '';

        Array.from(nativeSelect.options).forEach(function (opt) {
            var item = document.createElement('div');
            item.className = 'cs-option' + (opt.selected ? ' is-selected' : '');
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
            item.setAttribute('tabindex', '-1');
            item.dataset.value = opt.value;

            var dot = document.createElement('span');
            dot.className = 'cs-option__dot';

            item.appendChild(dot);
            item.appendChild(document.createTextNode(opt.text));

            item.addEventListener('click', function () {
                nativeSelect.value = opt.value;

                labelSpan.textContent = opt.text;
                dropdown.querySelectorAll('.cs-option').forEach(function (el) {
                    var sel = el.dataset.value === opt.value;
                    el.classList.toggle('is-selected', sel);
                    el.setAttribute('aria-selected', sel ? 'true' : 'false');
                });

                closeAll();
                nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
            });

            dropdown.appendChild(item);
        });

        wrap.appendChild(trigger);
        wrap.appendChild(dropdown);

        nativeSelect.parentNode.insertBefore(wrap, nativeSelect);
        nativeSelect.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;';
        wrap.appendChild(nativeSelect);

        trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            if (wrap.classList.contains('is-open')) {
                closeAll();
            } else {
                closeAll();
                wrap.classList.add('is-open');
                trigger.setAttribute('aria-expanded', 'true');
                openWrap = wrap;
            }
        });

        trigger.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                trigger.click();
            }
            if (e.key === 'Escape') {
                closeAll();
            }
            if (e.key === 'ArrowDown' && wrap.classList.contains('is-open')) {
                e.preventDefault();
                var first = dropdown.querySelector('.cs-option');
                if (first) first.focus();
            }
        });

        dropdown.addEventListener('keydown', function (e) {
            var options = Array.from(dropdown.querySelectorAll('.cs-option'));
            var focused = document.activeElement;
            var idx = options.indexOf(focused);

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (idx < options.length - 1) options[idx + 1].focus();
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (idx > 0) options[idx - 1].focus();
                else { closeAll(); trigger.focus(); }
            }
            if (e.key === 'Escape') {
                closeAll();
                trigger.focus();
            }
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (focused && focused.classList.contains('cs-option')) {
                    focused.click();
                }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('select[data-custom-select]').forEach(buildCustomSelect);
    });

    document.addEventListener('click', closeAll);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAll();
    });
}());
