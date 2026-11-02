from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When


def _param_list(params, key):
    if hasattr(params, 'getlist'):
        values = params.getlist(key)
    else:
        raw = params.get(key)
        if raw is None:
            values = []
        elif isinstance(raw, (list, tuple)):
            values = list(raw)
        else:
            values = [raw]
    return [str(value).strip() for value in values if str(value).strip()]


def attribute_params(params):
    """GET f_<slug>=<value>[, …]. Кілька значень одного атрибута — далі OR."""
    selected = {}
    for key in list(params.keys()):
        if not isinstance(key, str) or not key.startswith('f_') or len(key) < 3:
            continue
        values = []
        for value in _param_list(params, key)[:50]:
            if value not in values:
                values.append(value)
        if values:
            selected[key[2:]] = values
    return selected


def apply_attribute_filters(queryset, params):
    """Різні атрибути — AND, значення одного — OR. Exists, щоб M2M не двоїв рядки."""
    from products.models import FilterAttribute, FilterValue

    selected = attribute_params(params)
    if not selected:
        return queryset
    active = set(
        FilterAttribute.objects.filter(
            is_active=True, slug__in=list(selected),
        ).values_list('slug', flat=True)
    )
    for slug, values in selected.items():
        if slug not in active:
            continue
        match = FilterValue.objects.filter(
            attribute__slug=slug,
            attribute__is_active=True,
            slug__in=values,
            products=OuterRef('pk'),
        )
        queryset = queryset.filter(Exists(match))
    return queryset


def filter_products(queryset, params):
    price_min = params.get('price_min')
    price_max = params.get('price_max')
    stock = params.getlist('stock') if hasattr(params, 'getlist') else params.get('stock')
    badge = params.getlist('badge') if hasattr(params, 'getlist') else params.get('badge')
    subcategory = params.getlist('subcategory') if hasattr(params, 'getlist') else params.get('subcategory')
    sort = params.get('sort', 'default')

    if price_min:
        try:
            queryset = queryset.filter(price__gte=float(price_min))
        except (ValueError, TypeError):
            pass

    if price_max:
        try:
            queryset = queryset.filter(price__lte=float(price_max))
        except (ValueError, TypeError):
            pass

    if stock:
        stock_list = stock if isinstance(stock, list) else [stock]
        stock_list = [s for s in stock_list if s]
        if stock_list:
            queryset = queryset.filter(stock_status__in=stock_list)

    if badge:
        badge_list = badge if isinstance(badge, list) else [badge]
        badge_list = [b for b in badge_list if b]
        if badge_list:
            queryset = queryset.filter(
                Q(badge__in=badge_list) | Q(badge_obj__slug__in=badge_list)
            ).distinct()

    if subcategory:
        slug_list = subcategory if isinstance(subcategory, list) else [subcategory]
        slug_list = [s for s in slug_list if s]
        if slug_list:
            queryset = queryset.filter(categories__slug__in=slug_list).distinct()

    queryset = apply_attribute_filters(queryset, params)
    return _order_in_stock_first(queryset, sort)


_SORT_FIELDS = {
    'price_asc': ('price', 'id'),
    'price_desc': ('-price', 'id'),
    'newest': ('-created_at', 'id'),
    'name': ('name', 'id'),
    'default': ('id',),
}


def _order_in_stock_first(queryset, sort):
    """«Немає в наявності» завжди в кінці. «Під замовлення» лишається у своїй групі."""
    fields = _SORT_FIELDS.get(sort or 'default', _SORT_FIELDS['default'])
    return queryset.annotate(
        stock_sort=Case(
            When(stock_status='out', then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).order_by('stock_sort', *fields)
