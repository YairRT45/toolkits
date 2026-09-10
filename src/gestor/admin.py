from django.contrib import admin
from .models import Toolkit, Gop, Revision, Gop_revision, Evidencia, PlanAccion, Dueno

admin.site.register(Toolkit)
admin.site.register(Gop)
admin.site.register(Revision)
admin.site.register(Gop_revision)
admin.site.register(Evidencia)
admin.site.register(PlanAccion)
admin.site.register(Dueno)