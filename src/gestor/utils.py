from datetime import timedelta
from django.utils import timezone

from .models import Revision


def calcular_cumplimiento_mensual(toolkit, meses=6):
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
            linea=Revision.LINEA_GENERAL,
        )
        if revisiones.exists():
            porcentajes = [r.porcentaje_cumplimiento() for r in revisiones]
            promedio = round(sum(porcentajes) / len(porcentajes), 1)
        else:
            promedio = None

        label = inicio.strftime('%b %Y')
        datos.append({'label': label, 'porcentaje': promedio})
    return datos


def calcular_cumplimiento_mensual_ampliado(toolkit, meses=12):
    return calcular_cumplimiento_mensual(toolkit, meses)


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
    revision = toolkit.ultima_revision
    gop_info = gop_menor_cumplimiento(toolkit)
    return {
        'toolkit': toolkit,
        'porcentaje': revision.porcentaje_cumplimiento() if revision else None,
        'meta': toolkit.meta,
        'gops_no_cumplidos': contar_gops_no_cumplidos(toolkit),
        'gop_menor': gop_info[0],
        'gop_menor_pct': gop_info[1],
        'chart_data': calcular_cumplimiento_por_revision(toolkit),
    }

def calcular_cumplimiento_por_revision(toolkit, limite=10):
    """Obtiene las últimas N revisiones individuales ordenadas cronológicamente."""
    # Obtenemos las últimas revisiones en orden descendente (las más recientes)
    # Reemplaza 'revisiones' por el related_name correspondiente si es distinto
    # Reemplaza 'fecha' por el nombre exacto de tu campo de fecha/hora
    ultimas_revisiones = list(
        toolkit.revisiones.order_by('-fecha_revision')[:limite]
    )

    # Las invertimos para que en la gráfica aparezcan de izquierda a derecha en el tiempo
    ultimas_revisiones.reverse()

    return [
        {
            'label': rev.fecha_revision.strftime('%d/%m/%Y'),
            'porcentaje': rev.porcentaje_cumplimiento()
        }
        for rev in ultimas_revisiones
    ]