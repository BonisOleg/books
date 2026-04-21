document.addEventListener('DOMContentLoaded', function () {
    var cityInput = document.getElementById('city-input');
    var cityResults = document.getElementById('city-results');
    var warehouseInput = document.getElementById('warehouse-input');
    var warehouseResults = document.getElementById('warehouse-results');
    var warehouseRef = document.querySelector('[name="warehouse_ref"]');
    var selectedCityRef = '';
    var cityDebounce = null;
    var warehouseDebounce = null;

    if (cityInput && cityResults) {
        cityInput.addEventListener('input', function () {
            clearTimeout(cityDebounce);
            cityDebounce = setTimeout(function () {
                var q = cityInput.value.trim();
                if (q.length < 2) { cityResults.classList.remove('is-visible'); return; }

                fetch('/shipping/api/cities/?q=' + encodeURIComponent(q))
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        cityResults.innerHTML = '';
                        if (data.results && data.results.length) {
                            data.results.forEach(function (city) {
                                var div = document.createElement('div');
                                div.className = 'warehouse-autocomplete__item';
                                div.textContent = city.name;
                                div.addEventListener('click', function () {
                                    cityInput.value = city.name;
                                    selectedCityRef = city.ref;
                                    cityResults.classList.remove('is-visible');
                                    if (warehouseInput) warehouseInput.value = '';
                                    if (warehouseRef) warehouseRef.value = '';
                                });
                                cityResults.appendChild(div);
                            });
                            cityResults.classList.add('is-visible');
                        } else {
                            cityResults.classList.remove('is-visible');
                        }
                    })
                    .catch(function () {
                        cityResults.classList.remove('is-visible');
                    });
            }, 300);
        });
    }

    if (warehouseInput && warehouseResults) {
        warehouseInput.addEventListener('input', function () {
            clearTimeout(warehouseDebounce);
            warehouseDebounce = setTimeout(function () {
                if (!selectedCityRef) return;
                var q = warehouseInput.value.trim();

                fetch('/shipping/api/warehouses/?city_ref=' + encodeURIComponent(selectedCityRef) + '&q=' + encodeURIComponent(q))
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        warehouseResults.innerHTML = '';
                        if (data.results && data.results.length) {
                            data.results.forEach(function (wh) {
                                var div = document.createElement('div');
                                div.className = 'warehouse-autocomplete__item';
                                div.textContent = wh.description;
                                div.addEventListener('click', function () {
                                    warehouseInput.value = wh.description;
                                    if (warehouseRef) warehouseRef.value = wh.ref;
                                    warehouseResults.classList.remove('is-visible');
                                });
                                warehouseResults.appendChild(div);
                            });
                            warehouseResults.classList.add('is-visible');
                        } else {
                            warehouseResults.classList.remove('is-visible');
                        }
                    })
                    .catch(function () {
                        warehouseResults.classList.remove('is-visible');
                    });
            }, 300);
        });
    }

    document.addEventListener('click', function (e) {
        if (cityInput && cityResults && !cityInput.contains(e.target) && !cityResults.contains(e.target)) {
            cityResults.classList.remove('is-visible');
        }
        if (warehouseInput && warehouseResults && !warehouseInput.contains(e.target) && !warehouseResults.contains(e.target)) {
            warehouseResults.classList.remove('is-visible');
        }
    });
});
