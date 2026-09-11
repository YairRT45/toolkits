from django.db import models
from django.utils import timezone

class Dueno(models.Model):
    nombre = models.CharField(max_length=50)
    apellido_p = models.CharField(max_length=50)
    apellido_m = models.CharField(max_length=50)
    foto = models.ImageField(upload_to='fotos/')

    def __str__(self):
        return f"{self.nombre} {self.apellido_p}"


class Toolkit(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    por_lineas = models.BooleanField(default=False)
    meta = models.DecimalField(max_digits=5, decimal_places=1, default=100.00)
    fecha_ultima_modificacion = models.DateField(default=timezone.now)
    dueno = models.ForeignKey(
        Dueno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='toolkits'
    )

    def __str__(self):
        return self.nombre

    @property
    def ultima_revision(self):
        return self.revisiones.order_by('-fecha_revision', '-id').first()

    def porcentaje_actual(self):
        if not self.revisiones.exists():
            return None
        if self.por_lineas:
            ultima_fecha = self.revisiones.order_by('-fecha_revision', '-id').first().fecha_revision
            revs = self.revisiones.filter(fecha_revision=ultima_fecha)
            total = sum(r.gop_revision_set.count() for r in revs)
            cumplidos = sum(r.gops_cumplidos_count() for r in revs)
            return round(cumplidos / total * 100, 1) if total else 0
        revision = self.ultima_revision
        if not revision:
            return None
        return revision.porcentaje_cumplimiento()


class Gop(models.Model):
    numero = models.PositiveIntegerField()
    proceso = models.CharField(max_length=255)
    pregunta = models.CharField(max_length=255)
    toolkit = models.ForeignKey(Toolkit, on_delete=models.CASCADE, related_name='gops')

    class Meta:
        unique_together = [['toolkit', 'numero']]
        ordering = ['numero']

    def __str__(self):
        return f"GOP {self.numero}: {self.pregunta}"


class Revision(models.Model):
    LINEA_GENERAL = 0

    toolkit = models.ForeignKey(Toolkit, on_delete=models.CASCADE, related_name='revisiones')
    fecha_revision = models.DateField(default=timezone.now)
    linea = models.IntegerField(default=LINEA_GENERAL)

    class Meta:
        unique_together = [['toolkit', 'fecha_revision', 'linea']]
        ordering = ['-fecha_revision', '-id']

    def __str__(self):
        if self.linea == self.LINEA_GENERAL:
            return f"Revisión {self.fecha_revision} (General)"
        return f"Revisión {self.fecha_revision} (Línea {self.linea})"

    def porcentaje_cumplimiento(self):
        total = self.gop_revision_set.count()
        if total == 0:
            return 0
        completos = self.gop_revision_set.filter(completo=True).count()
        return round((completos / total) * 100, 1)

    def gops_no_cumplidos(self):
        return self.gop_revision_set.filter(completo=False)

    def gops_cumplidos_count(self):
        return self.gop_revision_set.filter(completo=True).count()


class Gop_revision(models.Model):
    gop = models.ForeignKey(Gop, on_delete=models.CASCADE)
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name='gop_revision_set')
    comentario = models.CharField(max_length=500, blank=True, default='')
    completo = models.BooleanField(default=False)

    class Meta:
        unique_together = [['gop', 'revision']]

    def __str__(self):
        estado = 'Completo' if self.completo else 'Incompleto'
        return f"{self.gop} - {estado}"


class Evidencia(models.Model):
    gop_revision = models.ForeignKey(Gop_revision, on_delete=models.CASCADE, related_name='evidencias')
    archivo = models.FileField(upload_to='evidencias/')
    nombre = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.nombre or self.archivo.name


class PlanAccion(models.Model):
    gop_revision = models.ForeignKey(Gop_revision, on_delete=models.CASCADE, related_name='planes_accion')
    descripcion = models.TextField()
    responsable = models.CharField(max_length=255)
    fecha_limite = models.DateField()
    completado = models.BooleanField(default=False)
    fecha_creacion = models.DateField(auto_now_add=True)
    linea = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        if self.linea:
            return f"Plan: {self.gop_revision.gop.pregunta[:50]} (Línea {self.linea})"
        return f"Plan: {self.gop_revision.gop.pregunta[:50]}"
