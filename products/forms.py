from django import forms

from .models import Badge, FilterOption, Product


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


class BulkImageUploadForm(forms.Form):
    images = MultipleFileField(
        label='Зображення',
        help_text='Виберіть кілька файлів одночасно (Ctrl/Cmd+клік).',
    )
