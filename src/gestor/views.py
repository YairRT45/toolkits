import json
import os
import tempfile

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

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
            num = 0
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False):
                    num += 1
                    gop = f.save(commit=False)
                    gop.toolkit = toolkit
                    gop.numero = num
                    print(num)
                    gop.save()
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
            num = 0
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False):
                    num += 1
                    gop = f.save(commit=False)
                    gop.toolkit = toolkit
                    gop.numero = num
                    gop.save()
                elif f.cleaned_data and f.cleaned_data.get('DELETE', False) and f.instance.pk:
                    f.instance.delete()
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

    session_key = f'revision_lines_{pk}'

    if request.method == 'POST':
        if request.POST.get('cancelar'):
            request.session.pop(session_key, None)
            return redirect('detalle_toolkit', pk=pk)

        fecha = request.POST.get('fecha_revision', timezone.now().date().isoformat())
        linea_actual = int(request.POST.get('linea_actual', 1))
        es_ultima_linea = request.POST.get('guardar') == '1'

        if toolkit.por_lineas:
            if session_key not in request.session:
                request.session[session_key] = {
                    'fecha': fecha,
                    'lineas_data': {},
                }

            session_data = request.session[session_key]
            lineas_data = session_data.get('lineas_data', {})

            gops_data = {}
            for gop in gops:
                completo = request.POST.get(f'completo_{gop.id}') == 'on'
                comentario = request.POST.get(f'comentario_{gop.id}', '')

                gop_data = {
                    'completo': completo,
                    'comentario': comentario,
                }

                archivo = request.FILES.get(f'evidencia_{gop.id}')
                if archivo:
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, f'rev_{pk}_gop_{gop.id}_linea_{linea_actual}_{archivo.name}')
                    with open(temp_path, 'wb') as f:
                        for chunk in archivo.chunks():
                            f.write(chunk)
                    gop_data['archivo_temp'] = temp_path
                    gop_data['archivo_nombre'] = archivo.name

                gops_data[str(gop.id)] = gop_data

            lineas_data[str(linea_actual)] = {'gops': gops_data}

            session_data['lineas_data'] = lineas_data
            session_data['fecha'] = fecha
            request.session[session_key] = session_data
            request.session.modified = True
            request.session.save()

            if es_ultima_linea:
                incompletos = []
                ultima_revision = None

                for linea_num in range(1, 15):
                    ld = lineas_data.get(str(linea_num))
                    if not ld:
                        incompletos.extend([g.numero for g in gops])
                        continue

                    revision = Revision.objects.create(
                        toolkit=toolkit,
                        fecha_revision=fecha,
                        linea=linea_num,
                    )
                    ultima_revision = revision

                    for gop in gops:
                        gop_id_str = str(gop.id)
                        gop_data = ld.get('gops', {}).get(gop_id_str, {})
                        completo = gop_data.get('completo', False)
                        comentario = gop_data.get('comentario', '')

                        gr = Gop_revision.objects.create(
                            gop=gop,
                            revision=revision,
                            comentario=comentario,
                            completo=completo,
                        )

                        if not completo:
                            incompletos.append(gop.numero)

                        temp_path = gop_data.get('archivo_temp')
                        if temp_path and os.path.exists(temp_path):
                            with open(temp_path, 'rb') as f:
                                Evidencia.objects.create(
                                    gop_revision=gr,
                                    archivo=f,
                                    nombre=gop_data.get('archivo_nombre', ''),
                                )
                            os.remove(temp_path)

                incompletos = list(dict.fromkeys(incompletos))

                request.session.pop(session_key, None)
                request.session.modified = True
                request.session.save()

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
                return redirect('consultar_revision', pk=pk, revision_id=ultima_revision.id)
            else:
                return redirect(reverse('realizar_revision', kwargs={'pk': pk}) + f'?linea={linea_actual + 1}')

        else:
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

    linea_actual = 1
    lineas_data = {}
    fecha_hoy = timezone.now().date().isoformat()

    if toolkit.por_lineas:
        linea_actual = int(request.GET.get('linea', 1))
        if session_key in request.session:
            session_data = request.session[session_key]
            lineas_data = session_data.get('lineas_data', {})
            fecha_hoy = session_data.get('fecha', fecha_hoy)

    current_line_data = lineas_data.get(str(linea_actual), {})
    lineas_data_json = json.dumps(current_line_data, cls=DjangoJSONEncoder)

    return render(request, 'realizar_revision.html', {
        'toolkit': toolkit,
        'gops': gops,
        'lineas': [(i, f'Línea {i}') for i in range(1, 15)],
        'fecha_hoy': fecha_hoy,
        'nav_active': 'toolkits',
        'linea_actual': linea_actual,
        'lineas_data': lineas_data,
        'lineas_data_json': lineas_data_json,
        'total_lineas': 14 if toolkit.por_lineas else 1,
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