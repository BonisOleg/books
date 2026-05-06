(function () {
    'use strict';

    function getCsrfToken() {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf('csrftoken=') === 0) {
                return decodeURIComponent(c.substring('csrftoken='.length));
            }
        }
        return '';
    }

    function buildQuickSaveUrl() {
        // /admin/products/product/ → /admin/products/product/quick-save/
        var base = window.location.pathname.replace(/\/+$/, '');
        return base + '/quick-save/';
    }

    function injectSaveButtons() {
        var resultList = document.getElementById('result_list');
        if (!resultList) return;

        var rows = resultList.querySelectorAll('tbody tr');
        if (!rows.length) return;

        // Add header th
        var thead = resultList.querySelector('thead tr');
        if (thead) {
            var th = document.createElement('th');
            th.scope = 'col';
            thead.appendChild(th);
        }

        rows.forEach(function (row) {
            var checkbox = row.querySelector('input[name="_selected_action"]');
            if (!checkbox) return;

            var productId = checkbox.value;

            var td = document.createElement('td');
            td.className = 'field-quick-save';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = 'Зберегти';
            btn.className = 'quick-save-btn';
            btn.dataset.productId = productId;

            td.appendChild(btn);
            row.appendChild(td);

            btn.addEventListener('click', function () {
                saveRow(btn, productId, row);
            });
        });
    }

    function saveRow(btn, productId, row) {
        var priceInput      = row.querySelector('input[name$="-price"]');
        var stockSelect     = row.querySelector('select[name$="-stock_status"]');
        var badgeSelect     = row.querySelector('select[name$="-badge_obj"]');
        var isActiveInput   = row.querySelector('input[name$="-is_active"][type="checkbox"]');

        var payload = { product_id: parseInt(productId, 10) };

        if (priceInput)    payload.price        = priceInput.value;
        if (stockSelect)   payload.stock_status = stockSelect.value;
        if (badgeSelect)   payload.badge_obj    = badgeSelect.value;
        if (isActiveInput) payload.is_active    = isActiveInput.checked;

        btn.disabled = true;
        btn.textContent = '...';
        btn.className = 'quick-save-btn quick-save-btn--loading';

        fetch(buildQuickSaveUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(payload),
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success) {
                btn.textContent = '✓ Збережено';
                btn.className = 'quick-save-btn quick-save-btn--success';
                setTimeout(function () {
                    btn.textContent = 'Зберегти';
                    btn.className = 'quick-save-btn';
                    btn.disabled = false;
                }, 2000);
            } else {
                showError(btn, data.error || 'Помилка');
            }
        })
        .catch(function () {
            showError(btn, 'Помилка мережі');
        });
    }

    function showError(btn, msg) {
        btn.textContent = '✗ ' + msg;
        btn.className = 'quick-save-btn quick-save-btn--error';
        btn.disabled = false;
        setTimeout(function () {
            btn.textContent = 'Зберегти';
            btn.className = 'quick-save-btn';
        }, 3000);
    }

    document.addEventListener('DOMContentLoaded', injectSaveButtons);
}());
