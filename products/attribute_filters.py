"""Які атрибути показувати в тулбарі категорії та каталогу."""
from django.http import QueryDict

from products.filters import attribute_params
from products.models import Category, FilterAttribute, FilterValue, Product


def clean_catalog_querydict(params, *, drop_page: bool = True) -> QueryDict:
    """GET без порожніх значень і службових HX-параметрів (збереження getlist).

    page за замовчуванням прибирається (номер додає {% filter_querystring page=N %}
    або HX-Push-Url після фільтра/сортування).
    """
    cleaned = QueryDict(mutable=True)
    if params is None:
        return cleaned
    keys = params.keys() if hasattr(params, 'keys') else []
    for key in keys:
        if not isinstance(key, str):
            continue
        if key.lower().startswith('hx'):
            continue
        if key == 'page' and drop_page:
            continue
        if key == 'page':
            for value in _values(params, key):
                try:
                    if int(value) >= 2:
                        cleaned.appendlist(key, str(int(value)))
                except (TypeError, ValueError):
                    continue
            continue
        for value in _values(params, key):
            cleaned.appendlist(key, value)
    return cleaned


def catalog_push_path(request) -> str:
    """Шлях + чистий query для HX-Push-Url (без page і порожніх параметрів)."""
    path = getattr(request, 'path', '/') or '/'
    cleaned = clean_catalog_querydict(getattr(request, 'GET', None), drop_page=True)
    encoded = cleaned.urlencode()
    return f'{path}?{encoded}' if encoded else path


def category_branch_ids(category):
    """Та сама гілка, що й лістинг категорії: сама категорія і прямі діти."""
    ids = [category.pk]
    ids.extend(
        Category.objects.filter(
            parent=category, is_active=True,
        ).values_list('pk', flat=True)
    )
    return ids


def category_listing_products(category):
    """Активні товари сітки категорії, без GET-фільтрів.

    Той самий відбір, що в CategoryDetailView до filter_products:
    is_active=True у цій категорії та її активних прямих дітей.
    «Немає в наявності» лишається в сітці.
    """
    return Product.objects.filter(
        is_active=True,
        categories__id__in=category_branch_ids(category),
    ).distinct()


def active_descendant_ids(category):
    """Ця категорія і всі активні нащадки. Цикли в parent ігноруються."""
    seen = []
    seen_set = set()
    frontier = [category.pk]
    while frontier:
        layer = []
        for pk in frontier:
            if pk in seen_set:
                continue
            seen_set.add(pk)
            seen.append(pk)
            layer.append(pk)
        if not layer:
            break
        frontier = list(
            Category.objects.filter(
                parent_id__in=layer, is_active=True,
            ).values_list('pk', flat=True)
        )
    return seen


def category_has_visible_products(category):
    """Чи є активний товар у категорії або в активних нащадках.

    Фільтр товару той самий, що в лістингу (is_active=True). Гілка лістингу —
    сама категорія і прямі активні діти; глибші нащадки теж тримають предка
    в індексі, навіть якщо сітка предка їх не показує.
    """
    ids = active_descendant_ids(category)
    if not ids:
        return False
    return Product.objects.filter(
        is_active=True,
        categories__id__in=ids,
    ).exists()


def indexable_categories():
    """Активні категорії, у чиєму дереві активних нащадків є активний товар."""
    rows = list(
        Category.objects.filter(is_active=True).values_list('pk', 'parent_id')
    )
    children = {}
    active_ids = []
    for pk, parent_id in rows:
        active_ids.append(pk)
        children.setdefault(parent_id, []).append(pk)
    active_set = set(active_ids)
    populated = set(
        Product.objects.filter(
            is_active=True,
            categories__id__in=active_ids,
        ).values_list('categories__id', flat=True).distinct()
    ) & active_set

    memo = {}

    def _has(pk):
        cached = memo.get(pk)
        if cached is not None:
            return cached
        found = pk in populated
        if not found:
            for child in children.get(pk, ()):
                if _has(child):
                    found = True
                    break
        memo[pk] = found
        return found

    keep = [pk for pk in active_ids if _has(pk)]
    return Category.objects.filter(pk__in=keep)


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


def _category_scope_ids(category):
    """Поточна категорія і всі предки. Каталог (category=None) — порожня множина."""
    if category is None:
        return set()
    scope = {category.pk}
    scope.update(ancestor.pk for ancestor in category.get_ancestors())
    return scope


def _visible_attributes(category):
    """Порожні categories — скрізь, включно з /catalog/.

    Інакше атрибут видно в обраній категорії і в усіх її підкатегоріях:
    збіг із поточною категорією або з будь-яким її предком.
    """
    attributes = FilterAttribute.objects.filter(is_active=True).prefetch_related(
        'categories',
    ).order_by('position', 'name', 'pk')
    scope_ids = _category_scope_ids(category)
    visible = []
    for attr in attributes:
        bound_ids = {cat.pk for cat in attr.categories.all()}
        if not bound_ids or (category is not None and bound_ids & scope_ids):
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
