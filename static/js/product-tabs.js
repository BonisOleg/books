document.addEventListener('DOMContentLoaded', function () {
    var navBtns = document.querySelectorAll('.product-tabs__btn');
    if (!navBtns.length) {
        return;
    }

    var panels = document.querySelectorAll('.product-tabs__panel');

    navBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            navBtns.forEach(function (b) { b.classList.remove('is-active'); });
            panels.forEach(function (p) { p.classList.remove('is-active'); });
            btn.classList.add('is-active');
            var panel = document.getElementById('tab-' + btn.dataset.tab);
            if (panel) {
                panel.classList.add('is-active');
            }
        });
    });
});
