from django.db.models import Q


def filter_products(queryset, params):
    price_min = params.get('price_min')
    price_max = params.get('price_max')
    stock = params.getlist('stock') if hasattr(params, 'getlist') else params.get('stock')
    badge = params.get('badge')
    subcategory = params.getlist('subcategory') if hasattr(params, 'getlist') else params.get('subcategory')
    sort = params.get('sort', 'default')
    q = params.get('q', '').strip()

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(sku__icontains=q)
        )

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
        queryset = queryset.filter(badge=badge)

    if subcategory:
        slug_list = subcategory if isinstance(subcategory, list) else [subcategory]
        slug_list = [s for s in slug_list if s]
        if slug_list:
            queryset = queryset.filter(category__slug__in=slug_list)

    sort_map = {
        'price_asc': 'price',
        'price_desc': '-price',
        'newest': '-created_at',
        'name': 'name',
        'default': 'id',
    }
    order = sort_map.get(sort, 'id')
    queryset = queryset.order_by(order)

    return queryset
