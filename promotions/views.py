from django.shortcuts import render
from django.utils import timezone
from products.models import Product
from .models import GiftPickerQuestion, Promotion


def promotion_list(request):
    now = timezone.now()
    promotions = (
        Promotion.objects
        .filter(is_active=True, start_date__lte=now, end_date__gte=now)
        .select_related('product')
        .prefetch_related('product__images')
        .order_by('end_date')
    )
    return render(request, 'promotions/promotion_list.html', {
        'promotions': promotions,
        'page_title': 'Акції',
    })


def gift_picker(request):
    questions = GiftPickerQuestion.objects.filter(
        is_active=True
    ).prefetch_related('options__categories').order_by('order')

    return render(request, 'promotions/gift_picker.html', {
        'questions': questions,
        'page_title': 'Підібрати подарунок',
    })


def gift_picker_results(request):
    selected_options = request.GET.getlist('option')
    category_ids = set()
    price_min = None
    price_max = None

    from .models import GiftPickerOption
    options = GiftPickerOption.objects.filter(
        id__in=selected_options
    ).prefetch_related('categories')

    for opt in options:
        for cat in opt.categories.all():
            category_ids.add(cat.id)
        if opt.price_min is not None and (price_min is None or opt.price_min < price_min):
            price_min = opt.price_min
        if opt.price_max is not None and (price_max is None or opt.price_max > price_max):
            price_max = opt.price_max

    qs = Product.objects.filter(is_active=True)
    if category_ids:
        qs = qs.filter(category_id__in=category_ids)
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)

    products = qs.select_related('category').prefetch_related('images')[:20]

    return render(request, 'promotions/gift_results.html', {
        'products': products,
    })
