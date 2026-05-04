(function () {
    'use strict';

    /**
     * Finds consecutive fieldsets with .lang-panel class and wraps each
     * consecutive group in a .lang-panels-container grid div.
     * This makes them appear as side-by-side language windows.
     */
    function wrapLangPanels() {
        var main = document.querySelector('#content-main');
        if (!main) return;

        var allFieldsets = Array.from(main.querySelectorAll('fieldset.module'));
        var groups = [];
        var current = null;

        allFieldsets.forEach(function (fs) {
            if (fs.classList.contains('lang-panel')) {
                if (!current) current = [];
                current.push(fs);
            } else {
                if (current && current.length) {
                    groups.push(current);
                    current = null;
                }
            }
        });
        if (current && current.length) groups.push(current);

        groups.forEach(function (group) {
            var wrapper = document.createElement('div');
            wrapper.className = 'lang-panels-container';
            wrapper.dataset.count = group.length;
            group[0].parentNode.insertBefore(wrapper, group[0]);
            group.forEach(function (fs) {
                wrapper.appendChild(fs);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wrapLangPanels);
    } else {
        wrapLangPanels();
    }
})();
