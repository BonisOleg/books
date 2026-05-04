from django.db.models import Prefetch
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from .models import FilterGroup, FilterOption, Product, Category
from .filters import filter_products
from .schema import _plain_text, get_product_schema, get_breadcrumb_schema


def _get_filter_groups(category=None):
    """Return active FilterGroups visible for given category (or all if None)."""
    groups = FilterGroup.objects.filter(is_active=True).prefetch_related(
        'options', 'categories'
    ).order_by('order')
    result = []
    for g in groups:
        cats = list(g.categories.all())
        if not cats or (category and category in cats):
            result.append(g)
    return result


def _with_active_promotions(qs):
    from promotions.models import Promotion
    now = timezone.now()
    active_qs = Promotion.objects.filter(
        is_active=True, start_date__lte=now, end_date__gte=now
    )
    return qs.prefetch_related(
        Prefetch('promotions', queryset=active_qs, to_attr='active_promotions')
    )


class CatalogView(ListView):
    model = Product
    template_name = 'products/category_list.html'
    context_object_name = 'products'
    paginate_by = 24

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).prefetch_related(
            'images', 'categories'
        )
        qs = _with_active_promotions(qs)
        return filter_products(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.filter(
            parent__isnull=True, is_active=True
        ).order_by('order')
        ctx['page_title'] = 'Каталог'
        ctx['current_sort'] = self.request.GET.get('sort', 'default')
        ctx['filter_params'] = self.request.GET
        ctx['selected_stocks'] = self.request.GET.getlist('stock')
        ctx['selected_subcategories'] = self.request.GET.getlist('subcategory')
        return ctx


class CategoryDetailView(ListView):
    template_name = 'products/category_detail.html'
    context_object_name = 'products'
    paginate_by = 24

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs['slug'], is_active=True)
        cat_ids = [self.category.id]
        children = Category.objects.filter(parent=self.category, is_active=True)
        cat_ids.extend(children.values_list('id', flat=True))

        qs = Product.objects.filter(
            is_active=True, categories__id__in=cat_ids
        ).prefetch_related('images', 'categories').distinct()
        qs = _with_active_promotions(qs)
        return filter_products(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['category'] = self.category
        ctx['subcategories'] = Category.objects.filter(
            parent=self.category, is_active=True
        ).order_by('order')
        ctx['page_title'] = self.category.meta_title or self.category.name
        ctx['page_meta_description'] = self.category.meta_description
        ctx['current_sort'] = self.request.GET.get('sort', 'default')
        ctx['filter_params'] = self.request.GET
        ctx['selected_stocks'] = self.request.GET.getlist('stock')
        ctx['selected_subcategories'] = self.request.GET.getlist('subcategory')

        breadcrumbs = [('Головна', '/'), ('Каталог', '/catalog/')]
        for anc in self.category.get_ancestors():
            breadcrumbs.append((anc.name, anc.get_absolute_url()))
        breadcrumbs.append((self.category.name, None))
        ctx['breadcrumbs'] = breadcrumbs
        ctx['breadcrumb_schema'] = get_breadcrumb_schema(breadcrumbs, self.request)
        ctx['filter_groups'] = _get_filter_groups(self.category)
        return ctx

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['products/partials/product_grid.html']
        return ['products/category_detail.html']


class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).prefetch_related(
            'images', 'videos', 'attributes', 'categories'
        )
        return _with_active_promotions(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object
        ctx['page_title'] = product.meta_title or product.name
        raw_meta = product.meta_description or product.short_description
        ctx['page_meta_description'] = _plain_text(raw_meta, max_len=300)
        ctx['product_schema'] = get_product_schema(product, self.request)
        ctx['reviews'] = product.reviews.filter(is_approved=True).order_by('-created_at')

        viewed_ids = self.request.session.get('viewed_products', [])
        previous_viewed = [pid for pid in viewed_ids if pid != product.id]
        if previous_viewed:
            recently_viewed_qs = Product.objects.filter(
                id__in=previous_viewed[:12], is_active=True
            ).prefetch_related('images')
            recently_viewed_map = {p.id: p for p in recently_viewed_qs}
            ctx['recently_viewed'] = [
                recently_viewed_map[pid] for pid in previous_viewed[:12]
                if pid in recently_viewed_map
            ]

        new_history = [product.id] + [pid for pid in viewed_ids if pid != product.id]
        self.request.session['viewed_products'] = new_history[:24]

        breadcrumbs = [('Головна', '/'), ('Каталог', '/catalog/')]
        primary_category = product.categories.first()
        if primary_category:
            for anc in primary_category.get_ancestors():
                breadcrumbs.append((anc.name, anc.get_absolute_url()))
            breadcrumbs.append((primary_category.name, primary_category.get_absolute_url()))
        breadcrumbs.append((product.name, None))
        ctx['breadcrumbs'] = breadcrumbs
        ctx['breadcrumb_schema'] = get_breadcrumb_schema(breadcrumbs, self.request)

        if primary_category:
            ctx['related_products'] = Product.objects.filter(
                categories=primary_category, is_active=True
            ).exclude(id=product.id).prefetch_related('images').distinct()[:8]

        from promotions.models import UpsellGroup, Promotion
        from django.utils import timezone
        try:
            upsell = UpsellGroup.objects.filter(
                trigger_product=product, is_active=True
            ).prefetch_related('suggested_products__images').first()
            if upsell:
                ctx['upsell_products'] = upsell.suggested_products.filter(is_active=True)
        except Exception:
            pass

        try:
            now = timezone.now()
            promotion = Promotion.objects.filter(
                product=product,
                is_active=True,
                start_date__lte=now,
                end_date__gte=now,
            ).first()
            ctx['promotion'] = promotion
            if promotion:
                ctx['timer_end'] = promotion.end_date
            elif product.sale_timer_active:
                ctx['timer_end'] = product.sale_end_date
        except Exception:
            pass

        return ctx


class SearchView(ListView):
    template_name = 'products/category_list.html'
    context_object_name = 'products'
    paginate_by = 24

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).prefetch_related(
            'images', 'categories'
        )
        qs = _with_active_promotions(qs)
        return filter_products(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '')
        ctx['page_title'] = f'Пошук: {q}' if q else 'Пошук'
        ctx['search_query'] = q
        return ctx
