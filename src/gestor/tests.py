from django.test import TestCase

from .models import Toolkit
from .forms import GopFormSet


class GopFormSetValidationTests(TestCase):
    def setUp(self):
        self.toolkit = Toolkit.objects.create(
            nombre='Toolkit A',
            meta=100,
            por_lineas=False,
        )

    def test_preguntas_duplicadas_rechazadas(self):
        data = {
            'gops-TOTAL_FORMS': '3',
            'gops-INITIAL_FORMS': '0',
            'gops-MIN_NUM_FORMS': '0',
            'gops-MAX_NUM_FORMS': '1000',
            'gops-0-proceso': 'Proceso 1',
            'gops-0-pregunta': '¿Se cumple la norma X?',
            'gops-1-proceso': 'Proceso 2',
            'gops-1-pregunta': '¿Se cumple la norma X?',
            'gops-2-proceso': 'Proceso 3',
            'gops-2-pregunta': '¿Existe evidencia del registro?',
        }
        formset = GopFormSet(data=data, instance=self.toolkit)
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('pregunta' in f.errors for f in formset.forms))

    def test_preguntas_duplicadas_ignoran_mayusculas(self):
        data = {
            'gops-TOTAL_FORMS': '2',
            'gops-INITIAL_FORMS': '0',
            'gops-MIN_NUM_FORMS': '0',
            'gops-MAX_NUM_FORMS': '1000',
            'gops-0-proceso': 'Proceso 1',
            'gops-0-pregunta': '¿Se cumple la norma X?',
            'gops-1-proceso': 'Proceso 2',
            'gops-1-pregunta': '¿SE CUMPLE LA NORMA X?',
        }
        formset = GopFormSet(data=data, instance=self.toolkit)
        self.assertFalse(formset.is_valid())

    def test_misma_pregunta_en_distintos_toolkits(self):
        otro_toolkit = Toolkit.objects.create(nombre='Toolkit B')
        data = {
            'gops-TOTAL_FORMS': '1',
            'gops-INITIAL_FORMS': '0',
            'gops-MIN_NUM_FORMS': '0',
            'gops-MAX_NUM_FORMS': '1000',
            'gops-0-proceso': 'Proceso 1',
            'gops-0-pregunta': '¿Se cumple la norma X?',
        }
        formset = GopFormSet(data=data, instance=otro_toolkit)
        self.assertTrue(formset.is_valid())