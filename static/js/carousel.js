(function () {
    'use strict';

    function initCarousel(el) {
        var track = el.querySelector('.banners__track');
        var slides = el.querySelectorAll('.banners__slide');
        var dots = el.querySelectorAll('.banners__dot');
        var btnPrev = el.querySelector('.banners__btn--prev');
        var btnNext = el.querySelector('.banners__btn--next');

        if (!track || slides.length < 2) return;

        var current = 0;
        var autoTimer = null;
        var autoDelay = parseInt(el.dataset.carouselAuto, 10) || 5000;

        function activateImages(slide) {
            if (!slide) return;
            var imgs = slide.querySelectorAll('img[data-src]');
            for (var i = 0; i < imgs.length; i++) {
                var img = imgs[i];
                if (img.getAttribute('src')) continue;
                if (img.dataset.srcset) img.setAttribute('srcset', img.dataset.srcset);
                if (img.dataset.sizes) img.setAttribute('sizes', img.dataset.sizes);
                img.setAttribute('src', img.dataset.src);
            }
        }

        function warm(index) {
            activateImages(slides[index]);
            activateImages(slides[(index + 1) % slides.length]);
        }

        function goTo(index) {
            current = ((index % slides.length) + slides.length) % slides.length;
            warm(current);
            track.style.transform = 'translateX(-' + (current * 100) + '%)';

            for (var i = 0; i < dots.length; i++) {
                var active = i === current;
                dots[i].classList.toggle('banners__dot--active', active);
                dots[i].setAttribute('aria-selected', active ? 'true' : 'false');
            }
        }

        var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function startAuto() {
            stopAuto();
            if (reduceMotion) return;
            autoTimer = setInterval(function () { goTo(current + 1); }, autoDelay);
        }

        function stopAuto() {
            if (autoTimer) {
                clearInterval(autoTimer);
                autoTimer = null;
            }
        }

        if (btnPrev) {
            btnPrev.addEventListener('click', function () {
                goTo(current - 1);
                startAuto();
            });
        }

        if (btnNext) {
            btnNext.addEventListener('click', function () {
                goTo(current + 1);
                startAuto();
            });
        }

        for (var d = 0; d < dots.length; d++) {
            (function (index) {
                dots[index].addEventListener('click', function () {
                    goTo(index);
                    startAuto();
                });
            })(d);
        }

        el.addEventListener('mouseenter', stopAuto);
        el.addEventListener('mouseleave', function () {
            if (!el.contains(document.activeElement)) startAuto();
        });
        el.addEventListener('focusin', stopAuto);
        el.addEventListener('focusout', function () {
            startAuto();
        });

        /* Touch / swipe (iOS Safari safe: passive listeners) */
        var touchStartX = 0;
        var touchDeltaX = 0;
        var dragging = false;

        el.addEventListener('touchstart', function (e) {
            touchStartX = e.touches[0].clientX;
            touchDeltaX = 0;
            dragging = true;
            stopAuto();
        }, { passive: true });

        el.addEventListener('touchmove', function (e) {
            if (!dragging) return;
            touchDeltaX = e.touches[0].clientX - touchStartX;
        }, { passive: true });

        el.addEventListener('touchend', function () {
            if (dragging && Math.abs(touchDeltaX) > 40) {
                goTo(touchDeltaX < 0 ? current + 1 : current - 1);
            }
            dragging = false;
            startAuto();
        });

        el.addEventListener('touchcancel', function () {
            dragging = false;
            startAuto();
        });

        /* Keyboard navigation */
        el.setAttribute('tabindex', '0');
        el.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowLeft') { goTo(current - 1); startAuto(); }
            if (e.key === 'ArrowRight') { goTo(current + 1); startAuto(); }
        });

        /* Pause when tab is hidden (saves resources) */
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) { stopAuto(); } else { startAuto(); }
        });

        startAuto();
        goTo(0);
        var idleWarm = function () { warm((current + 1) % slides.length); };
        if (window.requestIdleCallback) {
            window.requestIdleCallback(idleWarm, { timeout: 2000 });
        } else {
            window.setTimeout(idleWarm, 300);
        }
    }

    function initAll() {
        var carousels = document.querySelectorAll('[data-carousel]');
        for (var i = 0; i < carousels.length; i++) {
            if (!carousels[i].dataset.carouselInit) {
                carousels[i].dataset.carouselInit = '1';
                initCarousel(carousels[i]);
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    /* HTMX: re-init after dynamic swaps */
    document.addEventListener('htmx:afterSwap', initAll);
})();
