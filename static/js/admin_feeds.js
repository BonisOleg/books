(function () {
    'use strict';

    function copyFeedUrl() {
        var input = document.getElementById('ie-feeds-url');
        var feedback = document.getElementById('ie-feeds-copied');
        if (!input) {
            return;
        }

        var text = input.value;

        function showCopied() {
            if (!feedback) {
                return;
            }
            feedback.classList.add('is-visible');
            window.setTimeout(function () {
                feedback.classList.remove('is-visible');
            }, 2000);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(showCopied).catch(function () {
                fallbackCopy(input, showCopied);
            });
            return;
        }

        fallbackCopy(input, showCopied);
    }

    function fallbackCopy(input, callback) {
        input.focus();
        input.select();
        input.setSelectionRange(0, input.value.length);
        try {
            document.execCommand('copy');
            callback();
        } catch (e) {
            /* ignore */
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('ie-feeds-copy');
        if (btn) {
            btn.addEventListener('click', copyFeedUrl);
        }
    });
})();
