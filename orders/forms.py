from django import forms
from .models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'first_name', 'last_name', 'patronymic', 'phone',
            'email', 'city', 'warehouse', 'warehouse_ref',
            'comment', 'payment_method',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Ім\'я',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Прізвище',
            }),
            'patronymic': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'По батькові',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': '+380...',
                'type': 'tel',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input', 'placeholder': 'email@example.com',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Місто',
                'id': 'city-input',
            }),
            'warehouse': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Відділення Нової Пошти',
                'id': 'warehouse-input',
                'autocomplete': 'off',
            }),
            'warehouse_ref': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 3,
                'placeholder': 'Коментар до замовлення',
            }),
            'payment_method': forms.RadioSelect(),
        }


class OneClickForm(forms.Form):
    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input', 'placeholder': '+380...',
            'type': 'tel',
        })
    )
    name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input', 'placeholder': 'Ваше ім\'я',
        })
    )
