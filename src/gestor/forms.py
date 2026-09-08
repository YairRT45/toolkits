from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import Toolkit, Gop, Revision, Gop_revision, PlanAccion


class ToolkitForm(forms.ModelForm):
    class Meta:
        model = Toolkit
        fields = ['nombre', 'por_lineas', 'meta']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del Toolkit'}),
            'por_lineas': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'meta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '100'}),
        }
        labels = {
            'nombre': 'Nombre',
            'por_lineas': 'Revisión por líneas (14 líneas)',
            'meta': 'Meta de cumplimiento (%)',
        }


class GopForm(forms.ModelForm):
    class Meta:
        model = Gop
        fields = ['proceso', 'pregunta']
        widgets = {
            'proceso': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Proceso'}),
            'pregunta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pregunta del GOP'}),
        }


class BaseGopFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        preguntas = {}
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue
            pregunta = form.cleaned_data.get('pregunta')
            if not pregunta:
                continue
            clave = pregunta.strip().lower()
            if clave in preguntas:
                form.add_error('pregunta', 'Esta pregunta ya se repite en otro GOP del mismo Toolkit.')
            else:
                preguntas[clave] = form


GopFormSet = inlineformset_factory(
    Toolkit, Gop, form=GopForm,
    formset=BaseGopFormSet,
    extra=1, can_delete=True, min_num=1, validate_min=True,
)


class RevisionForm(forms.ModelForm):
    class Meta:
        model = Revision
        fields = ['fecha_revision', 'linea']
        widgets = {
            'fecha_revision': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'linea': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, toolkit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.toolkit = toolkit
        if toolkit and not toolkit.por_lineas:
            self.fields['linea'].widget = forms.HiddenInput()
            self.fields['linea'].initial = Revision.LINEA_GENERAL
        else:
            choices = [(i, f'Línea {i}') for i in range(1, 15)]
            choices.insert(0, (Revision.LINEA_GENERAL, 'General'))
            self.fields['linea'].widget = forms.Select(
                attrs={'class': 'form-control'},
                choices=choices,
            )


class PlanAccionForm(forms.ModelForm):
    gop_revision = forms.ModelChoiceField(
        queryset=Gop_revision.objects.none(),
        empty_label="Selecciona un GOP",
        widget=forms.Select(attrs={'class': 'form-control', }),
        label='GOP incumplido',
    )

    class Meta:
        model = PlanAccion
        fields = ['gop_revision', 'descripcion', 'responsable', 'fecha_limite']
        widgets = {
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descripción del plan de acción'}),
            'responsable': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Responsable'}),
            'fecha_limite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, revision=None, **kwargs):
        super().__init__(*args, **kwargs)
        if revision:
            self.fields['gop_revision'].queryset = revision.gops_no_cumplidos()
