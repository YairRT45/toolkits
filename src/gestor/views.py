import json
import os
import tempfile
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from .models import Toolkit, Gop, Revision, Gop_revision, Evidencia, PlanAccion
from .forms import ToolkitForm, GopFormSet, RevisionForm, PlanAccionForm
from .utils import (
    resumen_toolkit,
    calcular_cumplimiento_mensual, calcular_cumplimiento_mensual_ampliado,
    calcular_cumplimiento_mensual_global,
    gop_menor_cumplimiento, contar_gops_no_cumplidos, gops_no_cumplidos_por_revision,
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
            if formset.non_form_errors():
                messages.error(request, 'Debe incluir al menos un GOP.')
            else:
                messages.error(request, 'Revise los errores en los GOPs.')
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
    ultima_revision = ultima_revision = toolkit.revisiones.order_by('-fecha_revision', '-id').first()
    gops = toolkit.gops.all()
    return render(request, 'detalle_toolkit.html', {
        'toolkit': toolkit,
        'revision': ultima_revision,
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
            if formset.non_form_errors():
                messages.error(request, 'Debe incluir al menos un GOP.')
            else:
                messages.error(request, 'Revise los errores en los GOPs.')
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


def _agrupar_revisiones_por_fecha(toolkit):
    revisiones = toolkit.revisiones.all().order_by('-fecha_revision', 'linea')
    grupos = {}
    for rev in revisiones:
        grupos.setdefault(rev.fecha_revision, []).append(rev)
    fechas = []
    for fecha in sorted(grupos.keys(), reverse=True):
        lineas = sorted(grupos[fecha], key=lambda r: r.linea)
        fechas.append({
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'es_por_lineas': toolkit.por_lineas,
            'lineas': lineas,
        })
    return fechas


def listar_revisiones(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    
    if toolkit.por_lineas:
        from django.db.models import Avg
        revisiones_raw = toolkit.revisiones.all()
        
        fechas_agrupadas = {}
        for rev in revisiones_raw:
            fecha_key = rev.fecha_revision
            if fecha_key not in fechas_agrupadas:
                fechas_agrupadas[fecha_key] = {
                    'fecha': fecha_key,
                    'lineas': [],
                    'primer_id': rev.id,
                }
            fechas_agrupadas[fecha_key]['lineas'].append(rev)
        
        revisiones_agrupadas = []
        for fecha_key in sorted(fechas_agrupadas.keys(), reverse=True):
            grupo = fechas_agrupadas[fecha_key]
            lineas = grupo['lineas']
            
            total_gops = 0
            total_cumplidos = 0
            total_incompletos = 0
            
            for rev in lineas:
                total_gops += rev.gop_revision_set.count()
                total_cumplidos += rev.gops_cumplidos_count()
                total_incompletos += rev.gops_no_cumplidos().count()
            
            promedio_cumplimiento = round((total_cumplidos / total_gops * 100), 1) if total_gops > 0 else 0
            
            revisiones_agrupadas.append({
                'fecha': grupo['fecha'],
                'lineas': sorted(lineas, key=lambda x: x.linea),
                'promedio_cumplimiento': promedio_cumplimiento,
                'total_incompletos': total_incompletos,
                'primer_id': grupo['primer_id'],
                'es_agrupada': True,
            })
    else:
        revisiones_agrupadas = []
        revisiones = toolkit.revisiones.filter(linea=Revision.LINEA_GENERAL)
        for rev in revisiones:
            revisiones_agrupadas.append({
                'fecha': rev.fecha_revision,
                'revision': rev,
                'es_agrupada': False,
            })
    
    return render(request, 'listar_revisiones.html', {
        'toolkit': toolkit,
        'revisiones': revisiones_agrupadas,
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

    fechas = _agrupar_revisiones_por_fecha(toolkit)

    return render(request, 'consultar_revision.html', {
        'toolkit': toolkit,
        'revision': revision,
        'gop_revisiones': gop_revisiones,
        'fechas': fechas,
        'es_global': False,
        'nav_active': 'toolkits',
    })


def consultar_revision_global(request, pk, fecha):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    try:
        fecha_date = date.fromisoformat(fecha)
    except ValueError:
        messages.error(request, 'Fecha inválida.')
        return redirect('listar_revisiones', pk=pk)

    revisiones = toolkit.revisiones.filter(fecha_revision=fecha_date)
    if not revisiones.exists():
        messages.warning(request, 'No hay revisiones registradas para esa fecha.')
        return redirect('listar_revisiones', pk=pk)

    total_gops = sum(rev.gop_revision_set.count() for rev in revisiones)
    total_cumplidos = sum(rev.gops_cumplidos_count() for rev in revisiones)
    promedio = round(total_cumplidos / total_gops * 100, 1) if total_gops else 0
    total_incompletos = total_gops - total_cumplidos
    cantidad_lineas = revisiones.count()

    gops_consolidados = []
    for gop in toolkit.gops.all():
        completadas = Gop_revision.objects.filter(
            revision__in=revisiones, gop=gop, completo=True
        ).count()
        gops_consolidados.append({
            'gop': gop,
            'completadas': completadas,
            'total_lineas': cantidad_lineas,
            'porcentaje': round(completadas / cantidad_lineas * 100, 1) if cantidad_lineas else 0,
        })

    fechas = _agrupar_revisiones_por_fecha(toolkit)

    return render(request, 'consultar_revision.html', {
        'toolkit': toolkit,
        'revision': None,
        'gop_revisiones': None,
        'fechas': fechas,
        'es_global': True,
        'fecha_global': fecha,
        'fecha_display': fecha_date,
        'promedio_global': promedio,
        'total_incompletos': total_incompletos,
        'cantidad_lineas': cantidad_lineas,
        'gops_consolidados': gops_consolidados,
        'meta': toolkit.meta,
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

    chart_linea = revision.linea if (toolkit.por_lineas and revision.linea != Revision.LINEA_GENERAL) else None
    chart_data = calcular_cumplimiento_mensual(toolkit, linea=chart_linea)
    gop_info = gop_menor_cumplimiento(toolkit)
    planes_abiertos = PlanAccion.objects.filter(
        gop_revision__revision__toolkit=toolkit,
        completado=False,
    ).count()

    fechas = _agrupar_revisiones_por_fecha(toolkit)

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


def desglose_revision_global(request, pk, fecha):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    try:
        fecha_date = date.fromisoformat(fecha)
    except ValueError:
        messages.error(request, 'Fecha inválida.')
        return redirect('listar_revisiones', pk=pk)

    revisiones = toolkit.revisiones.filter(fecha_revision=fecha_date)
    if not revisiones.exists():
        messages.warning(request, 'No hay revisiones registradas para esa fecha.')
        return redirect('listar_revisiones', pk=pk)

    total_gops = sum(rev.gop_revision_set.count() for rev in revisiones)
    total_cumplidos = sum(rev.gops_cumplidos_count() for rev in revisiones)
    promedio = round(total_cumplidos / total_gops * 100, 1) if total_gops else 0
    total_incompletos = total_gops - total_cumplidos
    cantidad_lineas = revisiones.count()

    gops_consolidados = []
    for gop in toolkit.gops.all():
        completadas = Gop_revision.objects.filter(
            revision__in=revisiones, gop=gop, completo=True
        ).count()
        gops_consolidados.append({
            'gop': gop,
            'completadas': completadas,
            'total_lineas': cantidad_lineas,
            'porcentaje': round(completadas / cantidad_lineas * 100, 1) if cantidad_lineas else 0,
        })
    gops_consolidados.sort(key=lambda x: x['porcentaje'])
    gop_menor_global = gops_consolidados[0] if gops_consolidados else None

    planes_abiertos = PlanAccion.objects.filter(
        gop_revision__revision__in=revisiones,
        completado=False,
    ).count()

    chart_data = calcular_cumplimiento_mensual_global(toolkit)
    fechas = _agrupar_revisiones_por_fecha(toolkit)

    return render(request, 'desglose_revision.html', {
        'toolkit': toolkit,
        'revision': None,
        'es_global': True,
        'fecha_global': fecha,
        'fecha_display': fecha_date,
        'porcentaje': promedio,
        'meta': toolkit.meta,
        'gops_no_cumplidos': total_incompletos,
        'gop_menor': gop_menor_global['gop'] if gop_menor_global else None,
        'gop_menor_pct': gop_menor_global['porcentaje'] if gop_menor_global else 0,
        'planes_abiertos': planes_abiertos,
        'chart_data': json.dumps(chart_data),
        'fechas': fechas,
        'gops_consolidados': gops_consolidados,
        'cantidad_lineas': cantidad_lineas,
        'nav_active': 'toolkits',
    })


def ampliar_grafica(request, pk):
    toolkit = get_object_or_404(Toolkit, pk=pk)
    linea_q = request.GET.get('linea')
    linea = int(linea_q) if linea_q is not None and linea_q != '' else None
    chart_data = calcular_cumplimiento_mensual_ampliado(toolkit, meses=12, linea=linea)
    return render(request, 'ampliar_grafica.html', {
        'toolkit': toolkit,
        'chart_data': json.dumps(chart_data),
        'linea': linea,
        'nav_active': 'toolkits',
    })


def gops_no_cumplidos(request, toolkit_id=None, revision_id=None):
    resultados = gops_no_cumplidos_por_revision(toolkit_id, revision_id)
    toolkits = Toolkit.objects.all()
    toolkit_seleccionado = None
    if toolkit_id:
        toolkit_seleccionado = Toolkit.objects.filter(pk=toolkit_id).first()
    return render(request, 'gops_no_cumplidos.html', {
        'resultados': resultados,
        'toolkits': toolkits,
        'toolkit_seleccionado': toolkit_seleccionado,
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