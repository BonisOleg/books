"""Які атрибути показувати в тулбарі категорії та каталогу."""
from products.filters import attribute_params
from products.models import Category, FilterAttribute, FilterValue


def category_branch_ids(category):
    """Та сама гілка, що й лістинг категорії: сама категорія і прямі діти."""
    ids = [category.pk]
    ids.extend(
        Category.objects.filter(
            parent=category, is_active=True,
        ).values_list('pk', flat=True)
    )
    return ids


def preserved_query(params):
    """Параметри, які форма фільтрів має зберегти. f_* і page збираються окремо."""
    items = []
    for key in params:
        if key in ('page', 'sort') or (isinstance(key, str) and key.startswith('f_')):
            continue
        for value in _values(params, key):
            items.append((key, value))
    return items


def attribute_filter_choices(product_qs, category, params):
    selected = attribute_params(params)
    attributes = _visible_attributes(category)
    if not attributes:
        return []
    attr_ids = [attr.pk for attr in attributes]
    values = (
        FilterValue.objects.filter(
            attribute_id__in=attr_ids,
            products__in=product_qs.order_by().values('pk'),
        )
        .select_related('attribute')
        .order_by('position', 'name', 'pk')
        .distinct()
    )
    buckets = {attr.pk: [] for attr in attributes}
    for value in values:
        chosen = selected.get(value.attribute.slug, [])
        buckets[value.attribute_id].append({
            'slug': value.slug,
            'name': value.name,
            'selected': value.slug in chosen,
        })
    result = []
    for attr in attributes:
        options = buckets[attr.pk]
        if not options:
            continue
        result.append({
            'slug': attr.slug,
            'name': attr.name,
            'selected_count': sum(1 for option in options if option['selected']),
            'values': options,
        })
    return result


def _visible_attributes(category):
    attributes = FilterAttribute.objects.filter(is_active=True).prefetch_related(
        'categories',
    ).order_by('position', 'name', 'pk')
    visible = []
    for attr in attributes:
        categories = list(attr.categories.all())
        if not categories or (category is not None and category in categories):
            visible.append(attr)
    return visible


def _values(params, key):
    if hasattr(params, 'getlist'):
        return [value for value in params.getlist(key) if value != '']
    raw = params.get(key)
    if raw in (None, ''):
        return []
    if isinstance(raw, (list, tuple)):
        return [value for value in raw if value != '']
    return [raw]
