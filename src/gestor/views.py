import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from .models import Toolkit, Gop, Revision, Gop_revision, Evidencia, PlanAccion
from .forms import ToolkitForm, GopFormSet, RevisionForm, PlanAccionForm
from .utils import (
    resumen_toolkit, todos_gops_no_cumplidos,
    calcular_cumplimiento_mensual, calcular_cumplimiento_mensual_ampliado,
    gop_menor_cumplimiento, contar_gops_no_cumplidos,
)


def listar_toolkits(request):
    toolkits = Toolkit.objects.all()
    datos = []
    for tk in toolkits:
        datos.append({
            'toolkit': tk,
            'porcentaje': tk.porcentaje_actual(),
            'ultima': tk.ultima_revision,
        })
    return render(request, 'toolkits.html', {
        'toolkits': datos,
        'nav_active': 'toolkits',
    })


@transaction.atomic
def crear_toolkit(request):
    if request.method == 'POST':
        form = ToolkitForm(request.POST)
        formset = GopFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            toolkit = form.save(commit=False)
            toolkit.fecha_ultima_modificacion = timezone.now().date()
            toolkit.save()
            formset.instance = toolkit
            formset.save()
            messages.success(request, 'Toolkit creado correctamente.')
            return redirect('listar_toolkits')
        if not form.is_valid():
            if 'nombre' in form.errors:
                for error in form.errors['nombre']:
                    if 'unique' in error or 'ya existe' in error.lower():
                        messages.error(request, 'Ya existe un Toolkit con ese nombre.')
                    else:
                        messages.error(request, error)
        if not formset.is_valid():
            messages.error(request, 'Debe incluir al menos un GOP.')
    else:
        form = ToolkitForm()
        formset = GopFormSet()
    return render(request, 'crear_toolkit.html', {
        'form': form,
        'formset': formset,
        'nav_active': 'toolkits',
        'titulo': 'Nuevo Toolkit',
    })


def detalle_toolkit(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    gops = toolkit.gops.all()
    return render(request, 'detalle_toolkit.html', {
        'toolkit': toolkit,
        'gops': gops,
        'nav_active': 'toolkits',
    })


@transaction.atomic
def editar_toolkit(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    if request.method == 'POST':
        form = ToolkitForm(request.POST, instance=toolkit)
        formset = GopFormSet(request.POST, instance=toolkit)
        if form.is_valid() and formset.is_valid():
            toolkit = form.save(commit=False)
            toolkit.fecha_ultima_modificacion = timezone.now().date()
            toolkit.save()
            formset.save()
            messages.success(request, 'Toolkit actualizado correctamente.')
            return redirect('detalle_toolkit', pk=pk)
        if not formset.is_valid():
            messages.error(request, 'Debe incluir al menos un GOP.')
    else:
        form = ToolkitForm(instance=toolkit)
        formset = GopFormSet(instance=toolkit)
    return render(request, 'crear_toolkit.html', {
        'form': form,
        'formset': formset,
        'toolkit': toolkit,
        'nav_active': 'toolkits',
        'titulo': f'Editar: {toolkit.nombre}',
    })


@transaction.atomic
def eliminar_toolkit(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    if request.method == 'POST':
        nombre = toolkit.nombre
        toolkit.delete()
        messages.success(request, f'Toolkit "{nombre}" eliminado.')
        return redirect('listar_toolkits')
    return render(request, 'confirmar_eliminar.html', {
        'objeto': toolkit,
        'tipo': 'Toolkit',
        'nav_active': 'toolkits',
    })


def listar_revisiones(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    revisiones = toolkit.revisiones.all()
    if toolkit.por_lineas:
        linea = request.GET.get('linea')
        if linea is not None and linea != '':
            revisiones = revisiones.filter(linea=int(linea))
    else:
        revisiones = revisiones.filter(linea=Revision.LINEA_GENERAL)
    return render(request, 'listar_revisiones.html', {
        'toolkit': toolkit,
        'revisiones': revisiones,
        'lineas_filtro': range(1, 15),
        'nav_active': 'toolkits',
    })


@transaction.atomic
def realizar_revision(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    gops = toolkit.gops.all()

    if not gops.exists():
        messages.error(request, 'Este Toolkit no tiene GOPs registrados.')
        return redirect('detalle_toolkit', pk=pk)

    if request.method == 'POST':
        if request.POST.get('cancelar'):
            return redirect('detalle_toolkit', pk=pk)

        fecha = request.POST.get('fecha_revision', timezone.now().date().isoformat())
        linea = int(request.POST.get('linea', Revision.LINEA_GENERAL))

        revision = Revision.objects.create(
            toolkit=toolkit,
            fecha_revision=fecha,
            linea=linea,
        )

        incompletos = []
        for gop in gops:
            completo = request.POST.get(f'completo_{gop.id}') == 'on'
            comentario = request.POST.get(f'comentario_{gop.id}', '')
            gr = Gop_revision.objects.create(
                gop=gop,
                revision=revision,
                comentario=comentario,
                completo=completo,
            )
            if not completo:
                incompletos.append(gop.numero)

            archivo = request.FILES.get(f'evidencia_{gop.id}')
            if archivo:
                Evidencia.objects.create(
                    gop_revision=gr,
                    archivo=archivo,
                    nombre=archivo.name,
                )

        if incompletos:
            messages.warning(
                request,
                f'Revisión guardada. GOPs incompletos: {", ".join(map(str, incompletos))}. '
                'Considere crear planes de acción.',
            )
        else:
            messages.success(request, 'Revisión completada. Todos los GOPs cumplidos.')

        toolkit.fecha_ultima_modificacion = timezone.now().date()
        toolkit.save()
        return redirect('consultar_revision', pk=pk, revision_id=revision.id)

    lineas = [(Revision.LINEA_GENERAL, 'General')]
    if toolkit.por_lineas:
        lineas += [(i, f'Línea {i}') for i in range(1, 15)]

    return render(request, 'realizar_revision.html', {
        'toolkit': toolkit,
        'gops': gops,
        'lineas': lineas,
        'fecha_hoy': timezone.now().date().isoformat(),
        'nav_active': 'toolkits',
    })


def consultar_revision(request, pk, revision_id):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    revision = get_object_or_404(Revision, pk=revision_id, toolkit=toolkit)
    gop_revisiones = revision.gop_revision_set.select_related('gop').prefetch_related('evidencias')

    fechas = toolkit.revisiones.values_list('id', 'fecha_revision', 'linea').order_by('-fecha_revision')

    return render(request, 'consultar_revision.html', {
        'toolkit': toolkit,
        'revision': revision,
        'gop_revisiones': gop_revisiones,
        'fechas': fechas,
        'nav_active': 'toolkits',
    })


def desglose_revision(request, pk, revision_id=None):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    if revision_id:
        revision = get_object_or_404(Revision, pk=revision_id, toolkit=toolkit)
    else:
        revision = toolkit.ultima_revision
        if not revision:
            messages.warning(request, 'No hay revisiones registradas para este Toolkit.')
            return redirect('detalle_toolkit', pk=pk)

    chart_data = calcular_cumplimiento_mensual(toolkit)
    gop_info = gop_menor_cumplimiento(toolkit)
    planes_abiertos = PlanAccion.objects.filter(
        gop_revision__revision__toolkit=toolkit,
        completado=False,
    ).count()

    fechas = toolkit.revisiones.values_list('id', 'fecha_revision', 'linea').order_by('-fecha_revision')

    return render(request, 'desglose_revision.html', {
        'toolkit': toolkit,
        'revision': revision,
        'porcentaje': revision.porcentaje_cumplimiento(),
        'meta': toolkit.meta,
        'gops_no_cumplidos': revision.gops_no_cumplidos().count(),
        'gop_menor': gop_info[0],
        'gop_menor_pct': gop_info[1],
        'planes_abiertos': planes_abiertos,
        'chart_data': json.dumps(chart_data),
        'fechas': fechas,
        'nav_active': 'toolkits',
    })


def ampliar_grafica(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    chart_data = calcular_cumplimiento_mensual_ampliado(toolkit, meses=12)
    return render(request, 'ampliar_grafica.html', {
        'toolkit': toolkit,
        'chart_data': json.dumps(chart_data),
        'nav_active': 'toolkits',
    })


def gops_no_cumplidos(request):
    resultados = todos_gops_no_cumplidos()
    return render(request, 'gops_no_cumplidos.html', {
        'resultados': resultados,
        'nav_active': 'resumen',
    })


def listar_planes_accion(request, pk=None):
    if pk:
        toolkit = get_object_or_404(Toolkit, pk=pk)
        planes = PlanAccion.objects.filter(
            gop_revision__revision__toolkit=toolkit,
        ).select_related('gop_revision__gop', 'gop_revision__revision')
    else:
        toolkit = None
        planes = PlanAccion.objects.all().select_related(
            'gop_revision__gop', 'gop_revision__revision__toolkit',
        )
    return render(request, 'planes_accion.html', {
        'planes': planes,
        'toolkit': toolkit,
        'nav_active': 'resumen' if not pk else 'toolkits',
    })


def crear_plan_accion(request, pk, revision_id):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    revision = get_object_or_404(Revision, pk=revision_id, toolkit=toolkit)

    if not revision.gops_no_cumplidos().exists():
        messages.warning(request, 'No hay GOPs incumplidos en esta revisión.')
        return redirect('listar_planes_accion', pk=pk)

    if request.method == 'POST':
        form = PlanAccionForm(request.POST, revision=revision)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan de acción creado correctamente.')
            return redirect('listar_planes_accion', pk=pk)
    else:
        form = PlanAccionForm(revision=revision)

    return render(request, 'crear_plan_accion.html', {
        'form': form,
        'toolkit': toolkit,
        'revision': revision,
        'nav_active': 'toolkits',
    })


# def resumen(request):
#     toolkits = Toolkit.objects.all()
#     resumenes = [resumen_toolkit(tk) for tk in toolkits]
#     charts_json = json.dumps([
#         {'id': item['toolkit'].pk, 'data': item['chart_data']}
#         for item in resumenes
#     ])
#     return render(request, 'resumen.html', {
#         'resumenes': resumenes,
#         'charts_json': charts_json,
#         'nav_active': 'resumen',
#     })

def resumen(request):
    toolkits = Toolkit.objects.all()
    resumenes = [resumen_toolkit(tk) for tk in toolkits]
    print(resumenes)
    
    charts_json = json.dumps([
        {'id': item['toolkit'].pk, 'data': item['chart_data']}
        for item in resumenes
    ], cls=DjangoJSONEncoder)
    
    return render(request, 'resumen.html', {
        'resumenes': resumenes,
        'charts_json': charts_json,
        'nav_active': 'resumen',
    })