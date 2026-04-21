from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .exporters import export_csv, export_excel, export_xml
from .importers import import_csv, import_excel


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
    if request.method == 'POST':
        file_obj = request.FILES.get('file')
        if not file_obj:
            messages.error(request, 'Оберіть файл для імпорту.')
            return redirect('import_export_app:dashboard')

        filename = file_obj.name.lower()
        if filename.endswith('.csv'):
            results = import_csv(file_obj)
        elif filename.endswith('.xlsx'):
            results = import_excel(file_obj)
        else:
            messages.error(request, 'Непідтримуваний формат. Використовуйте CSV або XLSX.')
            return redirect('import_export_app:dashboard')

        return render(request, 'import_export_app/import_results.html', {
            'results': results,
            'page_title': 'Результати імпорту',
        })

    return redirect('import_export_app:dashboard')


@staff_member_required
def dashboard(request):
    return render(request, 'import_export_app/dashboard.html', {
        'page_title': 'Імпорт / Експорт товарів',
    })
