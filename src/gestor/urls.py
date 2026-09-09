from django.urls import path
from . import views

urlpatterns = [
    path('', views.listar_toolkits, name='listar_toolkits'),
    path('crear/', views.crear_toolkit, name='crear_toolkit'),
    path('resumen/', views.resumen, name='resumen'),
    path('gops-no-cumplidos/', views.gops_no_cumplidos, name='gops_no_cumplidos'),
    path('gops-no-cumplidos/<int:toolkit_id>/', views.gops_no_cumplidos, name='gops_no_cumplidos_toolkit'),
    path('gops-no-cumplidos/<int:toolkit_id>/<int:revision_id>/', views.gops_no_cumplidos, name='gops_no_cumplidos_revision'),
    path('planes-accion/', views.listar_planes_accion, name='listar_planes_accion_global'),

    path('<int:pk>/', views.detalle_toolkit, name='detalle_toolkit'),
    path('<int:pk>/editar/', views.editar_toolkit, name='editar_toolkit'),
    path('<int:pk>/eliminar/', views.eliminar_toolkit, name='eliminar_toolkit'),
    path('<int:pk>/revisiones/', views.listar_revisiones, name='listar_revisiones'),
    path('<int:pk>/revision/nueva/', views.realizar_revision, name='realizar_revision'),
    path('<int:pk>/revision/<int:revision_id>/', views.consultar_revision, name='consultar_revision'),
    path('<int:pk>/desglose/', views.desglose_revision, name='desglose_revision'),
    path('<int:pk>/desglose/<int:revision_id>/', views.desglose_revision, name='desglose_revision_fecha'),
    path('<int:pk>/grafica/', views.ampliar_grafica, name='ampliar_grafica'),
    path('<int:pk>/planes-accion/', views.listar_planes_accion, name='listar_planes_accion'),
    path('<int:pk>/revision/<int:revision_id>/plan-accion/', views.crear_plan_accion, name='crear_plan_accion'),
]
