from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.admin.sites import NotRegistered
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.text import capfirst

from .models import CustomUser

SUPERUSER_HELP = (
    'Не ставте суперкористувача менеджерам. Суперкористувач обходить усі групи '
    'й права. Менеджеру достатньо статусу персоналу та групи «Менеджер товарів» '
    'або «Менеджер замовлень».'
)

_PERMISSION_VERBS = {
    'view': 'може переглядати',
    'add': 'може додавати',
    'change': 'може редагувати',
    'delete': 'може видаляти',
}


def permission_label(perm):
    """«Назва моделі — може переглядати/додавати/редагувати/видаляти»."""
    action, separator, _rest = (perm.codename or '').partition('_')
    model = perm.content_type.model_class()
    if model is not None:
        verbose = capfirst(str(model._meta.verbose_name))
    else:
        verbose = capfirst(str(perm.content_type.name))
    verb = _PERMISSION_VERBS.get(action) if separator else None
    if verb:
        return f'{verbose} — {verb}'
    return f'{verbose} — {perm.name}'


def _guide_description():
    return format_html(
        '<a href="{}">Як додати менеджера</a>',
        reverse('admin:how_to_add_manager'),
    )


def how_to_add_manager_view(request):
    context = {
        **admin.site.each_context(request),
        'title': 'Як додати менеджера',
    }
    return render(request, 'admin/how_to_add_manager.html', context)


def _install_admin_extras():
    site = admin.site
    site.site_header = 'Адмінка магазину'
    site.site_title = 'Адмінка магазину'
    site.index_title = 'Керування магазином'
    if getattr(site, '_how_to_add_manager_installed', False):
        return

    original_get_urls = site.get_urls

    def get_urls():
        custom = [
            path(
                'how-to-add-manager/',
                site.admin_view(how_to_add_manager_view),
                name='how_to_add_manager',
            ),
        ]
        return custom + original_get_urls()

    site.get_urls = get_urls
    site._how_to_add_manager_installed = True


try:
    admin.site.unregister(Group)
except NotRegistered:
    pass


@admin.register(Group)
class HumanGroupAdmin(DjangoGroupAdmin):
    filter_horizontal = ('permissions',)

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request=request, **kwargs)
        if db_field.name == 'permissions' and formfield is not None:
            formfield.label_from_instance = permission_label
        return formfield

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'fields': ('name', 'permissions'),
                'description': _guide_description(),
            }),
        )


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Додатково', {'fields': ('phone', 'patronymic')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'password1', 'password2', 'phone', 'patronymic'),
            },
        ),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'is_superuser' and formfield is not None:
            formfield.help_text = SUPERUSER_HELP
        return formfield

    def get_fieldsets(self, request, obj=None):
        fieldsets = []
        guide = _guide_description()
        saw_superuser = False
        for title, options in super().get_fieldsets(request, obj):
            options = dict(options)
            fields = options.get('fields') or ()
            if 'is_superuser' in fields:
                saw_superuser = True
                options['description'] = format_html('{} {}', SUPERUSER_HELP, guide)
            fieldsets.append((title, options))
        if not saw_superuser and fieldsets:
            title, options = fieldsets[0]
            options = dict(options)
            options['description'] = format_html(
                'Після створення увімкніть «Статус персоналу», не вмикайте '
                'суперкористувача і додайте групу. {}',
                guide,
            )
            fieldsets[0] = (title, options)
        return fieldsets


_install_admin_extras()
