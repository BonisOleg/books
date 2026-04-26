document.addEventListener('DOMContentLoaded', function () {
    const burger = document.getElementById('burger-btn');
    const menu = document.getElementById('mobile-menu');
    const overlay = document.getElementById('mobile-overlay');
    const closeBtn = document.getElementById('mobile-close');

    function openMenu() {
        menu.classList.add('is-open');
        overlay.classList.add('is-visible');
        document.body.style.overflow = 'hidden';
    }

    function closeMenu() {
        menu.classList.remove('is-open');
        overlay.classList.remove('is-visible');
        document.body.style.overflow = '';
    }

    if (burger) burger.addEventListener('click', openMenu);
    if (closeBtn) closeBtn.addEventListener('click', closeMenu);
    if (overlay) overlay.addEventListener('click', closeMenu);

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
                .then(function(r) { return r.text(); })
                .then(function(html) {
                    miniCart.innerHTML = html;
                    miniCart.classList.add('is-visible');
                });
        }
        function hideMiniCart() {
            hideTimeout = setTimeout(function() {
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
});
