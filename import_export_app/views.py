from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from products.feed_utils import get_feed_dashboard_context

from .exporters import export_csv, export_excel, export_xml
from .importers import import_csv, import_excel


def _admin_ctx(request, extra=None):
    ctx = {
        'has_permission': request.user.is_active and request.user.is_staff,
    }
    if extra:
        ctx.update(extra)
    return ctx


@staff_member_required
def export_view(request):
    fmt = request.GET.get('format', 'csv')
    if fmt == 'csv':
        return export_csv(request)
    elif fmt == 'excel':
        return export_excel(request)
    elif fmt == 'xml':
        return export_xml(request)
    return redirect('import_export_app:dashboard')


@staff_member_required
def import_view(request):
    if request.method != 'POST':
        return redirect('import_export_app:dashboard')

    file_obj = request.FILES.get('file')
    if not file_obj:
        messages.error(request, 'Оберіть файл для імпорту.')
        return redirect('import_export_app:dashboard')

    language = request.POST.get('language', 'uk')
    if language not in ('uk', 'ru'):
        language = 'uk'
    fetch_images = request.POST.get('fetch_images') == 'on'

    filename = file_obj.name.lower()
    try:
        if filename.endswith('.csv'):
            results = import_csv(file_obj, language=language, fetch_images=fetch_images)
        elif filename.endswith('.xlsx'):
            results = import_excel(file_obj, language=language, fetch_images=fetch_images)
        else:
            messages.error(request, 'Непідтримуваний формат файлу. Використовуйте CSV або XLSX.')
            return redirect('import_export_app:dashboard')
    except Exception:
        messages.error(
            request,
            'Не вдалося обробити файл. Переконайтесь, що файл не пошкоджений '
            'і відповідає формату CSV або XLSX.',
        )
        return redirect('import_export_app:dashboard')

    return render(
        request,
        'import_export_app/import_results.html',
        _admin_ctx(request, {'results': results, 'title': 'Результати імпорту'}),
    )


@staff_member_required
def dashboard(request):
    return render(
        request,
        'import_export_app/dashboard.html',
        _admin_ctx(request, {
            'title': 'Імпорт / Експорт товарів',
            **get_feed_dashboard_context(),
        }),
    )
