from django import forms

from .models import Badge, FilterOption, FilterValue, Product
from .widgets import use_filter_value_autocomplete


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
        field = self.fields['filter_values']
        field.queryset = FilterValue.objects.select_related('attribute').order_by(
            'attribute__position', 'attribute__name', 'position', 'name',
        )
        use_filter_value_autocomplete(field)
        if self.instance.pk:
            field.initial = self.instance.filter_values.all()

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
