(function () {
    'use strict';

    var node = document.getElementById('analytics-config');
    if (!node) return;

    var cfg;
    try {
        cfg = JSON.parse(node.textContent || '{}');
    } catch (e) {
        return;
    }

    window.dataLayer = window.dataLayer || [];

    function injectScript(src) {
        var script = document.createElement('script');
        script.async = true;
        script.src = src;
        document.head.appendChild(script);
    }

    function installFbq() {
        if (window.fbq) return;
        var queue = function () {
            queue.callMethod
                ? queue.callMethod.apply(queue, arguments)
                : queue.queue.push(arguments);
        };
        if (!window._fbq) window._fbq = queue;
        queue.push = queue;
        queue.loaded = true;
        queue.version = '2.0';
        queue.queue = [];
        window.fbq = queue;
    }

    function injectHtml(html) {
        if (!html) return;
        var host = document.createElement('div');
        host.innerHTML = html;
        var scripts = Array.prototype.slice.call(host.querySelectorAll('script'));
        scripts.forEach(function (script) { script.parentNode.removeChild(script); });
        while (host.firstChild) {
            document.body.appendChild(host.firstChild);
        }
        scripts.forEach(function (old) {
            var script = document.createElement('script');
            Array.prototype.forEach.call(old.attributes, function (attr) {
                script.setAttribute(attr.name, attr.value);
            });
            script.text = old.text || old.textContent || '';
            document.body.appendChild(script);
        });
    }

    var started = false;

    function load() {
        if (started) return;
        started = true;

        if (cfg.gtm) {
            window.dataLayer.push({
                'gtm.start': new Date().getTime(),
                event: 'gtm.js'
            });
            injectScript('https://www.googletagmanager.com/gtm.js?id=' + encodeURIComponent(cfg.gtm));
        }

        /* GTM не змінюємо. Окремий gtag лишається: контейнер не звіряли, дубль GA4 можливий. */
        if (cfg.ga || cfg.ads) {
            window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
            injectScript(
                'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(cfg.ga || cfg.ads)
            );
            window.gtag('js', new Date());
            if (cfg.ga) window.gtag('config', cfg.ga);
            if (cfg.ads) window.gtag('config', cfg.ads);
        }

        if (cfg.pixel) {
            installFbq();
            window.fbq('init', cfg.pixel);
            window.fbq('track', 'PageView');
            injectScript('https://connect.facebook.net/en_US/fbevents.js');
        }

        if (cfg.consultant && document.getElementById('consultant-deferred')) {
            injectHtml(cfg.consultant);
        }
    }

    /* Платний трафік: теги одразу, інакше конверсії GTM на click-слухачах
       (tel:, /t.me, «Купити») губляться на першому кліку до прокрутки. */
    var AD_PARAMS = /(?:^|[?&#])(?:gclid|gbraid|wbraid|dclid|fbclid|ttclid|msclkid|yclid|utm_[a-z]+)=/i;

    function isAdLanding() {
        return AD_PARAMS.test(window.location.search) || AD_PARAMS.test(window.location.hash);
    }

    function arm() {
        if (document.getElementById('purchase-datalayer') || isAdLanding()) {
            load();
            return;
        }

        var events = ['scroll', 'pointerdown', 'keydown', 'touchstart'];
        function onInteract() {
            events.forEach(function (name) {
                window.removeEventListener(name, onInteract);
            });
            load();
        }
        events.forEach(function (name) {
            window.addEventListener(name, onInteract, { passive: true });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arm);
    } else {
        arm();
    }
})();
