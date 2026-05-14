from django import forms
from .models import (Marca, TipoEquipo, TipoPeriferico, TipoComponente, ModeloComponente,
                     Institucion, Sede, Grupo, Subgrupo, Rol, Persona, Perfil, Modulo, Software,
                     Equipo, Componente, Periferico, InstalacionSoftware, Dispositivo,
                     ViaReporte, TipoRequerimiento, Estado, Prioridad, GrupoProgramas,
                     Requerimiento)


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
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoComponenteForm(forms.ModelForm):
    class Meta:
        model = TipoComponente
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ModeloComponenteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].queryset = TipoComponente.objects.filter(activo=True)
        self.fields['marca'].queryset = Marca.objects.filter(activo=True)

    class Meta:
        model = ModeloComponente
        fields = ['tipo', 'nombre', 'capacidad', 'marca', 'activo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True,
                                            'placeholder': 'Ej: Intel Core i5-10400'}),
            'capacidad': forms.TextInput(attrs={'class': 'form-control',
                                               'placeholder': 'Ej: 8 GB, 3.6 GHz'}),
            'marca': forms.Select(attrs={'class': 'form-select'}),
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['institucion'].queryset = Institucion.objects.filter(activo=True)

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sede'].queryset = Sede.objects.select_related('institucion').filter(activo=True)

    class Meta:
        model = Grupo
        fields = ['nombre', 'sede', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'sede': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubgrupoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grupo'].queryset = Grupo.objects.select_related('sede').filter(activo=True)

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
        fields = ['nombre', 'descripcion', 'es_admin']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'es_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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


class GrupoProgramasForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['programas'].queryset = Software.objects.filter(activo=True).order_by('nombre')

    class Meta:
        model = GrupoProgramas
        fields = ['nombre', 'descripcion', 'programas', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'programas': forms.CheckboxSelectMultiple(),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ── INVENTARIO ────────────────────────────────────────────────────────────────

class EquipoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grupo'].queryset = Grupo.objects.select_related('sede').filter(activo=True)
        self.fields['grupo_programas'].queryset = GrupoProgramas.objects.filter(activo=True).order_by('nombre')
        grupo_id = self.data.get('grupo') or (
            self.instance.subgrupo.grupo_id if self.instance.pk and self.instance.subgrupo_id else None
        )
        if grupo_id:
            self.fields['subgrupo'].queryset = Subgrupo.objects.filter(grupo_id=grupo_id, activo=True)
        else:
            self.fields['subgrupo'].queryset = Subgrupo.objects.none()

    class Meta:
        model = Equipo
        fields = ['codigo', 'tipo', 'grupo', 'subgrupo', 'grupo_programas', 'ip', 'observaciones', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'grupo': forms.Select(attrs={
                'class': 'form-select',
                '@change': 'onGrupoChange($event.target.value)',
            }),
            'subgrupo': forms.Select(attrs={'class': 'form-select'}),
            'grupo_programas': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_grupo_programas',
            }),
            'ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 192.168.1.100'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DispositivoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subgrupo'].queryset = Subgrupo.objects.select_related('grupo__sede').filter(activo=True)
        self.fields['tipo'].queryset = TipoPeriferico.objects.filter(activo=True).order_by('nombre')
        self.fields['marca'].queryset = Marca.objects.filter(activo=True).order_by('nombre')

    class Meta:
        model = Dispositivo
        fields = ['subgrupo', 'tipo', 'marca', 'ip', 'extension', 'activo', 'observaciones']
        widgets = {
            'subgrupo': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.Select(attrs={'class': 'form-select'}),
            'ip': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 192.168.1.100'}),
            'extension': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 104'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ComponenteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modelo'].queryset = ModeloComponente.objects.select_related('tipo').filter(activo=True)

    class Meta:
        model = Componente
        fields = ['modelo', 'activo']
        widgets = {
            'modelo': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PerifericoForm(forms.ModelForm):
    class Meta:
        model = Periferico
        fields = ['tipo', 'marca', 'activo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InstalacionSoftwareForm(forms.ModelForm):
    class Meta:
        model = InstalacionSoftware
        fields = ['software', 'version', 'fecha_instalacion', 'fecha_vencimiento', 'observaciones']
        widgets = {
            'software': forms.Select(attrs={'class': 'form-select'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_instalacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ── SOPORTE ───────────────────────────────────────────────────────────────────

class ViaReporteForm(forms.ModelForm):
    class Meta:
        model = ViaReporte
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoRequerimientoForm(forms.ModelForm):
    class Meta:
        model = TipoRequerimiento
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EstadoForm(forms.ModelForm):
    class Meta:
        model = Estado
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PrioridadForm(forms.ModelForm):
    class Meta:
        model = Prioridad
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RequerimientoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_requerimiento'].queryset = TipoRequerimiento.objects.filter(activo=True)
        self.fields['estado'].queryset = Estado.objects.filter(activo=True)
        self.fields['prioridad'].queryset = Prioridad.objects.filter(activo=True)
        self.fields['via_reporte'].queryset = ViaReporte.objects.filter(activo=True)
        self.fields['tecnico'].queryset = Persona.objects.only('id', 'nombre', 'apellido1', 'apellido2').filter(activo=True)
        self.fields['area'].queryset = Grupo.objects.select_related('sede').filter(activo=True)
        area_id = self.data.get('area') or (self.instance.area_id if self.instance.pk else None)
        if area_id:
            self.fields['departamento'].queryset = Subgrupo.objects.filter(
                grupo_id=area_id, activo=True
            )
        else:
            self.fields['departamento'].queryset = Subgrupo.objects.none()

    class Meta:
        model = Requerimiento
        fields = [
            'fecha_reporte', 'persona_reporto', 'tipo_requerimiento', 'via_reporte',
            'descripcion', 'estado', 'prioridad', 'area', 'departamento',
            'tecnico', 'fecha_solucion', 'accion', 'observaciones', 'evidencia',
        ]
        widgets = {
            'fecha_reporte': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'persona_reporto': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_requerimiento': forms.Select(attrs={'class': 'form-select'}),
            'via_reporte': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'tecnico': forms.Select(attrs={'class': 'form-select'}),
            'fecha_solucion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'accion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'evidencia': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
