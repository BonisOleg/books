(function () {
    function ready(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    function insertButton(input, label) {
        if (!input || input.dataset.npBound === '1') {
            return null;
        }
        input.dataset.npBound = '1';
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'np-origin-lookup__button';
        button.textContent = label;
        input.insertAdjacentElement('afterend', button);
        var list = document.createElement('div');
        list.className = 'np-origin-lookup__results';
        list.hidden = true;
        button.insertAdjacentElement('afterend', list);
        return { button: button, list: list };
    }

    function showResults(list, items, errorText, onPick) {
        list.replaceChildren();
        list.hidden = false;
        if (!items.length) {
            var empty = document.createElement('p');
            empty.className = 'np-origin-lookup__empty';
            empty.textContent = errorText || 'Нічого не знайдено';
            list.appendChild(empty);
            return;
        }
        items.forEach(function (item) {
            var option = document.createElement('button');
            option.type = 'button';
            option.className = 'np-origin-lookup__option';
            option.textContent = item.name || '';
            option.addEventListener('click', function () {
                onPick(item);
                list.hidden = true;
            });
            list.appendChild(option);
        });
    }

    function fetchJson(url) {
        return fetch(url, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        }).then(function (response) {
            return response.json();
        }).then(function (data) {
            return {
                results: (data && data.results) || [],
                error: (data && data.error) || '',
            };
        }).catch(function () {
            return { results: [], error: 'НП не відповідає' };
        });
    }

    ready(function () {
        var config = document.getElementById('np-origin-lookup');
        if (!config) {
            return;
        }
        var cityName = document.getElementById('id_city_name');
        var cityRef = document.getElementById('id_city_ref');
        var warehouseName = document.getElementById('id_warehouse_name');
        var warehouseRef = document.getElementById('id_warehouse_ref');
        var streetName = document.getElementById('id_street_name');
        var streetRef = document.getElementById('id_street_ref');
        var settlementRef = '';

        var cityUi = insertButton(cityName, 'Знайти місто');
        if (cityUi) {
            cityUi.button.addEventListener('click', function () {
                var query = cityName.value.trim();
                fetchJson(config.dataset.citiesUrl + '?q=' + encodeURIComponent(query)).then(function (data) {
                    showResults(cityUi.list, data.results, data.error, function (item) {
                        if (item.name) {
                            cityName.value = item.name;
                        }
                        if (cityRef) {
                            cityRef.value = item.ref || '';
                        }
                        settlementRef = item.settlement_ref || '';
                    });
                });
            });
        }

        var warehouseUi = insertButton(warehouseName, 'Знайти відділення');
        if (warehouseUi) {
            warehouseUi.button.addEventListener('click', function () {
                var ref = cityRef ? cityRef.value.trim() : '';
                var query = warehouseName.value.trim();
                var url = config.dataset.warehousesUrl
                    + '?city_ref=' + encodeURIComponent(ref)
                    + '&q=' + encodeURIComponent(query);
                fetchJson(url).then(function (data) {
                    showResults(warehouseUi.list, data.results, data.error, function (item) {
                        if (item.name) {
                            warehouseName.value = item.name;
                        }
                        if (warehouseRef) {
                            warehouseRef.value = item.ref || '';
                        }
                    });
                });
            });
        }

        var streetUi = insertButton(streetName, 'Знайти вулицю');
        if (!streetUi) {
            return;
        }
        streetUi.button.addEventListener('click', function () {
            function searchStreets(ref) {
                var query = streetName.value.trim();
                var url = config.dataset.streetsUrl
                    + '?settlement_ref=' + encodeURIComponent(ref)
                    + '&q=' + encodeURIComponent(query);
                fetchJson(url).then(function (data) {
                    showResults(streetUi.list, data.results, data.error, function (item) {
                        if (item.name) {
                            streetName.value = item.name;
                        }
                        if (streetRef) {
                            streetRef.value = item.ref || '';
                        }
                    });
                });
            }

            if (settlementRef) {
                searchStreets(settlementRef);
                return;
            }
            var query = cityName ? cityName.value.trim() : '';
            fetchJson(config.dataset.citiesUrl + '?q=' + encodeURIComponent(query)).then(function (data) {
                var first = data.results[0];
                if (!first || !first.settlement_ref) {
                    showResults(streetUi.list, [], data.error || 'Спочатку оберіть місто', function () {});
                    return;
                }
                settlementRef = first.settlement_ref;
                if (cityRef && first.ref) {
                    cityRef.value = first.ref;
                }
                searchStreets(settlementRef);
            });
        });
    });
}());
