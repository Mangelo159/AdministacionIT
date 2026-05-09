from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.db.models import Prefetch
from django.urls import reverse_lazy, reverse, NoReverseMatch
from django.views.decorators.http import require_POST
import json
from datetime import date
from django.db.models import Q, ProtectedError, Case, When, Value, F, IntegerField

from .models import (Marca, TipoEquipo, TipoPeriferico, TipoComponente, ModeloComponente,
                     Modulo, Perfil, Institucion, Sede, Grupo, Subgrupo, Rol, Persona, Software,
                     Equipo, Componente, Periferico, InstalacionSoftware,
                     sedes_permitidas)
from .forms import (MarcaForm, TipoEquipoForm, TipoPerifericoForm, TipoComponenteForm,
                    ModeloComponenteForm,
                    InstitucionForm, SedeForm, GrupoForm, SubgrupoForm,
                    RolForm, PersonaForm, PerfilForm, ModuloForm, SoftwareForm,
                    EquipoForm, ComponenteForm, PerifericoForm, InstalacionSoftwareForm)


def _sedes_ids(user):
    """None = sin filtro (superusuario/staff). Lista vacía o de IDs = usuario normal."""
    if user.is_superuser or user.is_staff:
        return None
    if hasattr(user, 'persona'):
        return list(user.persona.sedes.values_list('id', flat=True))
    return []


@login_required
def mantenimientos(request):
    return render(request, 'inv/mantenimientos/index.html')


@login_required
def inventario(request):
    return redirect('inv:equipo_lista')


@login_required
def home(request):
    if request.user.is_superuser:
        modulos = list(Modulo.objects.filter(activo=True).order_by('orden', 'nombre'))
    elif hasattr(request.user, 'persona'):
        roles_ids = Perfil.objects.filter(
            persona=request.user.persona, activo=True
        ).values_list('rol_id', flat=True)
        modulos = list(
            Modulo.objects.filter(activo=True, roles__in=roles_ids)
            .distinct()
            .order_by('orden', 'nombre')
        )
    else:
        modulos = []

    for m in modulos:
        try:
            m.url_resuelta = reverse(m.url_name)
        except NoReverseMatch:
            m.url_resuelta = '#'

    return render(request, 'inv/home.html', {'modulos': modulos})


# ── Mixins base ───────────────────────────────────────────────────────────────

class _CatalogoList(LoginRequiredMixin, ListView):
    context_object_name = 'objetos'
    template_name = 'inv/catalogos/catalogo_lista.html'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class _CatalogoForm(LoginRequiredMixin):
    template_name = 'inv/catalogos/catalogo_form.html'

    def form_valid(self, form):
        accion = 'creado' if not form.instance.pk else 'actualizado'
        messages.success(self.request, f'{self.model._meta.verbose_name.capitalize()} {accion}.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        es_nuevo = self.object is None
        ctx['titulo'] = f'{"Crear" if es_nuevo else "Editar"} {self.model._meta.verbose_name}'
        ctx['volver_url'] = self.success_url
        return ctx


# ── MARCA ─────────────────────────────────────────────────────────────────────

class MarcaListView(_CatalogoList):
    model = Marca

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Marcas',
            tiene_codigo=False,
            url_crear='inv:marca_crear',
            url_editar='inv:marca_editar',
            url_toggle='inv:marca_toggle',
            url_eliminar='inv:marca_eliminar',
        )
        return ctx


class MarcaCreateView(_CatalogoForm, CreateView):
    model = Marca
    form_class = MarcaForm
    success_url = reverse_lazy('inv:marca_lista')


class MarcaUpdateView(_CatalogoForm, UpdateView):
    model = Marca
    form_class = MarcaForm
    success_url = reverse_lazy('inv:marca_lista')


@login_required
@require_POST
def marca_toggle(request, pk):
    obj = get_object_or_404(Marca, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Marca {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:marca_lista')


@login_required
@require_POST
def marca_delete(request, pk):
    obj = get_object_or_404(Marca, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
        messages.success(request, f'Marca "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la marca "{nombre}" porque tiene registros asociados.')
    return redirect('inv:marca_lista')


# ── TIPO EQUIPO ───────────────────────────────────────────────────────────────

class TipoEquipoListView(_CatalogoList):
    model = TipoEquipo

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Tipos de Equipo',
            tiene_codigo=False,
            url_crear='inv:tipo_equipo_crear',
            url_editar='inv:tipo_equipo_editar',
            url_toggle='inv:tipo_equipo_toggle',
            url_eliminar='inv:tipo_equipo_eliminar',
        )
        return ctx


class TipoEquipoCreateView(_CatalogoForm, CreateView):
    model = TipoEquipo
    form_class = TipoEquipoForm
    success_url = reverse_lazy('inv:tipo_equipo_lista')


class TipoEquipoUpdateView(_CatalogoForm, UpdateView):
    model = TipoEquipo
    form_class = TipoEquipoForm
    success_url = reverse_lazy('inv:tipo_equipo_lista')


@login_required
@require_POST
def tipo_equipo_toggle(request, pk):
    obj = get_object_or_404(TipoEquipo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Tipo de equipo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_equipo_lista')


@login_required
@require_POST
def tipo_equipo_delete(request, pk):
    obj = get_object_or_404(TipoEquipo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Tipo de equipo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el tipo de equipo "{nombre}" porque tiene registros asociados.')
    return redirect('inv:tipo_equipo_lista')


# ── TIPO PERIFÉRICO ───────────────────────────────────────────────────────────

class TipoPerifericoListView(_CatalogoList):
    model = TipoPeriferico

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Tipos de Periférico',
            tiene_codigo=False,
            url_crear='inv:tipo_periferico_crear',
            url_editar='inv:tipo_periferico_editar',
            url_toggle='inv:tipo_periferico_toggle',
            url_eliminar='inv:tipo_periferico_eliminar',
        )
        return ctx


class TipoPerifericoCreateView(_CatalogoForm, CreateView):
    model = TipoPeriferico
    form_class = TipoPerifericoForm
    success_url = reverse_lazy('inv:tipo_periferico_lista')


class TipoPerifericoUpdateView(_CatalogoForm, UpdateView):
    model = TipoPeriferico
    form_class = TipoPerifericoForm
    success_url = reverse_lazy('inv:tipo_periferico_lista')


@login_required
@require_POST
def tipo_periferico_toggle(request, pk):
    obj = get_object_or_404(TipoPeriferico, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Tipo de periférico {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_periferico_lista')


@login_required
@require_POST
def tipo_periferico_delete(request, pk):
    obj = get_object_or_404(TipoPeriferico, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
        messages.success(request, f'Tipo de periférico "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el tipo de periférico "{nombre}" porque tiene registros asociados.')
    return redirect('inv:tipo_periferico_lista')


# ── INSTITUCIÓN ──────────────────────────────────────────────────────────────

class InstitucionListView(_CatalogoList):
    model = Institucion

    def get_queryset(self):
        qs = super().get_queryset()
        ids = _sedes_ids(self.request.user)
        if ids is not None:
            qs = qs.filter(sedes__id__in=ids).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Instituciones',
            tiene_codigo=False,
            url_crear='inv:institucion_crear',
            url_editar='inv:institucion_editar',
            url_toggle='inv:institucion_toggle',
            url_eliminar='inv:institucion_eliminar',
        )
        return ctx


class InstitucionCreateView(_CatalogoForm, CreateView):
    model = Institucion
    form_class = InstitucionForm
    success_url = reverse_lazy('inv:institucion_lista')


class InstitucionUpdateView(_CatalogoForm, UpdateView):
    model = Institucion
    form_class = InstitucionForm
    success_url = reverse_lazy('inv:institucion_lista')


@login_required
@require_POST
def institucion_toggle(request, pk):
    obj = get_object_or_404(Institucion, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Institución {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:institucion_lista')


@login_required
@require_POST
def institucion_delete(request, pk):
    obj = get_object_or_404(Institucion, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Institución "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la institución "{nombre}" porque tiene sedes o personas asociadas.')
    return redirect('inv:institucion_lista')


# ── SEDE ──────────────────────────────────────────────────────────────────────

class SedeListView(LoginRequiredMixin, ListView):
    model = Sede
    template_name = 'inv/catalogos/sede_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Sede.objects.select_related('institucion').all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)
        ids = _sedes_ids(self.request.user)
        if ids is not None:
            qs = qs.filter(id__in=ids)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['form'] = SedeForm()
        instituciones = Institucion.objects.filter(activo=True).order_by('nombre')
        ids = _sedes_ids(self.request.user)
        if ids is not None:
            instituciones = instituciones.filter(sedes__id__in=ids).distinct()
        ctx['instituciones'] = instituciones
        return ctx


class SedeCreateView(_CatalogoForm, CreateView):
    model = Sede
    form_class = SedeForm
    success_url = reverse_lazy('inv:sede_lista')


class SedeUpdateView(_CatalogoForm, UpdateView):
    model = Sede
    form_class = SedeForm
    success_url = reverse_lazy('inv:sede_lista')


@login_required
@require_POST
def sede_toggle(request, pk):
    obj = get_object_or_404(Sede, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Sede {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:sede_lista')


@login_required
@require_POST
def sede_delete(request, pk):
    obj = get_object_or_404(Sede, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Sede "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la sede "{nombre}" porque tiene áreas asociadas.')
    return redirect('inv:sede_lista')


# ── GRUPOS Y SUBGRUPOS ────────────────────────────────────────────────────────

class GrupoListView(LoginRequiredMixin, View):
    template_name = 'inv/catalogos/grupo_lista.html'

    def get(self, request):
        q = request.GET.get('q', '').strip()
        ids = _sedes_ids(request.user)

        sedes_qs = Sede.objects.select_related('institucion').filter(activo=True).order_by('nombre')
        if ids is not None:
            sedes_qs = sedes_qs.filter(id__in=ids)

        grupos_qs = Grupo.objects.select_related('sede').prefetch_related(
            Prefetch('subgrupos', queryset=Subgrupo.objects.order_by('nombre'))
        ).order_by('nombre')
        if ids is not None:
            grupos_qs = grupos_qs.filter(sede__id__in=ids)
        if q:
            grupos_qs = grupos_qs.filter(
                Q(nombre__icontains=q) | Q(subgrupos__nombre__icontains=q)
            ).distinct()

        grupos_por_sede = {}
        for grupo in grupos_qs:
            grupos_por_sede.setdefault(grupo.sede_id, []).append(grupo)

        sedes_data = [
            {'sede': sede, 'grupos': grupos_por_sede.get(sede.pk, [])}
            for sede in sedes_qs
        ]

        return render(request, self.template_name, {
            'sedes_data': sedes_data,
            'sedes': sedes_qs,
            'q': q,
        })


class GrupoCreateView(_CatalogoForm, CreateView):
    model = Grupo
    form_class = GrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


class GrupoUpdateView(_CatalogoForm, UpdateView):
    model = Grupo
    form_class = GrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


@login_required
@require_POST
def grupo_toggle(request, pk):
    obj = get_object_or_404(Grupo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Grupo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:grupo_lista')


@login_required
@require_POST
def grupo_delete(request, pk):
    obj = get_object_or_404(Grupo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Grupo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene subgrupos o equipos asociados.')
    return redirect('inv:grupo_lista')


class SubgrupoCreateView(_CatalogoForm, CreateView):
    model = Subgrupo
    form_class = SubgrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


class SubgrupoUpdateView(_CatalogoForm, UpdateView):
    model = Subgrupo
    form_class = SubgrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


@login_required
@require_POST
def subgrupo_toggle(request, pk):
    obj = get_object_or_404(Subgrupo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Subgrupo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:grupo_lista')


@login_required
@require_POST
def subgrupo_delete(request, pk):
    obj = get_object_or_404(Subgrupo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Subgrupo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene equipos asociados.')
    return redirect('inv:grupo_lista')


# ── TIPO COMPONENTE ───────────────────────────────────────────────────────────

class TipoComponenteListView(_CatalogoList):
    model = TipoComponente

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Tipos de Componente',
            tiene_codigo=False,
            url_crear='inv:tipo_componente_crear',
            url_editar='inv:tipo_componente_editar',
            url_toggle='inv:tipo_componente_toggle',
            url_eliminar='inv:tipo_componente_eliminar',
        )
        return ctx


class TipoComponenteCreateView(_CatalogoForm, CreateView):
    model = TipoComponente
    form_class = TipoComponenteForm
    success_url = reverse_lazy('inv:tipo_componente_lista')


class TipoComponenteUpdateView(_CatalogoForm, UpdateView):
    model = TipoComponente
    form_class = TipoComponenteForm
    success_url = reverse_lazy('inv:tipo_componente_lista')


@login_required
@require_POST
def tipo_componente_toggle(request, pk):
    obj = get_object_or_404(TipoComponente, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Tipo de componente {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_componente_lista')


@login_required
@require_POST
def tipo_componente_delete(request, pk):
    obj = get_object_or_404(TipoComponente, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
        messages.success(request, f'Tipo de componente "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el tipo de componente "{nombre}" porque tiene registros asociados.')
    return redirect('inv:tipo_componente_lista')


# ── ROL ───────────────────────────────────────────────────────────────────────

class RolListView(LoginRequiredMixin, ListView):
    model = Rol
    template_name = 'inv/catalogos/rol_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Rol.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['url_eliminar'] = 'inv:rol_eliminar'
        return ctx


class RolCreateView(_CatalogoForm, CreateView):
    model = Rol
    form_class = RolForm
    success_url = reverse_lazy('inv:rol_lista')


class RolUpdateView(_CatalogoForm, UpdateView):
    model = Rol
    form_class = RolForm
    success_url = reverse_lazy('inv:rol_lista')


@login_required
@require_POST
def rol_delete(request, pk):
    obj = get_object_or_404(Rol, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Rol "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el rol "{nombre}" porque tiene perfiles o módulos asociados.')
    return redirect('inv:rol_lista')


# ── PERSONA ───────────────────────────────────────────────────────────────────

class PersonaListView(LoginRequiredMixin, ListView):
    model = Persona
    template_name = 'inv/catalogos/persona_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Persona.objects.select_related('institucion').prefetch_related('sedes').all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) |
                Q(apellido1__icontains=q) |
                Q(apellido2__icontains=q)
            )
        ids = _sedes_ids(self.request.user)
        if ids is not None:
            qs = qs.filter(sedes__id__in=ids).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ids = _sedes_ids(self.request.user)
        instituciones = Institucion.objects.filter(activo=True).order_by('nombre')
        sedes_qs = Sede.objects.filter(activo=True).order_by('nombre')
        if ids is not None:
            instituciones = instituciones.filter(sedes__id__in=ids).distinct()
            sedes_qs = sedes_qs.filter(id__in=ids)
        ctx['instituciones'] = instituciones
        ctx['sedes'] = sedes_qs
        ctx['url_eliminar'] = 'inv:persona_eliminar'
        return ctx


class PersonaCreateView(_CatalogoForm, CreateView):
    model = Persona
    form_class = PersonaForm
    success_url = reverse_lazy('inv:persona_lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.info(self.request, f'Usuario generado: <strong>{self.object.user.username}</strong>')
        return response


class PersonaUpdateView(_CatalogoForm, UpdateView):
    model = Persona
    form_class = PersonaForm
    success_url = reverse_lazy('inv:persona_lista')


@login_required
@require_POST
def persona_toggle(request, pk):
    obj = get_object_or_404(Persona, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Persona {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:persona_lista')


@login_required
@require_POST
def persona_delete(request, pk):
    obj = get_object_or_404(Persona, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Persona "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la persona "{nombre}" porque tiene perfiles asociados.')
    return redirect('inv:persona_lista')


# ── PERFIL ────────────────────────────────────────────────────────────────────

class PerfilListView(LoginRequiredMixin, ListView):
    model = Perfil
    template_name = 'inv/catalogos/perfil_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Perfil.objects.select_related('persona', 'rol').all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(persona__nombre__icontains=q) |
                Q(persona__apellido1__icontains=q) |
                Q(rol__nombre__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['personas'] = Persona.objects.filter(activo=True).order_by('apellido1', 'nombre')
        ctx['roles'] = Rol.objects.all().order_by('nombre')
        ctx['url_eliminar'] = 'inv:perfil_eliminar'
        return ctx


class PerfilCreateView(_CatalogoForm, CreateView):
    model = Perfil
    form_class = PerfilForm
    success_url = reverse_lazy('inv:perfil_lista')


class PerfilUpdateView(_CatalogoForm, UpdateView):
    model = Perfil
    form_class = PerfilForm
    success_url = reverse_lazy('inv:perfil_lista')


@login_required
@require_POST
def perfil_toggle(request, pk):
    obj = get_object_or_404(Perfil, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Perfil {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:perfil_lista')


@login_required
@require_POST
def perfil_delete(request, pk):
    obj = get_object_or_404(Perfil, pk=pk)
    nombre = str(obj)
    try:
        obj.delete()
        messages.success(request, f'Perfil "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el perfil "{nombre}" porque tiene registros asociados.')
    return redirect('inv:perfil_lista')


# ── MÓDULO ────────────────────────────────────────────────────────────────────

class ModuloListView(LoginRequiredMixin, ListView):
    model = Modulo
    template_name = 'inv/catalogos/modulo_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Modulo.objects.prefetch_related('roles').all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['todos_roles'] = Rol.objects.all().order_by('nombre')
        ctx['url_eliminar'] = 'inv:modulo_eliminar'
        return ctx


class ModuloCreateView(_CatalogoForm, CreateView):
    model = Modulo
    form_class = ModuloForm
    success_url = reverse_lazy('inv:modulo_lista')


class ModuloUpdateView(_CatalogoForm, UpdateView):
    model = Modulo
    form_class = ModuloForm
    success_url = reverse_lazy('inv:modulo_lista')


@login_required
@require_POST
def modulo_toggle(request, pk):
    obj = get_object_or_404(Modulo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Módulo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:modulo_lista')


@login_required
@require_POST
def modulo_delete(request, pk):
    obj = get_object_or_404(Modulo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Módulo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el módulo "{nombre}" porque tiene registros asociados.')
    return redirect('inv:modulo_lista')


# ── SOFTWARE ──────────────────────────────────────────────────────────────────

class SoftwareListView(LoginRequiredMixin, ListView):
    model = Software
    template_name = 'inv/catalogos/software_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        qs = Software.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(fabricante__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['url_eliminar'] = 'inv:software_eliminar'
        return ctx


class SoftwareCreateView(_CatalogoForm, CreateView):
    model = Software
    form_class = SoftwareForm
    success_url = reverse_lazy('inv:software_lista')


class SoftwareUpdateView(_CatalogoForm, UpdateView):
    model = Software
    form_class = SoftwareForm
    success_url = reverse_lazy('inv:software_lista')


@login_required
@require_POST
def software_toggle(request, pk):
    obj = get_object_or_404(Software, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Software {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:software_lista')


@login_required
@require_POST
def software_delete(request, pk):
    obj = get_object_or_404(Software, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
        messages.success(request, f'Software "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el software "{nombre}" porque tiene registros asociados.')
    return redirect('inv:software_lista')


# ── EQUIPO ────────────────────────────────────────────────────────────────────

_CATALOG_TTL = 900  # 15 minutos


def _catalogo_cached(key, queryset_fn):
    """Devuelve datos de catálogo desde caché; los recalcula si expiraron."""
    data = cache.get(key)
    if data is None:
        data = list(queryset_fn())
        cache.set(key, data, _CATALOG_TTL)
    return data


def _invalidar_catalogos():
    cache.delete_many(['tc_json', 'tp_json', 'marcas_json', 'sw_json', 'grupos_activos'])


class EquipoListView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_lista.html'

    def get(self, request):
        sedes_ids = _sedes_ids(request.user)
        sedes_qs = Sede.objects.select_related('institucion').filter(activo=True).order_by('nombre')
        if sedes_ids is not None:
            sedes_qs = sedes_qs.filter(id__in=sedes_ids)

        qs = Equipo.objects.select_related('grupo__sede', 'subgrupo__grupo__sede')
        if sedes_ids is not None:
            qs = qs.filter(
                Q(grupo__sede__id__in=sedes_ids) | Q(subgrupo__grupo__sede__id__in=sedes_ids)
            )

        conteo = {}
        for eq in qs:
            if eq.subgrupo_id:
                sid = eq.subgrupo.grupo.sede_id
            elif eq.grupo_id:
                sid = eq.grupo.sede_id
            else:
                continue
            conteo[sid] = conteo.get(sid, 0) + 1

        sedes_data = [
            {'sede': sede, 'total': conteo.get(sede.pk, 0)}
            for sede in sedes_qs
        ]
        return render(request, self.template_name, {'sedes_data': sedes_data})


class EquipoSedeView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_sede.html'

    @staticmethod
    def _parse_json_field(data, key):
        try:
            return json.loads(data.get(key, '[]') or '[]')
        except (ValueError, TypeError):
            return []

    def _get_sede(self, request, sede_pk):
        sedes_ids = _sedes_ids(request.user)
        qs = Sede.objects.select_related('institucion').filter(pk=sede_pk, activo=True)
        if sedes_ids is not None:
            qs = qs.filter(id__in=sedes_ids)
        return get_object_or_404(qs)

    def _build_context(self, request, sede, form, modal_open=False):
        q = request.GET.get('q', '').strip()
        equipos = Equipo.objects.select_related(
            'tipo', 'grupo__sede', 'subgrupo__grupo__sede'
        ).filter(
            Q(grupo__sede=sede) | Q(subgrupo__grupo__sede=sede)
        ).order_by('codigo')
        if q:
            equipos = equipos.filter(Q(codigo__icontains=q) | Q(tipo__nombre__icontains=q))

        grupo_id = form.data.get('grupo') if form.is_bound else None
        initial_subgrupos = list(
            Subgrupo.objects.filter(grupo_id=grupo_id, activo=True).values('id', 'nombre')
        ) if grupo_id else []

        pj = self._parse_json_field
        return {
            'sede': sede,
            'equipos': equipos,
            'q': q,
            'form': form,
            'modal_open': modal_open,
            'initial_subgrupos': initial_subgrupos,
            'tc_json': _catalogo_cached('tc_json', lambda: TipoComponente.objects.filter(activo=True).values('id', 'nombre')),
            'tp_json': _catalogo_cached('tp_json', lambda: TipoPeriferico.objects.filter(activo=True).values('id', 'nombre')),
            'marcas_json': _catalogo_cached('marcas_json', lambda: Marca.objects.filter(activo=True).values('id', 'nombre')),
            'sw_json': _catalogo_cached('sw_json', lambda: Software.objects.filter(activo=True).values('id', 'nombre')),
            'init_comp': pj(form.data, 'componentes_json') if form.is_bound else [],
            'init_peri': pj(form.data, 'perifericos_json') if form.is_bound else [],
            'init_sw':   pj(form.data, 'software_json')    if form.is_bound else [],
        }

    def get(self, request, sede_pk):
        sede = self._get_sede(request, sede_pk)
        return render(request, self.template_name, self._build_context(request, sede, EquipoForm()))

    def post(self, request, sede_pk):
        sede = self._get_sede(request, sede_pk)
        form = EquipoForm(request.POST)
        if form.is_valid():
            equipo = form.save()
            pj = self._parse_json_field

            for c in pj(request.POST, 'componentes_json'):
                if c.get('modelo'):
                    try:
                        Componente.objects.create(
                            equipo=equipo,
                            modelo_id=int(c['modelo']),
                            activo=bool(c.get('activo', True)),
                        )
                    except Exception:
                        pass

            for p in pj(request.POST, 'perifericos_json'):
                if p.get('tipo'):
                    try:
                        Periferico.objects.create(
                            equipo=equipo,
                            tipo_id=int(p['tipo']),
                            marca_id=int(p['marca']) if p.get('marca') else None,
                            activo=bool(p.get('activo', True)),
                        )
                    except Exception:
                        pass

            for s in pj(request.POST, 'software_json'):
                if s.get('software'):
                    try:
                        InstalacionSoftware.objects.create(
                            equipo=equipo,
                            software_id=int(s['software']),
                            version=s.get('version') or '',
                            fecha_instalacion=s.get('fecha_instalacion') or None,
                            fecha_vencimiento=s.get('fecha_vencimiento') or None,
                            observaciones=s.get('observaciones') or '',
                        )
                    except Exception:
                        pass

            messages.success(request, 'Equipo creado.')
            return redirect('inv:equipo_detalle', pk=equipo.pk)
        return render(request, self.template_name,
                      self._build_context(request, sede, form, modal_open=True))


class EquipoDetailView(LoginRequiredMixin, DetailView):
    model = Equipo
    context_object_name = 'equipo'
    template_name = 'inv/inventario/equipo_detalle.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        equipo = self.object
        ctx['componentes'] = equipo.componentes.select_related(
            'modelo__tipo', 'modelo__marca'
        ).order_by('modelo__tipo__nombre', 'modelo__nombre')
        ctx['perifericos'] = equipo.perifericos.select_related('tipo', 'marca').order_by('tipo__nombre')
        ctx['software_instalado'] = equipo.software_instalado.select_related('software').order_by('software__nombre')
        ctx['tipos_componente'] = TipoComponente.objects.filter(activo=True)
        ctx['tipos_periferico'] = TipoPeriferico.objects.filter(activo=True)
        ctx['marcas'] = Marca.objects.filter(activo=True)
        ctx['software_catalog'] = Software.objects.filter(activo=True)
        ctx['today'] = date.today()
        return ctx


class EquipoCreateView(LoginRequiredMixin, CreateView):
    model = Equipo
    form_class = EquipoForm
    template_name = 'inv/inventario/equipo_form.html'

    def get_success_url(self):
        return reverse('inv:equipo_detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Equipo creado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Equipo'
        ctx['volver_url'] = reverse_lazy('inv:equipo_lista')
        form = ctx.get('form')
        grupo_id = form.data.get('grupo') if (form and form.is_bound) else None
        ctx['initial_subgrupos'] = list(
            Subgrupo.objects.filter(grupo_id=grupo_id, activo=True).values('id', 'nombre')
        ) if grupo_id else []
        return ctx


class EquipoUpdateView(LoginRequiredMixin, UpdateView):
    model = Equipo
    form_class = EquipoForm
    template_name = 'inv/inventario/equipo_form.html'

    def get_success_url(self):
        return reverse('inv:equipo_detalle', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Equipo actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Equipo — {self.object.codigo}'
        ctx['volver_url'] = reverse('inv:equipo_detalle', kwargs={'pk': self.object.pk})
        form = ctx.get('form')
        if form and form.is_bound:
            grupo_id = form.data.get('grupo')
        else:
            grupo_id = self.object.grupo_id
        ctx['initial_subgrupos'] = list(
            Subgrupo.objects.filter(grupo_id=grupo_id, activo=True).values('id', 'nombre')
        ) if grupo_id else []
        return ctx


@login_required
@require_POST
def equipo_toggle(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    equipo.activo = not equipo.activo
    equipo.save(update_fields=['activo'])
    messages.success(request, f'Equipo {"activado" if equipo.activo else "desactivado"}.')
    return redirect('inv:equipo_lista')


@login_required
@require_POST
def equipo_delete(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    codigo = equipo.codigo
    try:
        equipo.delete()
        messages.success(request, f'Equipo "{codigo}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{codigo}" porque tiene registros asociados.')
    return redirect('inv:equipo_lista')


@login_required
def subgrupos_json(request):
    grupo_id = request.GET.get('grupo_id')
    if not grupo_id:
        return JsonResponse({'subgrupos': []})
    ids = _sedes_ids(request.user)
    qs = Subgrupo.objects.filter(grupo_id=grupo_id, activo=True)
    if ids is not None:
        qs = qs.filter(grupo__sede__id__in=ids)
    return JsonResponse({'subgrupos': list(qs.values('id', 'nombre'))})


@login_required
def modelos_componente_json(request):
    tipo_id = request.GET.get('tipo_id')
    if not tipo_id:
        return JsonResponse({'modelos': []})
    qs = ModeloComponente.objects.filter(tipo_id=tipo_id, activo=True).select_related('marca')
    data = [
        {
            'id': m.id,
            'nombre': m.nombre,
            'capacidad': m.capacidad,
            'marca': m.marca.nombre if m.marca_id else '',
        }
        for m in qs
    ]
    return JsonResponse({'modelos': data})


# ── MODELO COMPONENTE ─────────────────────────────────────────────────────────

class ModeloComponenteListView(LoginRequiredMixin, View):
    template_name = 'inv/catalogos/modelo_componente_lista.html'

    def get(self, request):
        q = request.GET.get('q', '').strip()
        tipo_id = request.GET.get('tipo', '')
        tipos_qs = TipoComponente.objects.filter(activo=True).order_by('nombre')
        marcas_qs = Marca.objects.filter(activo=True).order_by('nombre')
        qs = ModeloComponente.objects.select_related('tipo', 'marca').order_by('tipo__nombre', 'nombre')
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(tipo__nombre__icontains=q))
        if tipo_id:
            qs = qs.filter(tipo_id=tipo_id)
        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, self.template_name, {
            'objetos': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'titulo': 'Modelos de componente',
            'q': q,
            'tipos': tipos_qs,
            'marcas': marcas_qs,
            'tipo_sel': tipo_id,
        })


class ModeloComponenteCreateView(_CatalogoForm, CreateView):
    model = ModeloComponente
    form_class = ModeloComponenteForm
    success_url = reverse_lazy('inv:modelo_componente_lista')


class ModeloComponenteUpdateView(_CatalogoForm, UpdateView):
    model = ModeloComponente
    form_class = ModeloComponenteForm
    success_url = reverse_lazy('inv:modelo_componente_lista')


@login_required
@require_POST
def modelo_componente_toggle(request, pk):
    obj = get_object_or_404(ModeloComponente, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Modelo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:modelo_componente_lista')


@login_required
@require_POST
def modelo_componente_delete(request, pk):
    obj = get_object_or_404(ModeloComponente, pk=pk)
    nombre = str(obj)
    try:
        obj.delete()
        messages.success(request, f'Modelo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene componentes asociados.')
    return redirect('inv:modelo_componente_lista')


# ── COMPONENTE ────────────────────────────────────────────────────────────────

@login_required
@require_POST
def componente_create(request, equipo_pk):
    equipo = get_object_or_404(Equipo, pk=equipo_pk)
    form = ComponenteForm(request.POST)
    if form.is_valid():
        comp = form.save(commit=False)
        comp.equipo = equipo
        comp.save()
        messages.success(request, 'Componente agregado.')
    else:
        messages.error(request, 'Error al guardar el componente. Verifica los campos.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def componente_update(request, equipo_pk, pk):
    componente = get_object_or_404(Componente, pk=pk, equipo_id=equipo_pk)
    form = ComponenteForm(request.POST, instance=componente)
    if form.is_valid():
        form.save()
        messages.success(request, 'Componente actualizado.')
    else:
        messages.error(request, 'Error al actualizar el componente.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def componente_delete(request, equipo_pk, pk):
    componente = get_object_or_404(Componente, pk=pk, equipo_id=equipo_pk)
    componente.delete()
    messages.success(request, 'Componente eliminado.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


# ── PERIFÉRICO ────────────────────────────────────────────────────────────────

@login_required
@require_POST
def periferico_create(request, equipo_pk):
    equipo = get_object_or_404(Equipo, pk=equipo_pk)
    form = PerifericoForm(request.POST)
    if form.is_valid():
        peri = form.save(commit=False)
        peri.equipo = equipo
        peri.save()
        messages.success(request, 'Periférico agregado.')
    else:
        messages.error(request, 'Error al guardar el periférico. Verifica los campos.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def periferico_update(request, equipo_pk, pk):
    periferico = get_object_or_404(Periferico, pk=pk, equipo_id=equipo_pk)
    form = PerifericoForm(request.POST, instance=periferico)
    if form.is_valid():
        form.save()
        messages.success(request, 'Periférico actualizado.')
    else:
        messages.error(request, 'Error al actualizar el periférico.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def periferico_delete(request, equipo_pk, pk):
    periferico = get_object_or_404(Periferico, pk=pk, equipo_id=equipo_pk)
    periferico.delete()
    messages.success(request, 'Periférico eliminado.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


# ── SOFTWARE INSTALADO ────────────────────────────────────────────────────────

@login_required
@require_POST
def instalacion_create(request, equipo_pk):
    equipo = get_object_or_404(Equipo, pk=equipo_pk)
    form = InstalacionSoftwareForm(request.POST)
    if form.is_valid():
        inst = form.save(commit=False)
        inst.equipo = equipo
        inst.save()
        messages.success(request, 'Software agregado.')
    else:
        messages.error(request, 'Error al guardar la instalación. Verifica los campos.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def instalacion_update(request, equipo_pk, pk):
    instalacion = get_object_or_404(InstalacionSoftware, pk=pk, equipo_id=equipo_pk)
    form = InstalacionSoftwareForm(request.POST, instance=instalacion)
    if form.is_valid():
        form.save()
        messages.success(request, 'Instalación actualizada.')
    else:
        messages.error(request, 'Error al actualizar la instalación.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)


@login_required
@require_POST
def instalacion_delete(request, equipo_pk, pk):
    instalacion = get_object_or_404(InstalacionSoftware, pk=pk, equipo_id=equipo_pk)
    instalacion.delete()
    messages.success(request, 'Software eliminado.')
    return redirect('inv:equipo_detalle', pk=equipo_pk)
