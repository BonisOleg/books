from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.ratelimit import is_rate_limited

from .forms import ConsultationForm
from .models import ConsultationRequest, Product
from .notifications import send_consultation_notification


def _consult_rate_limited(request):
    ip_limit, ip_period = getattr(settings, 'ABUSE_CONSULT_IP', (5, 60))
    return is_rate_limited(
        request,
        'consult',
        ip_limit=ip_limit,
        ip_period=ip_period,
    )


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _form_errors(form):
    return {
        field: [str(error) for error in errors]
        for field, errors in form.errors.items()
    }


def _first_error(errors, fallback):
    for texts in errors.values():
        if texts:
            return texts[0]
    return fallback


def _respond(request, product, *, ok, message, errors=None, status=200):
    if _is_ajax(request):
        payload = {'ok': ok, 'message': message}
        if errors:
            payload['errors'] = errors
        return JsonResponse(
            payload,
            status=status,
            json_dumps_params={'ensure_ascii': False},
        )
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(product.get_absolute_url())


@require_POST
def consultation_request(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True,
        show_consult_button=True,
    )
    if _consult_rate_limited(request):
        return _respond(
            request,
            product,
            ok=False,
            message=_('Забагато спроб. Спробуйте пізніше.'),
            status=429,
        )

    form = ConsultationForm(request.POST, request=request)
    if not form.is_valid():
        errors = _form_errors(form)
        return _respond(
            request,
            product,
            ok=False,
            message=_first_error(errors, _('Не вдалося надіслати форму. Спробуйте ще раз.')),
            errors=errors,
            status=400,
        )

    consultation = ConsultationRequest(
        product=product,
        product_name=(product.name or '')[:400],
        product_url=request.build_absolute_uri(product.get_absolute_url())[:500],
        name=form.cleaned_data['name'],
        phone=form.cleaned_data['phone'],
        question=form.cleaned_data['question'],
    )
    consultation.save()
    send_consultation_notification(consultation)
    return _respond(
        request,
        product,
        ok=True,
        message=_('Дякуємо! Ми зв\'яжемося з вами найближчим часом.'),
    )
