from django import forms
from .models import (Marca, TipoEquipo, TipoPeriferico, TipoComponente,
                     Institucion, Sede, Grupo, Subgrupo, Rol, Persona, Perfil, Modulo, Software)


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoEquipoForm(forms.ModelForm):
    class Meta:
        model = TipoEquipo
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoPerifericoForm(forms.ModelForm):
    class Meta:
        model = TipoPeriferico
        fields = ['nombre', 'codigo', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoComponenteForm(forms.ModelForm):
    class Meta:
        model = TipoComponente
        fields = ['nombre', 'codigo', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InstitucionForm(forms.ModelForm):
    class Meta:
        model = Institucion
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        fields = ['nombre', 'institucion', 'direccion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['nombre', 'sede', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'sede': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubgrupoForm(forms.ModelForm):
    class Meta:
        model = Subgrupo
        fields = ['nombre', 'grupo', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre', 'apellido1', 'apellido2', 'institucion', 'sedes', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'apellido1': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido2': forms.TextInput(attrs={'class': 'form-control'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'sedes': forms.CheckboxSelectMultiple(),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['persona', 'rol', 'activo']
        widgets = {
            'persona': forms.Select(attrs={'class': 'form-select'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ['nombre', 'descripcion', 'url_name', 'icono', 'orden', 'activo', 'roles']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'url_name': forms.TextInput(attrs={'class': 'form-control'}),
            'icono': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'roles': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        }


class SoftwareForm(forms.ModelForm):
    class Meta:
        model = Software
        fields = ['nombre', 'fabricante', 'requiere_licencia', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'fabricante': forms.TextInput(attrs={'class': 'form-control'}),
            'requiere_licencia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
