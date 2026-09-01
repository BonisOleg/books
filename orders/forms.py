from django import forms
from django.utils.translation import gettext_lazy as _

from core.form_guards import (
    form_ts_field,
    honeypot_field,
    issue_form_ts,
    validate_form_guards,
)
from core.validators import PHONE_WIDGET_ATTRS, validate_ua_phone

from .models import Order


CHECKOUT_MODE_CHOICES = [
    ('guest', _('Я новий покупець (без реєстрації)')),
    ('register', _('Зареєструвати мене після оформлення')),
    ('account', _('У мене вже є акаунт')),
]


class CheckoutForm(forms.ModelForm):
    checkout_mode = forms.ChoiceField(
        label=_('Режим оформлення'),
        choices=CHECKOUT_MODE_CHOICES,
        initial='guest',
        widget=forms.RadioSelect(attrs={'class': 'checkout-mode__input'}),
    )
    website = honeypot_field()
    form_ts = form_ts_field()

    class Meta:
        model = Order
        fields = [
            'first_name', 'last_name', 'patronymic', 'phone',
            'email', 'city', 'warehouse', 'warehouse_ref',
            'comment', 'payment_method',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': _('Ім\'я'),
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': _('Прізвище'),
            }),
            'patronymic': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': _('По батькові'),
            }),
            'phone': forms.TextInput(attrs=PHONE_WIDGET_ATTRS),
            'email': forms.EmailInput(attrs={
                'class': 'form-input', 'placeholder': 'email@example.com',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': _('Місто'),
                'id': 'city-input',
            }),
            'warehouse': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': _('Відділення Нової Пошти'),
                'id': 'warehouse-input',
                'autocomplete': 'off',
            }),
            'warehouse_ref': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 3,
                'placeholder': _('Коментар до замовлення'),
            }),
            'payment_method': forms.RadioSelect(),
        }

    def __init__(self, *args, user=None, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.request = request
        if not self.is_bound:
            self.fields['form_ts'].initial = issue_form_ts()
        if user and user.is_authenticated:
            self.fields['checkout_mode'].initial = 'account'
            self.fields['checkout_mode'].widget = forms.HiddenInput()

    def clean_phone(self):
        return validate_ua_phone(self.cleaned_data.get('phone', ''))

    def clean(self):
        cleaned = super().clean()
        validate_form_guards(
            cleaned.get('website', ''),
            cleaned.get('form_ts', ''),
            request=self.request,
        )
        if cleaned.get('checkout_mode') == 'register' and not cleaned.get('email'):
            self.add_error('email', _('Для реєстрації потрібен email.'))
        return cleaned


class OneClickForm(forms.Form):
    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs=PHONE_WIDGET_ATTRS),
    )
    name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input', 'placeholder': _('Ваше ім\'я'),
        })
    )
    website = honeypot_field()
    form_ts = form_ts_field()

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        if not self.is_bound:
            self.fields['form_ts'].initial = issue_form_ts()

    def clean_phone(self):
        return validate_ua_phone(self.cleaned_data.get('phone', ''))

    def clean(self):
        cleaned = super().clean()
        validate_form_guards(
            cleaned.get('website', ''),
            cleaned.get('form_ts', ''),
            request=self.request,
        )
        return cleaned
