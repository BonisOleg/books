from django import forms
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.translation import gettext_lazy as _

from core.ratelimit import log_abuse

FORM_TS_MIN_SECONDS = 3
FORM_TS_MAX_SECONDS = 3600
FORM_GUARD_ERROR = _('Не вдалося надіслати форму. Спробуйте ще раз.')

HONEYPOT_FIELD_NAME = 'website'
FORM_TS_FIELD_NAME = 'form_ts'


def honeypot_field():
    return forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'class': 'u-hp__input',
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
        }),
    )


def form_ts_field():
    return forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )


def issue_form_ts():
    return TimestampSigner().sign('ok')


def validate_form_guards(honeypot, form_ts, request=None):
    if (honeypot or '').strip():
        log_abuse(request, 'honeypot')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard')

    token = (form_ts or '').strip()
    if not token:
        log_abuse(request, 'form_ts', extra='missing')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard')

    signer = TimestampSigner()
    min_age = max(FORM_TS_MIN_SECONDS - 1, 0)
    try:
        signer.unsign(token, max_age=min_age)
        log_abuse(request, 'form_ts', extra='too_fresh')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard')
    except SignatureExpired:
        pass
    except BadSignature:
        log_abuse(request, 'form_ts', extra='bad_signature')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard') from None

    try:
        signer.unsign(token, max_age=FORM_TS_MAX_SECONDS)
    except SignatureExpired:
        log_abuse(request, 'form_ts', extra='expired')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard') from None
    except BadSignature:
        log_abuse(request, 'form_ts', extra='bad_signature')
        raise forms.ValidationError(FORM_GUARD_ERROR, code='form_guard') from None
