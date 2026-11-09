document.addEventListener('DOMContentLoaded', function () {
    const burger = document.getElementById('burger-btn');
    const menu = document.getElementById('mobile-menu');
    const overlay = document.getElementById('mobile-overlay');
    const closeBtn = document.getElementById('mobile-close');

    function setMenuOpen(open) {
        if (!menu) return;
        var restoreFocus = !open && (
            menu.contains(document.activeElement) || document.activeElement === closeBtn
        );
        menu.classList.toggle('is-open', open);
        menu.setAttribute('aria-hidden', open ? 'false' : 'true');
        if (overlay) overlay.classList.toggle('is-visible', open);
        if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.body.style.overflow = open ? 'hidden' : '';
        if (open && closeBtn) {
            closeBtn.focus();
        } else if (restoreFocus && burger) {
            burger.focus();
        }
    }

    if (burger) burger.addEventListener('click', function () { setMenuOpen(true); });
    if (closeBtn) closeBtn.addEventListener('click', function () { setMenuOpen(false); });
    if (overlay) overlay.addEventListener('click', function () { setMenuOpen(false); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && menu && menu.classList.contains('is-open')) {
            setMenuOpen(false);
        }
    });

    const scrollUp = document.getElementById('scroll-up');
    const scrollDown = document.getElementById('scroll-down');

    function updateScrollButtons() {
        var scrollY = window.pageYOffset || document.documentElement.scrollTop;
        var docHeight = document.documentElement.scrollHeight;
        var winHeight = window.innerHeight;

        if (scrollUp) {
            if (scrollY > 300) {
                scrollUp.classList.add('is-visible');
            } else {
                scrollUp.classList.remove('is-visible');
            }
        }

        if (scrollDown) {
            if (scrollY + winHeight < docHeight - 200) {
                scrollDown.classList.add('is-visible');
            } else {
                scrollDown.classList.remove('is-visible');
            }
        }
    }

    window.addEventListener('scroll', updateScrollButtons, { passive: true });
    updateScrollButtons();

    if (scrollUp) {
        scrollUp.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
    if (scrollDown) {
        scrollDown.addEventListener('click', function () {
            window.scrollTo({
                top: document.documentElement.scrollHeight,
                behavior: 'smooth'
            });
        });
    }

    var cartIcon = document.getElementById('cart-icon');
    var miniCart = document.getElementById('mini-cart');
    if (cartIcon && miniCart) {
        var hideTimeout;
        function showMiniCart() {
            clearTimeout(hideTimeout);
            fetch('/cart/mini/')
                .then(function (r) { return r.text(); })
                .then(function (html) {
                    miniCart.innerHTML = html;
                    miniCart.classList.add('is-visible');
                });
        }
        function hideMiniCart() {
            hideTimeout = setTimeout(function () {
                miniCart.classList.remove('is-visible');
            }, 300);
        }
        cartIcon.parentElement.addEventListener('mouseenter', showMiniCart);
        cartIcon.parentElement.addEventListener('mouseleave', hideMiniCart);
    }

    document.querySelectorAll('select[data-auto-submit]').forEach(function (select) {
        select.addEventListener('change', function () {
            if (select.form) {
                select.form.submit();
            }
        });
    });

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail.target && evt.detail.target.id === 'cart-count') {
            var count = evt.detail.target.textContent.trim();
            evt.detail.target.classList.toggle(
                'header__cart-count--hidden',
                count === '0' || count === ''
            );
        }
    });

    // #region agent log
    function __dbgCardGap(runId) {
        var grid = document.getElementById('product-grid');
        if (!grid) return;
        var cards = grid.querySelectorAll(':scope > .product-card');
        if (!cards.length) return;
        var supportsSubgrid = CSS.supports('grid-template-rows', 'subgrid');
        var gridCs = getComputedStyle(grid);
        var samples = [];
        var n = Math.min(cards.length, 4);
        for (var i = 0; i < n; i++) {
            var card = cards[i];
            var cs = getComputedStyle(card);
            var price = card.querySelector('.product-card__price');
            var actions = card.querySelector('.product-card__actions');
            var name = card.querySelector('.product-card__name');
            var rating = card.querySelector('.product-card__rating');
            var stock = card.querySelector('.product-card__stock');
            var badges = card.querySelector('.product-card__badges');
            var priceRect = price ? price.getBoundingClientRect() : null;
            var actionsRect = actions ? actions.getBoundingClientRect() : null;
            var gap = (priceRect && actionsRect) ? Math.round(actionsRect.top - priceRect.bottom) : null;
            var kids = Array.prototype.map.call(card.children, function (el) {
                var r = el.getBoundingClientRect();
                var kcs = getComputedStyle(el);
                return {
                    cls: (el.className || '').toString().slice(0, 60),
                    tag: el.tagName,
                    h: Math.round(r.height),
                    mt: kcs.marginTop,
                    mb: kcs.marginBottom,
                    flex: kcs.flexGrow + '/' + kcs.flexShrink + '/' + kcs.flexBasis,
                    gridRow: kcs.gridRow,
                    pos: kcs.position
                };
            });
            samples.push({
                idx: i,
                gapPx: gap,
                cardH: Math.round(card.getBoundingClientRect().height),
                display: cs.display,
                gridTemplateRows: cs.gridTemplateRows,
                alignContent: cs.alignContent,
                alignItems: cs.alignItems,
                height: cs.height,
                alignSelf: cs.alignSelf,
                actionsMt: actions ? getComputedStyle(actions).marginTop : null,
                nameH: name ? Math.round(name.getBoundingClientRect().height) : null,
                ratingH: rating ? Math.round(rating.getBoundingClientRect().height) : null,
                ratingEmpty: rating ? !rating.childElementCount : null,
                stockH: stock ? Math.round(stock.getBoundingClientRect().height) : null,
                priceH: price ? Math.round(price.getBoundingClientRect().height) : null,
                actionsH: actions ? Math.round(actions.getBoundingClientRect().height) : null,
                badgesPos: badges ? getComputedStyle(badges).position : null,
                childCount: card.children.length,
                kids: kids
            });
        }
        var payload = {
            sessionId: '1b699f',
            runId: runId || 'pre-fix',
            hypothesisId: 'A-E',
            location: 'main.js:__dbgCardGap',
            message: 'catalog product-card gap metrics',
            data: {
                href: location.pathname,
                supportsSubgrid: supportsSubgrid,
                gridDisplay: gridCs.display,
                gridAlignItems: gridCs.alignItems,
                gridAlignContent: gridCs.alignContent,
                gridAutoRows: gridCs.gridAutoRows,
                gridTemplateRows: gridCs.gridTemplateRows,
                cardCount: cards.length,
                samples: samples
            },
            timestamp: Date.now()
        };
        fetch('http://127.0.0.1:7774/ingest/748b8ee3-a088-4e52-998c-fdb671f90a2b', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '1b699f' },
            body: JSON.stringify(payload)
        }).catch(function () {});
        try {
            console.info('[dbg-card-gap]', payload.data);
        } catch (e) {}
    }
    __dbgCardGap('pre-fix');
    window.addEventListener('load', function () { __dbgCardGap('pre-fix-load'); });
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail && evt.detail.target && evt.detail.target.id === 'product-grid') {
            __dbgCardGap('pre-fix-htmx');
        }
    });
    // #endregion
});
