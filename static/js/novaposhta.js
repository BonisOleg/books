document.addEventListener('DOMContentLoaded', function () {
    var root = document.getElementById('novaposhta-root');
    var citiesUrl = root ? root.dataset.citiesUrl : '/shipping/api/cities/';
    var warehousesUrl = root ? root.dataset.warehousesUrl : '/shipping/api/warehouses/';

    var cityInput = document.getElementById('city-input');
    var cityResults = document.getElementById('city-results');
    var warehouseInput = document.getElementById('warehouse-input');
    var warehouseResults = document.getElementById('warehouse-results');
    var warehouseRef = document.querySelector('[name="warehouse_ref"]');
    var selectedCityRef = '';
    var cityDebounce = null;
    var warehouseDebounce = null;

    function pickBestCity(results, query) {
        if (!results || !results.length) {
            return null;
        }

        if (results.length === 1) {
            return results[0];
        }

        var normalizedQuery = query.trim().toLowerCase();

        var exact = results.find(function (city) {
            return city.name.toLowerCase() === normalizedQuery;
        });
        if (exact) {
            return exact;
        }

        var mainCity = results.find(function (city) {
            return /^м\.\s/.test(city.name);
        });
        if (mainCity) {
            return mainCity;
        }

        return null;
    }

    function renderCityResults(results) {
        if (!cityResults) {
            return;
        }

        cityResults.innerHTML = '';

        if (!results.length) {
            cityResults.classList.remove('is-visible');
            return;
        }

        results.forEach(function (city) {
            var div = document.createElement('div');
            div.className = 'warehouse-autocomplete__item';
            div.textContent = city.name;
            div.addEventListener('click', function () {
                cityInput.value = city.name;
                selectedCityRef = city.ref;
                cityResults.classList.remove('is-visible');
                if (warehouseInput) {
                    warehouseInput.value = '';
                }
                if (warehouseRef) {
                    warehouseRef.value = '';
                }
            });
            cityResults.appendChild(div);
        });
        cityResults.classList.add('is-visible');
    }

    function fetchCities(query) {
        return fetch(citiesUrl + '?q=' + encodeURIComponent(query))
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                return data.results || [];
            })
            .catch(function () {
                return [];
            });
    }

    function resolveCityRef(options) {
        if (!cityInput) {
            return Promise.resolve(false);
        }

        var showDropdown = options && options.showDropdown;
        var query = cityInput.value.trim();

        if (query.length < 2) {
            selectedCityRef = '';
            if (cityResults) {
                cityResults.classList.remove('is-visible');
            }
            return Promise.resolve(false);
        }

        return fetchCities(query).then(function (results) {
            var best = pickBestCity(results, query);

            if (best) {
                selectedCityRef = best.ref;
                if (best.name && best.name !== cityInput.value) {
                    cityInput.value = best.name;
                }
                if (cityResults) {
                    cityResults.classList.remove('is-visible');
                }
                return true;
            }

            if (showDropdown) {
                renderCityResults(results);
            }

            return false;
        });
    }

    if (cityInput && cityResults) {
        cityInput.addEventListener('input', function () {
            clearTimeout(cityDebounce);

            if (!cityInput.value.trim()) {
                selectedCityRef = '';
                cityResults.classList.remove('is-visible');
                return;
            }

            cityDebounce = setTimeout(function () {
                resolveCityRef({ showDropdown: true });
            }, 300);
        });

        cityInput.addEventListener('change', function () {
            resolveCityRef({ showDropdown: false });
        });

        cityInput.addEventListener('blur', function () {
            setTimeout(function () {
                resolveCityRef({ showDropdown: false });
            }, 300);
        });

        if (cityInput.value.trim().length >= 2) {
            resolveCityRef({ showDropdown: false });
        }
    }

    if (warehouseInput && warehouseResults) {
        warehouseInput.addEventListener('input', function () {
            clearTimeout(warehouseDebounce);
            warehouseDebounce = setTimeout(function () {
                var q = warehouseInput.value.trim();

                function loadWarehouses() {
                    if (!selectedCityRef) {
                        return;
                    }

                    fetch(warehousesUrl + '?city_ref=' + encodeURIComponent(selectedCityRef) + '&q=' + encodeURIComponent(q))
                        .then(function (response) {
                            return response.json();
                        })
                        .then(function (data) {
                            warehouseResults.innerHTML = '';
                            if (data.results && data.results.length) {
                                data.results.forEach(function (wh) {
                                    var div = document.createElement('div');
                                    div.className = 'warehouse-autocomplete__item';
                                    div.textContent = wh.description;
                                    div.addEventListener('click', function () {
                                        warehouseInput.value = wh.description;
                                        if (warehouseRef) {
                                            warehouseRef.value = wh.ref;
                                        }
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
                }

                if (!selectedCityRef) {
                    resolveCityRef({ showDropdown: false }).then(loadWarehouses);
                    return;
                }

                loadWarehouses();
            }, 300);
        });

        warehouseInput.addEventListener('focus', function () {
            if (!selectedCityRef && cityInput && cityInput.value.trim().length >= 2) {
                resolveCityRef({ showDropdown: false });
            }
        });
    }

    document.addEventListener('click', function (event) {
        if (cityInput && cityResults && !cityInput.contains(event.target) && !cityResults.contains(event.target)) {
            cityResults.classList.remove('is-visible');
        }
        if (warehouseInput && warehouseResults && !warehouseInput.contains(event.target) && !warehouseResults.contains(event.target)) {
            warehouseResults.classList.remove('is-visible');
        }
    });
});
