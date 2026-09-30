from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import ListView, DetailView

from core.ratelimit import is_rate_limited
from .models import FilterGroup, Product, Category
from .filters import filter_products
from .schema import _plain_text, get_product_schema, get_breadcrumb_schema
from .search import apply_search, search_tokens


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
        ctx['page_title'] = _('Каталог')
        ctx['current_sort'] = self.request.GET.get('sort', 'default')
        ctx['filter_params'] = self.request.GET
        ctx['selected_stocks'] = self.request.GET.getlist('stock')
        ctx['selected_badges'] = self.request.GET.getlist('badge')
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
        ctx['selected_badges'] = self.request.GET.getlist('badge')
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

        # Prevent duplication: if description plain text matches short_description,
        # the tab-desc panel should not repeat content already shown in the info block.
        desc_html = product.description or ''
        short_html = product.short_description or ''
        plain_desc = ' '.join(strip_tags(desc_html).split())
        plain_short = ' '.join(strip_tags(short_html).split())
        if plain_short and plain_desc == plain_short:
            ctx['description_for_tab'] = ''
        else:
            ctx['description_for_tab'] = desc_html

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
        q = self.request.GET.get('q', '')
        qs = Product.objects.filter(is_active=True).prefetch_related(
            'images', 'categories'
        )
        qs = _with_active_promotions(qs)
        qs = apply_search(qs, q)
        qs = filter_products(qs, self.request.GET)
        sort = self.request.GET.get('sort', 'default') or 'default'
        if sort == 'default':
            qs = qs.order_by('rank', '-created_at')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '')
        sort = self.request.GET.get('sort', 'default') or 'default'
        ctx['search_query'] = q
        ctx['search_too_short'] = not search_tokens(q)
        ctx['current_sort'] = sort
        ctx['page_title'] = _('Пошук: %(query)s') % {'query': q} if q else _('Пошук')
        return ctx


class SearchSuggestView(View):
    def get(self, request):
        if is_rate_limited(request, 'search_suggest', ip_limit=60, ip_period=60):
            return HttpResponse(status=429)
        q = request.GET.get('q', '')
        searchable = bool(search_tokens(q))
        products = []
        if searchable:
            qs = apply_search(Product.objects.filter(is_active=True), q)
            products = list(
                qs.order_by('rank', '-created_at')
                .only('id', 'slug', 'price', 'name', 'name_uk', 'name_en', 'name_ru')
                .prefetch_related('images')[:8]
            )
        return render(request, 'products/partials/search_suggest.html', {
            'products': products,
            'query': q,
            'searchable': searchable,
        })
