from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Revision


def calcular_cumplimiento_mensual(toolkit, meses=6, linea=None):
    """Retorna lista de {label, porcentaje} para los últimos N meses."""
    hoy = timezone.now().date()
    datos = []
    for i in range(meses - 1, -1, -1):
        inicio = (hoy.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if inicio.month == 12:
            fin = inicio.replace(year=inicio.year + 1, month=1, day=1)
        else:
            fin = inicio.replace(month=inicio.month + 1, day=1)

        revisiones = toolkit.revisiones.filter(
            fecha_revision__gte=inicio,
            fecha_revision__lt=fin,
        )
        if linea is not None:
            revisiones = revisiones.filter(linea=linea)
        else:
            revisiones = revisiones.filter(linea=Revision.LINEA_GENERAL)

        if revisiones.exists():
            porcentajes = [r.porcentaje_cumplimiento() for r in revisiones]
            promedio = round(sum(porcentajes) / len(porcentajes), 1)
        else:
            promedio = None

        label = inicio.strftime('%b %Y')
        datos.append({'label': label, 'porcentaje': promedio})
    return datos


def calcular_cumplimiento_mensual_global(toolkit, meses=6):
    """Promedio mensual considerando todas las líneas de cada fecha."""
    hoy = timezone.now().date()
    datos = []
    for i in range(meses - 1, -1, -1):
        inicio = (hoy.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if inicio.month == 12:
            fin = inicio.replace(year=inicio.year + 1, month=1, day=1)
        else:
            fin = inicio.replace(month=inicio.month + 1, day=1)

        revisiones = toolkit.revisiones.filter(
            fecha_revision__gte=inicio,
            fecha_revision__lt=fin,
        )
        if revisiones.exists():
            por_fecha = {}
            for rev in revisiones:
                por_fecha.setdefault(rev.fecha_revision, {'total': 0, 'cumplidos': 0})
                por_fecha[rev.fecha_revision]['total'] += rev.gop_revision_set.count()
                por_fecha[rev.fecha_revision]['cumplidos'] += rev.gops_cumplidos_count()
            pct_fechas = [
                round(v['cumplidos'] / v['total'] * 100, 1) if v['total'] else 0
                for v in por_fecha.values()
            ]
            promedio = round(sum(pct_fechas) / len(pct_fechas), 1)
        else:
            promedio = None

        label = inicio.strftime('%b %Y')
        datos.append({'label': label, 'porcentaje': promedio})
    return datos


def calcular_cumplimiento_mensual_ampliado(toolkit, meses=12, linea=None):
    return calcular_cumplimiento_mensual(toolkit, meses, linea=linea)


def gop_menor_cumplimiento(toolkit):
    """GOP con menor tasa de cumplimiento histórico."""
    gops = toolkit.gops.all()
    if not gops.exists():
        return None

    peor = None
    peor_pct = 101
    for gop in gops:
        total = gop.gop_revision_set.count()
        if total == 0:
            continue
        cumplidos = gop.gop_revision_set.filter(completo=True).count()
        pct = (cumplidos / total) * 100
        if pct < peor_pct:
            peor_pct = pct
            peor = gop
    return peor, round(peor_pct, 1) if peor else (None, None)


def contar_gops_no_cumplidos(toolkit):
    """Cuenta GOPs no cumplidos en la última revisión."""
    revision = toolkit.ultima_revision
    if not revision:
        return 0
    return revision.gops_no_cumplidos().count()


def todos_gops_no_cumplidos():
    """Lista todos los GOPs no cumplidos de la última revisión de cada toolkit."""
    from .models import Gop_revision, Toolkit
    resultados = []
    for toolkit in Toolkit.objects.all():
        revision = toolkit.ultima_revision
        if revision:
            for gr in revision.gops_no_cumplidos().select_related('gop'):
                resultados.append({
                    'toolkit': toolkit,
                    'gop': gr.gop,
                    'revision': revision,
                    'comentario': gr.comentario,
                    'gop_revision': gr,
                })
    return resultados


def resumen_toolkit(toolkit):
    """Datos de resumen para un toolkit."""
    gop_info = gop_menor_cumplimiento(toolkit)

    promedio = None
    gops_pendientes = 0
    ultimas_revisiones = toolkit.revisiones.order_by('-fecha_revision')
    if ultimas_revisiones.exists():
        fecha_ultima = ultimas_revisiones.first().fecha_revision
        revs = toolkit.revisiones.filter(fecha_revision=fecha_ultima)
        total = sum(r.gop_revision_set.count() for r in revs)
        cumplidos = sum(r.gops_cumplidos_count() for r in revs)
        promedio = round(cumplidos / total * 100, 1) if total else 0
        gops_pendientes = total - cumplidos

    return {
        'toolkit': toolkit,
        'porcentaje': promedio,
        'meta': toolkit.meta,
        'gops_no_cumplidos': gops_pendientes,
        'gop_menor': gop_info[0],
        'gop_menor_pct': gop_info[1],
        'chart_data': calcular_cumplimiento_promedio_por_fecha(toolkit),
    }

def calcular_cumplimiento_por_revision(toolkit, limite=10):
    """Obtiene las últimas N revisiones individuales ordenadas cronológicamente."""
    ultimas_revisiones = list(
        toolkit.revisiones.order_by('-fecha_revision')[:limite]
    )
    ultimas_revisiones.reverse()

    return [
        {
            'label': rev.fecha_revision.strftime('%d/%m/%Y'),
            'porcentaje': rev.porcentaje_cumplimiento()
        }
        for rev in ultimas_revisiones
    ]


def calcular_cumplimiento_promedio_por_fecha(toolkit, limite=10):
    """Promedio por fecha consolidando todas las líneas de cada fecha."""
    revisiones = toolkit.revisiones.order_by('-fecha_revision')
    por_fecha = {}
    for rev in revisiones:
        por_fecha.setdefault(rev.fecha_revision, {'total': 0, 'cumplidos': 0})
        por_fecha[rev.fecha_revision]['total'] += rev.gop_revision_set.count()
        por_fecha[rev.fecha_revision]['cumplidos'] += rev.gops_cumplidos_count()

    fechas = sorted(por_fecha.keys(), reverse=True)[:limite]
    fechas.reverse()

    return [
        {
            'label': f.strftime('%d/%m/%Y'),
            'porcentaje': round(por_fecha[f]['cumplidos'] / por_fecha[f]['total'] * 100, 1) if por_fecha[f]['total'] else 0,
        }
        for f in fechas
    ]


def gops_no_cumplidos_por_revision(toolkit_id=None, revision_id=None):
    """Obtiene GOps no cumplidos filtrados por toolkit y/o revisión específica."""
    from .models import Toolkit, Revision

    if revision_id:
        revision = get_object_or_404(Revision, pk=revision_id)
        toolkit = revision.toolkit
        return [{
            'toolkit': toolkit,
            'revision': revision,
            'gops': list(revision.gops_no_cumplidos().select_related('gop')),
        }]

    if toolkit_id:
        toolkit = get_object_or_404(Toolkit, pk=toolkit_id)
        revision = toolkit.ultima_revision
        if not revision:
            return []
        return [{
            'toolkit': toolkit,
            'revision': revision,
            'gops': list(revision.gops_no_cumplidos().select_related('gop')),
        }]

    resultados = []
    for toolkit in Toolkit.objects.all():
        revision = toolkit.ultima_revision
        if revision:
            gops = list(revision.gops_no_cumplidos().select_related('gop'))
            if gops:
                resultados.append({
                    'toolkit': toolkit,
                    'revision': revision,
                    'gops': gops,
                })
    return resultados