from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _

from core.form_guards import form_ts_field, honeypot_field, issue_form_ts, validate_form_guards
from core.validators import PHONE_WIDGET_ATTRS, validate_ua_phone

from .models import Badge, FilterOption, FilterValue, Product, ProductGroup, ProductVideo
from .widgets import use_filter_value_autocomplete


class ProductVideoForm(forms.ModelForm):
    class Meta:
        model = ProductVideo
        fields = '__all__'
        error_messages = {
            'video_url': {
                'invalid': 'Вкажіть коректне посилання на YouTube.',
            },
        }


class FilterOptionForm(forms.ModelForm):
    class Meta:
        model = FilterOption
        fields = '__all__'

    def __init__(self, *args, filter_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        if filter_type == 'stock':
            choices = [('', '---')] + Product.STOCK_CHOICES
            self.fields['value'].widget = forms.Select(choices=choices)
            self.fields['value'].help_text = 'Оберіть статус наявності зі списку.'
        elif filter_type == 'badge':
            badges = list(
                Badge.objects.values_list('slug', 'name_uk').order_by('order')
            )
            choices = [('', '---')] + [(slug, f'{name}  [{slug}]') for slug, name in badges]
            self.fields['value'].widget = forms.Select(choices=choices)
            self.fields['value'].help_text = 'Оберіть мітку зі списку.'
        else:
            self.fields['value'].widget = forms.HiddenInput()
            self.fields['value'].required = False


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data]
        return single_clean(data, initial)


class ProductAdminForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=ProductGroup.objects.all(),
        required=False,
        label='Групи',
        widget=FilteredSelectMultiple('Групи', False),
    )
    filter_values = forms.ModelMultipleChoiceField(
        label='Значення фільтрів',
        queryset=FilterValue.objects.none(),
        required=False,
        help_text='Можна обрати кілька. Пошук за назвою атрибута або значення.',
    )

    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and 'groups' in self.fields:
            self.fields['groups'].initial = self.instance.groups.all()
        field = self.fields['filter_values']
        field.queryset = FilterValue.objects.select_related('attribute').order_by(
            'attribute__position', 'attribute__name', 'position', 'name',
        )
        use_filter_value_autocomplete(field)
        if self.instance.pk:
            field.initial = self.instance.filter_values.all()

    def _save_m2m(self):
        super()._save_m2m()
        if 'groups' in self.cleaned_data:
            self.instance.groups.set(self.cleaned_data['groups'])

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if 'filter_values' not in self.cleaned_data:
            return instance
        if commit:
            self._save_filter_values()
            return instance
        original_save_m2m = self.save_m2m

        def save_m2m():
            original_save_m2m()
            self._save_filter_values()

        self.save_m2m = save_m2m
        return instance

    def _save_filter_values(self):
        self.instance.filter_values.set(self.cleaned_data['filter_values'])


class AddFilterValuesForm(forms.Form):
    filter_values = forms.ModelMultipleChoiceField(
        label='Значення фільтра',
        queryset=FilterValue.objects.none(),
        required=True,
        help_text='Їх буде додано до вибраних товарів. Уже призначені значення не знімаються.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['filter_values']
        field.queryset = FilterValue.objects.select_related('attribute').order_by(
            'attribute__position', 'attribute__name', 'position', 'name',
        )
        use_filter_value_autocomplete(field)


class BulkImageUploadForm(forms.Form):
    images = MultipleFileField(
        label='Зображення',
        help_text='Виберіть кілька файлів одночасно (Ctrl/Cmd+клік).',
    )


class ConsultationForm(forms.Form):
    name = forms.CharField(
        label=_('Ім\'я'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': _('Ім\'я'),
            'autocomplete': 'name',
            'autocapitalize': 'words',
            'maxlength': '150',
            'enterkeyhint': 'next',
        }),
        error_messages={
            'required': _('Вкажіть ім\'я.'),
            'max_length': _('Ім\'я занадто довге.'),
        },
    )
    phone = forms.CharField(
        label=_('Телефон'),
        max_length=30,
        widget=forms.TextInput(attrs={
            **PHONE_WIDGET_ATTRS,
            'enterkeyhint': 'next',
        }),
        error_messages={
            'required': _('Вкажіть телефон.'),
        },
    )
    question = forms.CharField(
        label=_('Питання'),
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 4,
            'placeholder': _('Ваше питання'),
            'autocomplete': 'off',
            'autocapitalize': 'sentences',
            'maxlength': '2000',
        }),
        error_messages={
            'required': _('Напишіть питання.'),
            'max_length': _('Питання занадто довге.'),
        },
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
