from django.contrib.admin.widgets import AutocompleteSelectMultiple
from django.urls import reverse

from products.models import FilterValue


class FilterValueAutocompleteWidget(AutocompleteSelectMultiple):
    """Autocomplete значень фільтра без поля на моделі Product."""

    def __init__(self, admin_site, attrs=None):
        field = FilterValue._meta.get_field('products')
        super().__init__(field, admin_site, attrs=attrs)

    def get_url(self):
        return reverse('admin:products_filtervalue_autocomplete')

    def optgroups(self, name, value, attr=None):
        selected = []
        for item in value or []:
            text = str(item).strip()
            if text and text not in selected:
                selected.append(text)
        default = (None, [], 0)
        if not selected or not hasattr(self.choices, 'queryset'):
            return [default]
        label_from = self.choices.field.label_from_instance
        selected_set = set(selected)
        for obj in self.choices.queryset.filter(pk__in=selected):
            index = len(default[1])
            default[1].append(
                self.create_option(
                    name, str(obj.pk), label_from(obj), selected_set, index,
                )
            )
        return [default]


def use_filter_value_autocomplete(field):
    from django.contrib import admin
    widget = FilterValueAutocompleteWidget(admin.site)
    widget.is_required = field.required
    field.widget = widget
    field.widget.choices = field.choices
