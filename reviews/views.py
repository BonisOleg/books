from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from products.models import Product
from .models import Review
from .forms import ReviewForm


def product_reviews(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
    form = ReviewForm()
    return render(request, 'products/partials/review_list.html', {
        'reviews': reviews,
        'product': product,
        'review_form': form,
    })


@require_POST
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ReviewForm(request.POST)
    submitted = False
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        if request.user.is_authenticated:
            review.user = request.user
            if not review.author_name:
                review.author_name = request.user.get_full_name() or request.user.username
        review.save()
        submitted = True
        form = ReviewForm()

    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
    return render(request, 'products/partials/review_list.html', {
        'reviews': reviews,
        'product': product,
        'review_form': form,
        'review_submitted': submitted,
    })
