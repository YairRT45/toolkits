# Archivo para poblar/crear Toolkit y sus GOPs en Django
# Puedes ejecutarlo vía: python manage.py shell < crear_toolkit.py
# o integrarlo en una migración de datos o comando personalizado.

import os
import django

# Si se ejecuta de forma independiente:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'toolkits.settings')
django.setup()

from django.utils import timezone
from gestor.models import Toolkit, Gop

def run():
    # 1. Crear o recuperar el Toolkit principal
    toolkit_nombre = "Servos"
    toolkit, created = Toolkit.objects.get_or_create(
        nombre=toolkit_nombre,
        defaults={
            'por_lineas': True,
            'meta': 100.0,
            'fecha_ultima_modificacion': timezone.now().date()
        }
    )
    if created:
        print(f"Toolkit '{toolkit.nombre}' creado exitosamente.")
    else:
        toolkit.por_lineas = False
        toolkit.save()
        print(f"Toolkit '{toolkit.nombre}' ya existía y se actualizó.")

    # 2. Definición de los GOPs extraídos de la planilla
    gops_data = [
        {
            "numero": 1,
            "proceso": "Abnormal Operation Conditions Management",
            "pregunta": "¿Son consistentes los estándares de programación de software PLC para alarmas, ¿Enclavamientos y comunicaciones HMI aplicados a todos los sistemas basados en PLC?",
        },
        {
            "numero": 2,
            "proceso": "Abnormal Operation Conditions Management",
            "pregunta": "¿Existen procesos para revisar y abordar alarmas de PLC no definidas, fuerzas habilitadas y puentes?",
        },
        {
            "numero": 3,
            "proceso": "Abnormal Operation Conditions Management",
            "pregunta": "¿Existen procesos para revisar y abordar los equipos que no funcionan en modo automático?",
        },
        {
            "numero": 4,
            "proceso": "Automation Infrastructure",
            "pregunta": "¿Existen SWI documentados para gestionar el hardware y las funciones de C&A de la planta?",
        },
        {
            "numero": 5,
            "proceso": "Automation Infrastructure",
            "pregunta": "¿El hardware de automatización y control de bajo voltaje, incluidas las fuentes de alimentación, está aislado de los suministros eléctricos principales (MV/HV) y conectado a tierra adecuadamente?",
        },
        {
            "numero": 6,
            "proceso": "Automation Infrastructure",
            "pregunta": "¿Están los gabinetes de control, paneles, equipos montados en bastidor, cableado y terminales claramente etiquetados y coinciden con los dibujos?",
        },
        {
            "numero": 7,
            "proceso": "Automation Infrastructure",
            "pregunta": "¿Los gabinetes de control de la planta albergan los componentes de control de forma segura y ordenada, siguiendo las prácticas 5S con una gestión de cables limpia y organizada?",
        },
    ]

    # 3. Creación o actualización de GOPs
    for item in gops_data:
        gop, gop_created = Gop.objects.update_or_create(
            toolkit=toolkit,
            numero=item["numero"],
            defaults={
                "proceso": item["proceso"],
                "pregunta": item["pregunta"],
            }
        )
        estado = "creado" if gop_created else "actualizado"
        print(f"GOP {gop.numero} ({gop.proceso}): {estado}")

if __name__ == '__main__':
    run()