from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from django.db import IntegrityError
from django.db.models import Prefetch
from django.urls import reverse_lazy, reverse, NoReverseMatch
from django.views.decorators.http import require_POST
import json
from datetime import date
from django.db.models import Q, ProtectedError, Case, When, Value, F, IntegerField, Count

from .models import (Marca, TipoEquipo, TipoPeriferico, TipoComponente, ModeloComponente,
                     Modulo, Perfil, Institucion, Sede, Grupo, Subgrupo, Rol, Persona, Software,
                     Equipo, Componente, Periferico, InstalacionSoftware, Dispositivo,
                     ViaReporte, TipoRequerimiento, Estado, Prioridad,
                     GrupoProgramas, Requerimiento,
                     sedes_permitidas, _es_admin_rol)
from .forms import (MarcaForm, TipoEquipoForm, TipoPerifericoForm, TipoComponenteForm,
                    ModeloComponenteForm,
                    InstitucionForm, SedeForm, GrupoForm, SubgrupoForm,
                    RolForm, PersonaForm, PerfilForm, ModuloForm, SoftwareForm,
                    EquipoForm, DispositivoForm, ComponenteForm, PerifericoForm, InstalacionSoftwareForm,
                    ViaReporteForm, TipoRequerimientoForm, EstadoForm, PrioridadForm,
                    GrupoProgramasForm, RequerimientoForm)


def _sedes_ids(user):
    """None = sin filtro (superusuario/staff/rol-admin). Lista vacía o de IDs = usuario normal."""
    if user.is_superuser or user.is_staff or _es_admin_rol(user):
        return None
    if hasattr(user, 'persona'):
        return list(user.persona.sedes.values_list('id', flat=True))
    return []


def _tiene_perm(user, perm):
    """True si el usuario tiene el permiso dado. Superuser/staff/rol-admin siempre tienen acceso."""
    return user.is_superuser or user.is_staff or _es_admin_rol(user) or user.has_perm(perm)


def _sin_permiso(request, perm, redirect_url):
    """Si el usuario NO tiene el permiso devuelve un redirect con mensaje. Si sí tiene, devuelve None."""
    if _tiene_perm(request.user, perm):
        return None
    messages.error(request, 'No tienes permiso para realizar esta acción.')
    return redirect(redirect_url)


def _solo_superusuario(request):
    """Devuelve redirect si el usuario no es superusuario, None si sí lo es."""
    if not request.user.is_superuser:
        messages.error(request, 'Solo los superusuarios pueden acceder a esta sección.')
        return redirect('inv:mantenimientos')
    return None


class _SuperuserMixin:
    """Restringe acceso exclusivamente a superusuarios en vistas basadas en clase."""
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            messages.error(request, 'Solo los superusuarios pueden acceder a esta sección.')
            return redirect('inv:mantenimientos')
        return super().dispatch(request, *args, **kwargs)


@login_required
def mantenimientos(request):
    return render(request, 'inv/mantenimientos/index.html')


@login_required
def inventario(request):
    return redirect('inv:equipo_lista')


@login_required
def home(request):
    u = request.user
    if u.is_superuser:
        modulos = list(Modulo.objects.filter(activo=True).order_by('orden', 'nombre'))
    elif hasattr(u, 'persona'):
        roles_ids = Perfil.objects.filter(
            persona=u.persona, activo=True
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

    return render(request, 'inv/home.html', {
        'modulos': modulos,
        'puede_formulario': _tiene_perm(u, 'inv.add_requerimiento'),
        'puede_registro': _tiene_perm(u, 'inv.view_requerimiento'),
    })


# ── Mixins base ───────────────────────────────────────────────────────────────

class _ModalForm:
    """Para vistas cuyo formulario vive en un modal dentro de la lista.
    En vez de ir a catalogo_form.html al fallar, redirige al listado con el error."""
    def form_invalid(self, form):
        partes = []
        for campo, errores in form.errors.items():
            if campo == '__all__':
                partes.extend(errores)
            else:
                label = form.fields[campo].label or campo
                partes.append(f'{label}: {", ".join(errores)}')
        messages.error(self.request, 'No se pudo guardar. ' + ' | '.join(partes))
        next_url = self.request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(self.success_url)


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
        al = self.model._meta.app_label
        mn = self.model._meta.model_name
        u = self.request.user
        ctx['puede_agregar'] = _tiene_perm(u, f'{al}.add_{mn}')
        ctx['puede_editar'] = _tiene_perm(u, f'{al}.change_{mn}')
        ctx['puede_eliminar'] = _tiene_perm(u, f'{al}.delete_{mn}')
        return ctx


class _CatalogoForm(LoginRequiredMixin):
    template_name = 'inv/catalogos/catalogo_form.html'

    def dispatch(self, request, *args, **kwargs):
        al = self.model._meta.app_label
        mn = self.model._meta.model_name
        perm = f'{al}.add_{mn}' if not self.kwargs.get('pk') else f'{al}.change_{mn}'
        if not _tiene_perm(request.user, perm):
            messages.error(request, 'No tienes permiso para realizar esta acción.')
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

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


class MarcaCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Marca
    form_class = MarcaForm
    success_url = reverse_lazy('inv:marca_lista')


class MarcaUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Marca
    form_class = MarcaForm
    success_url = reverse_lazy('inv:marca_lista')


@login_required
@require_POST
def marca_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_marca', 'inv:marca_lista')
    if r: return r
    obj = get_object_or_404(Marca, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Marca {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:marca_lista')


@login_required
@require_POST
def marca_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_marca', 'inv:marca_lista')
    if r: return r
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


class TipoEquipoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = TipoEquipo
    form_class = TipoEquipoForm
    success_url = reverse_lazy('inv:tipo_equipo_lista')


class TipoEquipoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = TipoEquipo
    form_class = TipoEquipoForm
    success_url = reverse_lazy('inv:tipo_equipo_lista')


@login_required
@require_POST
def tipo_equipo_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_tipoequipo', 'inv:tipo_equipo_lista')
    if r: return r
    obj = get_object_or_404(TipoEquipo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Tipo de equipo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_equipo_lista')


@login_required
@require_POST
def tipo_equipo_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_tipoequipo', 'inv:tipo_equipo_lista')
    if r: return r
    obj = get_object_or_404(TipoEquipo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
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


class TipoPerifericoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = TipoPeriferico
    form_class = TipoPerifericoForm
    success_url = reverse_lazy('inv:tipo_periferico_lista')


class TipoPerifericoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = TipoPeriferico
    form_class = TipoPerifericoForm
    success_url = reverse_lazy('inv:tipo_periferico_lista')


@login_required
@require_POST
def tipo_periferico_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_tipoperiferico', 'inv:tipo_periferico_lista')
    if r: return r
    obj = get_object_or_404(TipoPeriferico, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Tipo de periférico {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_periferico_lista')


@login_required
@require_POST
def tipo_periferico_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_tipoperiferico', 'inv:tipo_periferico_lista')
    if r: return r
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

class InstitucionListView(_SuperuserMixin, _CatalogoList):
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


class InstitucionCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Institucion
    form_class = InstitucionForm
    success_url = reverse_lazy('inv:institucion_lista')


class InstitucionUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Institucion
    form_class = InstitucionForm
    success_url = reverse_lazy('inv:institucion_lista')


@login_required
@require_POST
def institucion_toggle(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Institucion, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Institución {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:institucion_lista')


@login_required
@require_POST
def institucion_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Institucion, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Institución "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la institución "{nombre}" porque tiene sedes o personas asociadas.')
    return redirect('inv:institucion_lista')


# ── SEDE ──────────────────────────────────────────────────────────────────────

class SedeListView(_SuperuserMixin, LoginRequiredMixin, ListView):
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
        u = self.request.user
        ctx['puede_agregar'] = _tiene_perm(u, 'inv.add_sede')
        ctx['puede_editar']  = _tiene_perm(u, 'inv.change_sede')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_sede')
        return ctx


class SedeCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Sede
    form_class = SedeForm
    success_url = reverse_lazy('inv:sede_lista')


class SedeUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Sede
    form_class = SedeForm
    success_url = reverse_lazy('inv:sede_lista')


@login_required
@require_POST
def sede_toggle(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Sede, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Sede {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:sede_lista')


@login_required
@require_POST
def sede_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
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

        u = request.user
        return render(request, self.template_name, {
            'sedes_data': sedes_data,
            'sedes': sedes_qs,
            'q': q,
            'puede_agregar':  _tiene_perm(u, 'inv.add_grupo'),
            'puede_editar':   _tiene_perm(u, 'inv.change_grupo'),
            'puede_eliminar': _tiene_perm(u, 'inv.delete_grupo'),
        })


class GrupoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Grupo
    form_class = GrupoForm
    success_url = reverse_lazy('inv:grupo_lista')

    def get_success_url(self):
        next_url = self.request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return next_url
        return str(self.success_url)


class GrupoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Grupo
    form_class = GrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


@login_required
@require_POST
def grupo_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_grupo', 'inv:grupo_lista')
    if r: return r
    obj = get_object_or_404(Grupo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Grupo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:grupo_lista')


@login_required
@require_POST
def grupo_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_grupo', 'inv:grupo_lista')
    if r: return r
    obj = get_object_or_404(Grupo, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Grupo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene subgrupos o equipos asociados.')
    return redirect('inv:grupo_lista')


class SubgrupoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Subgrupo
    form_class = SubgrupoForm
    success_url = reverse_lazy('inv:grupo_lista')

    def get_success_url(self):
        next_url = self.request.POST.get('next', '')
        if next_url and next_url.startswith('/'):
            return next_url
        return str(self.success_url)


class SubgrupoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Subgrupo
    form_class = SubgrupoForm
    success_url = reverse_lazy('inv:grupo_lista')


@login_required
@require_POST
def subgrupo_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_subgrupo', 'inv:grupo_lista')
    if r: return r
    obj = get_object_or_404(Subgrupo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Subgrupo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:grupo_lista')


@login_required
@require_POST
def subgrupo_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_subgrupo', 'inv:grupo_lista')
    if r: return r
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


class TipoComponenteCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = TipoComponente
    form_class = TipoComponenteForm
    success_url = reverse_lazy('inv:tipo_componente_lista')


class TipoComponenteUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = TipoComponente
    form_class = TipoComponenteForm
    success_url = reverse_lazy('inv:tipo_componente_lista')


@login_required
@require_POST
def tipo_componente_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_tipocomponente', 'inv:tipo_componente_lista')
    if r: return r
    obj = get_object_or_404(TipoComponente, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Tipo de componente {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_componente_lista')


@login_required
@require_POST
def tipo_componente_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_tipocomponente', 'inv:tipo_componente_lista')
    if r: return r
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

class RolListView(_SuperuserMixin, LoginRequiredMixin, ListView):
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
        u = self.request.user
        ctx['puede_agregar']  = _tiene_perm(u, 'inv.add_rol')
        ctx['puede_editar']   = _tiene_perm(u, 'inv.change_rol')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_rol')
        return ctx


class RolCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Rol
    form_class = RolForm
    success_url = reverse_lazy('inv:rol_lista')


class RolUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Rol
    form_class = RolForm
    success_url = reverse_lazy('inv:rol_lista')


@login_required
@require_POST
def rol_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Rol, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Rol "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el rol "{nombre}" porque tiene perfiles o módulos asociados.')
    return redirect('inv:rol_lista')


# ── PERSONA ───────────────────────────────────────────────────────────────────

class PersonaListView(_SuperuserMixin, LoginRequiredMixin, ListView):
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
        u = self.request.user
        ctx['puede_agregar']  = _tiene_perm(u, 'inv.add_persona')
        ctx['puede_editar']   = _tiene_perm(u, 'inv.change_persona')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_persona')
        return ctx


class PersonaCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Persona
    form_class = PersonaForm
    success_url = reverse_lazy('inv:persona_lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.info(self.request, f'Usuario generado: <strong>{self.object.user.username}</strong>')
        return response


class PersonaUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Persona
    form_class = PersonaForm
    success_url = reverse_lazy('inv:persona_lista')


@login_required
@require_POST
def persona_toggle(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Persona, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Persona {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:persona_lista')


@login_required
@require_POST
def persona_cambiar_clave(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Persona, pk=pk)
    clave1 = request.POST.get('clave1', '').strip()
    clave2 = request.POST.get('clave2', '').strip()
    if not clave1:
        messages.error(request, 'La clave no puede estar vacía.')
    elif clave1 != clave2:
        messages.error(request, 'Las claves no coinciden.')
    elif len(clave1) < 6:
        messages.error(request, 'La clave debe tener al menos 6 caracteres.')
    else:
        obj.user.set_password(clave1)
        obj.user.save(update_fields=['password'])
        messages.success(request, f'Clave de <strong>{obj.nombres_completos}</strong> actualizada correctamente.')
    return redirect('inv:persona_lista')


@login_required
@require_POST
def persona_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Persona, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Persona "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar la persona "{nombre}" porque tiene perfiles asociados.')
    return redirect('inv:persona_lista')


# ── PERFIL ────────────────────────────────────────────────────────────────────

class PerfilListView(_SuperuserMixin, LoginRequiredMixin, ListView):
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
        u = self.request.user
        ctx['puede_agregar']  = _tiene_perm(u, 'inv.add_perfil')
        ctx['puede_editar']   = _tiene_perm(u, 'inv.change_perfil')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_perfil')
        return ctx


class PerfilCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Perfil
    form_class = PerfilForm
    success_url = reverse_lazy('inv:perfil_lista')


class PerfilUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Perfil
    form_class = PerfilForm
    success_url = reverse_lazy('inv:perfil_lista')


@login_required
@require_POST
def perfil_toggle(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Perfil, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Perfil {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:perfil_lista')


@login_required
@require_POST
def perfil_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Perfil, pk=pk)
    nombre = str(obj)
    try:
        obj.delete()
        messages.success(request, f'Perfil "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el perfil "{nombre}" porque tiene registros asociados.')
    return redirect('inv:perfil_lista')


# ── MÓDULO ────────────────────────────────────────────────────────────────────

class ModuloListView(_SuperuserMixin, LoginRequiredMixin, ListView):
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
        u = self.request.user
        ctx['puede_agregar']  = _tiene_perm(u, 'inv.add_modulo')
        ctx['puede_editar']   = _tiene_perm(u, 'inv.change_modulo')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_modulo')
        return ctx


class ModuloCreateView(_SuperuserMixin, _ModalForm, _CatalogoForm, CreateView):
    model = Modulo
    form_class = ModuloForm
    success_url = reverse_lazy('inv:modulo_lista')


class ModuloUpdateView(_SuperuserMixin, _ModalForm, _CatalogoForm, UpdateView):
    model = Modulo
    form_class = ModuloForm
    success_url = reverse_lazy('inv:modulo_lista')


@login_required
@require_POST
def modulo_toggle(request, pk):
    r = _solo_superusuario(request)
    if r: return r
    obj = get_object_or_404(Modulo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Módulo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:modulo_lista')


@login_required
@require_POST
def modulo_delete(request, pk):
    r = _solo_superusuario(request)
    if r: return r
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
        u = self.request.user
        ctx['puede_agregar']  = _tiene_perm(u, 'inv.add_software')
        ctx['puede_editar']   = _tiene_perm(u, 'inv.change_software')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_software')
        return ctx


class SoftwareCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Software
    form_class = SoftwareForm
    success_url = reverse_lazy('inv:software_lista')


class SoftwareUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Software
    form_class = SoftwareForm
    success_url = reverse_lazy('inv:software_lista')


@login_required
@require_POST
def software_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_software', 'inv:software_lista')
    if r: return r
    obj = get_object_or_404(Software, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    _invalidar_catalogos()
    messages.success(request, f'Software {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:software_lista')


@login_required
@require_POST
def software_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_software', 'inv:software_lista')
    if r: return r
    obj = get_object_or_404(Software, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        _invalidar_catalogos()
        messages.success(request, f'Software "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el software "{nombre}" porque tiene registros asociados.')
    return redirect('inv:software_lista')


# ── GRUPO DE PROGRAMAS ────────────────────────────────────────────────────────

class GrupoProgramasListView(LoginRequiredMixin, ListView):
    model = GrupoProgramas
    template_name = 'inv/catalogos/grupo_programas_lista.html'
    context_object_name = 'objetos'
    paginate_by = 20

    def get_queryset(self):
        return GrupoProgramas.objects.prefetch_related('programas').order_by('nombre')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        ctx['titulo'] = 'Grupos de Programas'
        ctx['puede_crear']   = _tiene_perm(u, 'inv.add_grupoprogramas')
        ctx['puede_editar']  = _tiene_perm(u, 'inv.change_grupoprogramas')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_grupoprogramas')
        return ctx


class GrupoProgramasCreateView(_CatalogoForm, CreateView):
    model = GrupoProgramas
    form_class = GrupoProgramasForm
    template_name = 'inv/catalogos/grupo_programas_form.html'
    success_url = reverse_lazy('inv:grupo_programas_lista')


class GrupoProgramasUpdateView(_CatalogoForm, UpdateView):
    model = GrupoProgramas
    form_class = GrupoProgramasForm
    template_name = 'inv/catalogos/grupo_programas_form.html'
    success_url = reverse_lazy('inv:grupo_programas_lista')


@login_required
@require_POST
def grupo_programas_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_grupoprogramas', 'inv:grupo_programas_lista')
    if r: return r
    obj = get_object_or_404(GrupoProgramas, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Grupo "{obj.nombre}" {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:grupo_programas_lista')


@login_required
@require_POST
def grupo_programas_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_grupoprogramas', 'inv:grupo_programas_lista')
    if r: return r
    obj = get_object_or_404(GrupoProgramas, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Grupo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar el grupo "{nombre}" porque tiene registros asociados.')
    return redirect('inv:grupo_programas_lista')


@login_required
def grupo_programas_software_json(request, pk):
    """Devuelve la lista de software de un grupo para pre-cargar en el formulario de equipo."""
    grupo = get_object_or_404(GrupoProgramas, pk=pk, activo=True)
    data = [{'id': s.id, 'nombre': s.nombre} for s in grupo.programas.filter(activo=True).order_by('nombre')]
    return JsonResponse({'programas': data})


# ── EQUIPO ────────────────────────────────────────────────────────────────────

_CATALOG_TTL = 900  # 15 minutos


def _parse_json_field(data, key):
    try:
        return json.loads(data.get(key, '[]') or '[]')
    except (ValueError, TypeError):
        return []


def _catalogo_cached(key, queryset_fn):
    """Devuelve datos de catálogo desde caché; los recalcula si expiraron."""
    data = cache.get(key)
    if data is None:
        data = list(queryset_fn())
        cache.set(key, data, _CATALOG_TTL)
    return data


def _invalidar_catalogos():
    cache.delete_many(['tc_json', 'tp_json', 'marcas_json', 'sw_json', 'grupos_activos', 'te_json',
                       'tp_obj', 'marcas_obj', 'te_obj'])


class EquipoListView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_lista.html'

    def get(self, request):
        from django.db.models import Count
        sedes_ids = _sedes_ids(request.user)
        sedes_qs = Sede.objects.select_related('institucion').filter(activo=True).order_by('nombre')
        if sedes_ids is not None:
            sedes_qs = sedes_qs.filter(id__in=sedes_ids)

        # COUNT GROUP BY en la BD en lugar de cargar todos los equipos en Python
        grupo_q = (
            Equipo.objects
            .filter(subgrupo__isnull=True, grupo__isnull=False)
            .values('grupo__sede_id')
            .annotate(total=Count('id'))
        )
        subgrupo_q = (
            Equipo.objects
            .filter(subgrupo__isnull=False)
            .values('subgrupo__grupo__sede_id')
            .annotate(total=Count('id'))
        )
        if sedes_ids is not None:
            grupo_q = grupo_q.filter(grupo__sede__id__in=sedes_ids)
            subgrupo_q = subgrupo_q.filter(subgrupo__grupo__sede__id__in=sedes_ids)

        conteo = {}
        for row in grupo_q:
            sid = row['grupo__sede_id']
            conteo[sid] = conteo.get(sid, 0) + row['total']
        for row in subgrupo_q:
            sid = row['subgrupo__grupo__sede_id']
            conteo[sid] = conteo.get(sid, 0) + row['total']

        sedes_data = [
            {'sede': sede, 'total': conteo.get(sede.pk, 0)}
            for sede in sedes_qs
        ]
        return render(request, self.template_name, {'sedes_data': sedes_data})


class EquipoSedeView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_sede.html'

    def get(self, request, sede_pk):
        sedes_ids = _sedes_ids(request.user)
        qs = Sede.objects.select_related('institucion').filter(pk=sede_pk, activo=True)
        if sedes_ids is not None:
            qs = qs.filter(id__in=sedes_ids)
        sede = get_object_or_404(qs)
        grupos = (
            Grupo.objects.filter(sede=sede, activo=True)
            .order_by('id')
            .annotate(
                num_subgrupos=Count('subgrupos', filter=Q(subgrupos__activo=True), distinct=True),
                num_equipos=Count('equipos', distinct=True),
            )
        )
        return render(request, self.template_name, {'sede': sede, 'grupos': grupos})


class EquipoGrupoView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_grupo.html'

    def get(self, request, grupo_pk):
        grupo = get_object_or_404(Grupo.objects.select_related('sede__institucion'), pk=grupo_pk, activo=True)
        subgrupos = (
            Subgrupo.objects.filter(grupo=grupo, activo=True)
            .order_by('id')
            .annotate(
                num_equipos=Count('equipos', distinct=True),
                num_dispositivos=Count('dispositivos', distinct=True),
            )
        )
        return render(request, self.template_name, {
            'grupo': grupo,
            'sede': grupo.sede,
            'subgrupos': subgrupos,
            'tipos_equipo': _catalogo_cached('te_obj', lambda: list(TipoEquipo.objects.filter(activo=True).order_by('nombre'))),
            'tipos_periferico': _catalogo_cached('tp_obj', lambda: list(TipoPeriferico.objects.filter(activo=True).order_by('nombre'))),
            'marcas': _catalogo_cached('marcas_obj', lambda: list(Marca.objects.filter(activo=True).order_by('nombre'))),
            'tc_json': _catalogo_cached('tc_json', lambda: TipoComponente.objects.filter(activo=True).values('id', 'nombre')),
            'tp_json': _catalogo_cached('tp_json', lambda: TipoPeriferico.objects.filter(activo=True).values('id', 'nombre')),
            'marcas_json': _catalogo_cached('marcas_json', lambda: Marca.objects.filter(activo=True).values('id', 'nombre')),
            'sw_json': _catalogo_cached('sw_json', lambda: Software.objects.filter(activo=True).values('id', 'nombre')),
            'gp_json': list(GrupoProgramas.objects.filter(activo=True).values('id', 'nombre').order_by('nombre')),
        })


class EquipoSubgrupoView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/equipo_subgrupo.html'

    def _ctx(self, request, subgrupo, form, modal_open=False):
        equipos = list(
            Equipo.objects.filter(subgrupo=subgrupo)
            .select_related('tipo')
            .prefetch_related(
                'componentes__modelo__tipo',
                'perifericos__tipo',
                'perifericos__marca',
                'software_instalado__software',
            )
            .order_by('id')
        )
        equipos_data = {}
        for eq in equipos:
            equipos_data[eq.pk] = {
                'codigo': eq.codigo,
                'tipo_id': eq.tipo_id,
                'tipo_nombre': eq.tipo.nombre if eq.tipo else '',
                'ip': eq.ip or '',
                'obs': eq.observaciones or '',
                'activo': eq.activo,
                'comps': [
                    {
                        'modelo': c.modelo_id,
                        'tipo_nombre': c.modelo.tipo.nombre if c.modelo and c.modelo.tipo else '',
                        'modelo_nombre': c.modelo.nombre if c.modelo else '',
                        'capacidad': c.modelo.capacidad or '' if c.modelo else '',
                        'activo': c.activo,
                    }
                    for c in eq.componentes.all() if c.modelo_id
                ],
                'peri': [
                    {
                        'tipo': p.tipo_id,
                        'tipo_nombre': p.tipo.nombre if p.tipo else '',
                        'marca': p.marca_id,
                        'marca_nombre': p.marca.nombre if p.marca_id and p.marca else '',
                        'activo': p.activo,
                    }
                    for p in eq.perifericos.all() if p.tipo_id
                ],
                'sw': [
                    {
                        'id': i.pk,
                        'equipo_id': eq.pk,
                        'software': i.software_id,
                        'software_nombre': i.software.nombre if i.software else '',
                        'version': i.version or '',
                        'fecha_instalacion': str(i.fecha_instalacion) if i.fecha_instalacion else '',
                        'fecha_vencimiento': str(i.fecha_vencimiento) if i.fecha_vencimiento else '',
                        'observaciones': i.observaciones or '',
                    }
                    for i in eq.software_instalado.all() if i.software_id
                ],
            }
        return {
            'subgrupo': subgrupo,
            'grupo': subgrupo.grupo,
            'sede': subgrupo.grupo.sede,
            'equipos': equipos,
            'equipos_data': equipos_data,
            'dispositivos': Dispositivo.objects.filter(subgrupo=subgrupo).select_related('tipo', 'marca').order_by('id'),
            'form': form,
            'modal_open': modal_open,
            'puede_agregar':  _tiene_perm(request.user, 'inv.add_equipo'),
            'puede_editar':   _tiene_perm(request.user, 'inv.change_equipo'),
            'puede_eliminar': _tiene_perm(request.user, 'inv.delete_equipo'),
            'tc_json': _catalogo_cached('tc_json', lambda: TipoComponente.objects.filter(activo=True).values('id', 'nombre')),
            'tp_json': _catalogo_cached('tp_json', lambda: TipoPeriferico.objects.filter(activo=True).values('id', 'nombre')),
            'marcas_json': _catalogo_cached('marcas_json', lambda: Marca.objects.filter(activo=True).values('id', 'nombre')),
            'sw_json': _catalogo_cached('sw_json', lambda: Software.objects.filter(activo=True).values('id', 'nombre')),
            'gp_json': list(GrupoProgramas.objects.filter(activo=True).values('id', 'nombre').order_by('nombre')),
            'te_json': _catalogo_cached('te_json', lambda: TipoEquipo.objects.filter(activo=True).values('id', 'nombre')),
            'tipos_periferico': _catalogo_cached('tp_obj', lambda: list(TipoPeriferico.objects.filter(activo=True).order_by('nombre'))),
            'marcas': _catalogo_cached('marcas_obj', lambda: list(Marca.objects.filter(activo=True).order_by('nombre'))),
            'init_comp': _parse_json_field(form.data, 'componentes_json') if form.is_bound else [],
            'init_peri': _parse_json_field(form.data, 'perifericos_json') if form.is_bound else [],
            'init_sw':   _parse_json_field(form.data, 'software_json')    if form.is_bound else [],
        }

    def get(self, request, subgrupo_pk):
        subgrupo = get_object_or_404(Subgrupo.objects.select_related('grupo__sede__institucion'), pk=subgrupo_pk, activo=True)
        return render(request, self.template_name, self._ctx(request, subgrupo, EquipoForm()))

    def post(self, request, subgrupo_pk):
        subgrupo = get_object_or_404(Subgrupo.objects.select_related('grupo__sede__institucion'), pk=subgrupo_pk, activo=True)
        form = EquipoForm(request.POST)
        if form.is_valid():
            equipo = form.save()
            for c in _parse_json_field(request.POST, 'componentes_json'):
                if c.get('modelo'):
                    try:
                        Componente.objects.create(equipo=equipo, modelo_id=int(c['modelo']), activo=bool(c.get('activo', True)))
                    except Exception:
                        pass
            for p in _parse_json_field(request.POST, 'perifericos_json'):
                if p.get('tipo'):
                    try:
                        Periferico.objects.create(equipo=equipo, tipo_id=int(p['tipo']), marca_id=int(p['marca']) if p.get('marca') else None, activo=bool(p.get('activo', True)))
                    except Exception:
                        pass
            for s in _parse_json_field(request.POST, 'software_json'):
                if s.get('software'):
                    try:
                        InstalacionSoftware.objects.create(equipo=equipo, software_id=int(s['software']), version=s.get('version') or '', fecha_instalacion=s.get('fecha_instalacion') or None, fecha_vencimiento=s.get('fecha_vencimiento') or None, observaciones=s.get('observaciones') or '')
                    except Exception:
                        pass
            messages.success(request, 'Equipo creado.')
            next_url = request.POST.get('next', '')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('inv:equipo_lista_subgrupo', subgrupo_pk=subgrupo.pk)
        return render(request, self.template_name, self._ctx(request, subgrupo, form, modal_open=True))


class EquipoDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        equipo = get_object_or_404(Equipo, pk=pk)
        if equipo.subgrupo_id:
            return redirect('inv:equipo_lista_subgrupo', subgrupo_pk=equipo.subgrupo_id)
        return redirect('inv:equipo_lista')


class EquipoCreateView(LoginRequiredMixin, CreateView):
    model = Equipo
    form_class = EquipoForm
    template_name = 'inv/inventario/equipo_form.html'

    def get_success_url(self):
        if self.object.subgrupo_id:
            return reverse('inv:equipo_lista_subgrupo', kwargs={'subgrupo_pk': self.object.subgrupo_id})
        return reverse('inv:equipo_lista')

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
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        if self.object.subgrupo_id:
            return reverse('inv:equipo_lista_subgrupo', kwargs={'subgrupo_pk': self.object.subgrupo_id})
        return reverse('inv:equipo_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Equipo actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Equipo — {self.object.codigo}'
        if self.object.subgrupo_id:
            ctx['volver_url'] = reverse('inv:equipo_lista_subgrupo', kwargs={'subgrupo_pk': self.object.subgrupo_id})
        else:
            ctx['volver_url'] = reverse('inv:equipo_lista')
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
    if not _tiene_perm(request.user, 'inv.change_equipo'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    equipo = get_object_or_404(Equipo, pk=pk)
    equipo.activo = not equipo.activo
    equipo.save(update_fields=['activo'])
    messages.success(request, f'Equipo {"activado" if equipo.activo else "desactivado"}.')
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('inv:equipo_lista')


@login_required
@require_POST
def equipo_delete(request, pk):
    if not _tiene_perm(request.user, 'inv.delete_equipo'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    equipo = get_object_or_404(Equipo, pk=pk)
    codigo = equipo.codigo
    try:
        equipo.delete()
        messages.success(request, f'Equipo "{codigo}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{codigo}" porque tiene registros asociados.')
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('inv:equipo_lista')


@login_required
@require_POST
def equipo_editar_completo(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    form = EquipoForm(request.POST, instance=equipo)
    if form.is_valid():
        equipo = form.save()
        equipo.componentes.all().delete()
        for c in _parse_json_field(request.POST, 'componentes_json'):
            if c.get('modelo'):
                try:
                    Componente.objects.create(
                        equipo=equipo,
                        modelo_id=int(c['modelo']),
                        activo=bool(c.get('activo', True))
                    )
                except Exception:
                    pass
        equipo.perifericos.all().delete()
        for p in _parse_json_field(request.POST, 'perifericos_json'):
            if p.get('tipo'):
                try:
                    Periferico.objects.create(
                        equipo=equipo,
                        tipo_id=int(p['tipo']),
                        marca_id=int(p['marca']) if p.get('marca') else None,
                        activo=bool(p.get('activo', True))
                    )
                except Exception:
                    pass
        equipo.software_instalado.all().delete()
        for s in _parse_json_field(request.POST, 'software_json'):
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
        messages.success(request, f'Equipo "{equipo.codigo}" actualizado.')
    else:
        partes = []
        for campo, errores in form.errors.items():
            if campo == '__all__':
                partes.extend(errores)
            else:
                label = form.fields[campo].label or campo
                partes.append(f'{label}: {", ".join(errores)}')
        messages.error(request, 'No se pudo guardar. ' + ' | '.join(partes))
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    if equipo.subgrupo_id:
        return redirect('inv:equipo_lista_subgrupo', subgrupo_pk=equipo.subgrupo_id)
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
        u = request.user
        return render(request, self.template_name, {
            'objetos': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'titulo': 'Modelos de componente',
            'q': q,
            'tipos': tipos_qs,
            'marcas': marcas_qs,
            'tipo_sel': tipo_id,
            'puede_agregar':  _tiene_perm(u, 'inv.add_modelocomponente'),
            'puede_editar':   _tiene_perm(u, 'inv.change_modelocomponente'),
            'puede_eliminar': _tiene_perm(u, 'inv.delete_modelocomponente'),
        })


class ModeloComponenteCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = ModeloComponente
    form_class = ModeloComponenteForm
    success_url = reverse_lazy('inv:modelo_componente_lista')


class ModeloComponenteUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = ModeloComponente
    form_class = ModeloComponenteForm
    success_url = reverse_lazy('inv:modelo_componente_lista')


@login_required
@require_POST
def modelo_componente_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_modelocomponente', 'inv:modelo_componente_lista')
    if r: return r
    obj = get_object_or_404(ModeloComponente, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Modelo {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:modelo_componente_lista')


@login_required
@require_POST
def modelo_componente_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_modelocomponente', 'inv:modelo_componente_lista')
    if r: return r
    obj = get_object_or_404(ModeloComponente, pk=pk)
    nombre = str(obj)
    try:
        obj.delete()
        messages.success(request, f'Modelo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene componentes asociados.')
    return redirect('inv:modelo_componente_lista')


# ── DISPOSITIVO ──────────────────────────────────────────────────────────────

class DispositivoListView(LoginRequiredMixin, View):
    template_name = 'inv/inventario/dispositivo_lista.html'

    def get(self, request):
        q = request.GET.get('q', '').strip()
        subgrupo_id = request.GET.get('subgrupo', '')
        tipo_id = request.GET.get('tipo', '')

        subgrupos_qs = Subgrupo.objects.select_related('grupo__sede').filter(activo=True).order_by('grupo__sede__nombre', 'grupo__nombre', 'nombre')
        tipos_qs = TipoPeriferico.objects.filter(activo=True).order_by('nombre')
        marcas_qs = Marca.objects.filter(activo=True).order_by('nombre')

        qs = Dispositivo.objects.select_related('subgrupo__grupo__sede', 'tipo', 'marca').order_by('id')
        if q:
            qs = qs.filter(
                Q(tipo__nombre__icontains=q) | Q(ip__icontains=q) |
                Q(extension__icontains=q) | Q(marca__nombre__icontains=q) |
                Q(subgrupo__nombre__icontains=q)
            )
        if subgrupo_id:
            qs = qs.filter(subgrupo_id=subgrupo_id)
        if tipo_id:
            qs = qs.filter(tipo_id=tipo_id)

        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, self.template_name, {
            'objetos': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'titulo': 'Dispositivos',
            'q': q,
            'subgrupos': subgrupos_qs,
            'tipos': tipos_qs,
            'marcas': marcas_qs,
            'subgrupo_sel': subgrupo_id,
            'tipo_sel': tipo_id,
        })


class DispositivoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Dispositivo
    form_class = DispositivoForm
    success_url = reverse_lazy('inv:dispositivo_lista')

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        return reverse('inv:dispositivo_lista')


class DispositivoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Dispositivo
    form_class = DispositivoForm
    success_url = reverse_lazy('inv:dispositivo_lista')

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        return reverse('inv:dispositivo_lista')


@login_required
@require_POST
def dispositivo_toggle(request, pk):
    if not _tiene_perm(request.user, 'inv.change_dispositivo'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    obj = get_object_or_404(Dispositivo, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Dispositivo {"activado" if obj.activo else "desactivado"}.')
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('inv:dispositivo_lista')


@login_required
@require_POST
def dispositivo_delete(request, pk):
    if not _tiene_perm(request.user, 'inv.delete_dispositivo'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    obj = get_object_or_404(Dispositivo, pk=pk)
    nombre = str(obj)
    try:
        obj.delete()
        messages.success(request, f'Dispositivo "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene registros asociados.')
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('inv:dispositivo_lista')


# ── COMPONENTE ────────────────────────────────────────────────────────────────

def _redirect_equipo(request, equipo_pk):
    next_url = request.POST.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    equipo = Equipo.objects.filter(pk=equipo_pk).first()
    if equipo and equipo.subgrupo_id:
        return redirect('inv:equipo_lista_subgrupo', subgrupo_pk=equipo.subgrupo_id)
    return redirect('inv:equipo_lista')


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
    return _redirect_equipo(request, equipo_pk)


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
    return _redirect_equipo(request, equipo_pk)


@login_required
@require_POST
def componente_delete(request, equipo_pk, pk):
    if not _tiene_perm(request.user, 'inv.delete_componente'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    componente = get_object_or_404(Componente, pk=pk, equipo_id=equipo_pk)
    componente.delete()
    messages.success(request, 'Componente eliminado.')
    return _redirect_equipo(request, equipo_pk)


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
    return _redirect_equipo(request, equipo_pk)


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
    return _redirect_equipo(request, equipo_pk)


@login_required
@require_POST
def periferico_delete(request, equipo_pk, pk):
    if not _tiene_perm(request.user, 'inv.delete_periferico'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    periferico = get_object_or_404(Periferico, pk=pk, equipo_id=equipo_pk)
    periferico.delete()
    messages.success(request, 'Periférico eliminado.')
    return _redirect_equipo(request, equipo_pk)


# ── SOFTWARE INSTALADO ────────────────────────────────────────────────────────

@login_required
@require_POST
def instalacion_create(request, equipo_pk):
    equipo = get_object_or_404(Equipo, pk=equipo_pk)
    form = InstalacionSoftwareForm(request.POST)
    if form.is_valid():
        inst = form.save(commit=False)
        inst.equipo = equipo
        try:
            inst.save()
            messages.success(request, 'Software agregado.')
        except IntegrityError:
            messages.error(request, 'Este software ya está registrado en el equipo.')
    else:
        messages.error(request, 'Error al guardar la instalación. Verifica los campos.')
    return _redirect_equipo(request, equipo_pk)


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
    return _redirect_equipo(request, equipo_pk)


@login_required
@require_POST
def instalacion_delete(request, equipo_pk, pk):
    if not _tiene_perm(request.user, 'inv.delete_instalacionsoftware'):
        messages.error(request, 'No tienes permiso para realizar esta accion.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    instalacion = get_object_or_404(InstalacionSoftware, pk=pk, equipo_id=equipo_pk)
    instalacion.delete()
    messages.success(request, 'Software eliminado.')
    return _redirect_equipo(request, equipo_pk)


# ── CAMBIAR MI CONTRASEÑA ─────────────────────────────────────────────────────

@login_required
@require_POST
def cambiar_mi_clave(request):
    clave_actual = request.POST.get('clave_actual', '').strip()
    clave1 = request.POST.get('clave1', '').strip()
    clave2 = request.POST.get('clave2', '').strip()
    next_url = request.POST.get('next', '') or request.META.get('HTTP_REFERER', '/')

    if not request.user.check_password(clave_actual):
        messages.error(request, 'La contraseña actual es incorrecta.')
    elif not clave1:
        messages.error(request, 'La nueva contraseña no puede estar vacía.')
    elif clave1 != clave2:
        messages.error(request, 'Las contraseñas nuevas no coinciden.')
    elif len(clave1) < 6:
        messages.error(request, 'La nueva contraseña debe tener al menos 6 caracteres.')
    else:
        request.user.set_password(clave1)
        request.user.save(update_fields=['password'])
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Contraseña actualizada correctamente.')

    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('inv:home')


# ── VÍA DE REPORTE ────────────────────────────────────────────────────────────

class ViaReporteListView(_CatalogoList):
    model = ViaReporte

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Vías de Reporte',
            tiene_codigo=False,
            url_crear='inv:via_reporte_crear',
            url_editar='inv:via_reporte_editar',
            url_toggle='inv:via_reporte_toggle',
            url_eliminar='inv:via_reporte_eliminar',
        )
        return ctx


class ViaReporteCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = ViaReporte
    form_class = ViaReporteForm
    success_url = reverse_lazy('inv:via_reporte_lista')


class ViaReporteUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = ViaReporte
    form_class = ViaReporteForm
    success_url = reverse_lazy('inv:via_reporte_lista')


@login_required
@require_POST
def via_reporte_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_viareporte', 'inv:via_reporte_lista')
    if r: return r
    obj = get_object_or_404(ViaReporte, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Vía de reporte {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:via_reporte_lista')


@login_required
@require_POST
def via_reporte_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_viareporte', 'inv:via_reporte_lista')
    if r: return r
    obj = get_object_or_404(ViaReporte, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Vía de reporte "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene requerimientos asociados.')
    return redirect('inv:via_reporte_lista')


# ── TIPO DE REQUERIMIENTO ─────────────────────────────────────────────────────

class TipoRequerimientoListView(_CatalogoList):
    model = TipoRequerimiento

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Tipos de Requerimiento',
            tiene_codigo=False,
            url_crear='inv:tipo_requerimiento_crear',
            url_editar='inv:tipo_requerimiento_editar',
            url_toggle='inv:tipo_requerimiento_toggle',
            url_eliminar='inv:tipo_requerimiento_eliminar',
        )
        return ctx


class TipoRequerimientoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = TipoRequerimiento
    form_class = TipoRequerimientoForm
    success_url = reverse_lazy('inv:tipo_requerimiento_lista')


class TipoRequerimientoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = TipoRequerimiento
    form_class = TipoRequerimientoForm
    success_url = reverse_lazy('inv:tipo_requerimiento_lista')


@login_required
@require_POST
def tipo_requerimiento_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_tiporequerimiento', 'inv:tipo_requerimiento_lista')
    if r: return r
    obj = get_object_or_404(TipoRequerimiento, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Tipo de requerimiento {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:tipo_requerimiento_lista')


@login_required
@require_POST
def tipo_requerimiento_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_tiporequerimiento', 'inv:tipo_requerimiento_lista')
    if r: return r
    obj = get_object_or_404(TipoRequerimiento, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Tipo de requerimiento "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene requerimientos asociados.')
    return redirect('inv:tipo_requerimiento_lista')


# ── ESTADO ────────────────────────────────────────────────────────────────────

class EstadoListView(_CatalogoList):
    model = Estado

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Estados',
            tiene_codigo=False,
            url_crear='inv:estado_crear',
            url_editar='inv:estado_editar',
            url_toggle='inv:estado_toggle',
            url_eliminar='inv:estado_eliminar',
        )
        return ctx


class EstadoCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Estado
    form_class = EstadoForm
    success_url = reverse_lazy('inv:estado_lista')


class EstadoUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Estado
    form_class = EstadoForm
    success_url = reverse_lazy('inv:estado_lista')


@login_required
@require_POST
def estado_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_estado', 'inv:estado_lista')
    if r: return r
    obj = get_object_or_404(Estado, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Estado {"activado" if obj.activo else "desactivado"}.')
    return redirect('inv:estado_lista')


@login_required
@require_POST
def estado_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_estado', 'inv:estado_lista')
    if r: return r
    obj = get_object_or_404(Estado, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Estado "{nombre}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene requerimientos asociados.')
    return redirect('inv:estado_lista')


# ── PRIORIDAD ─────────────────────────────────────────────────────────────────

class PrioridadListView(_CatalogoList):
    model = Prioridad

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo='Prioridades',
            tiene_codigo=False,
            url_crear='inv:prioridad_crear',
            url_editar='inv:prioridad_editar',
            url_toggle='inv:prioridad_toggle',
            url_eliminar='inv:prioridad_eliminar',
        )
        return ctx


class PrioridadCreateView(_ModalForm, _CatalogoForm, CreateView):
    model = Prioridad
    form_class = PrioridadForm
    success_url = reverse_lazy('inv:prioridad_lista')


class PrioridadUpdateView(_ModalForm, _CatalogoForm, UpdateView):
    model = Prioridad
    form_class = PrioridadForm
    success_url = reverse_lazy('inv:prioridad_lista')


@login_required
@require_POST
def prioridad_toggle(request, pk):
    r = _sin_permiso(request, 'inv.change_prioridad', 'inv:prioridad_lista')
    if r: return r
    obj = get_object_or_404(Prioridad, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.success(request, f'Prioridad {"activada" if obj.activo else "desactivada"}.')
    return redirect('inv:prioridad_lista')


@login_required
@require_POST
def prioridad_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_prioridad', 'inv:prioridad_lista')
    if r: return r
    obj = get_object_or_404(Prioridad, pk=pk)
    nombre = obj.nombre
    try:
        obj.delete()
        messages.success(request, f'Prioridad "{nombre}" eliminada.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{nombre}" porque tiene requerimientos asociados.')
    return redirect('inv:prioridad_lista')


# ── REQUERIMIENTO ─────────────────────────────────────────────────────────────

class FormularioRequerimientoView(LoginRequiredMixin, View):
    """Módulo 1 — Página dedicada para registrar un nuevo requerimiento."""

    def _ctx(self, form):
        return {
            'form': form,
            'tipos_requerimiento': TipoRequerimiento.objects.filter(activo=True),
            'vias_reporte': ViaReporte.objects.filter(activo=True),
            'estados': Estado.objects.filter(activo=True),
            'prioridades': Prioridad.objects.filter(activo=True),
            'areas': Grupo.objects.filter(activo=True),
            'tecnicos': Persona.objects.filter(activo=True),
        }

    def get(self, request):
        if not _tiene_perm(request.user, 'inv.add_requerimiento'):
            messages.error(request, 'No tienes permiso para registrar requerimientos.')
            return redirect('inv:home')
        return render(request, 'inv/soporte/formulario_requerimiento.html',
                      self._ctx(RequerimientoForm()))

    def post(self, request):
        if not _tiene_perm(request.user, 'inv.add_requerimiento'):
            messages.error(request, 'No tienes permiso para registrar requerimientos.')
            return redirect('inv:home')
        form = RequerimientoForm(request.POST, request.FILES)
        if form.is_valid():
            req = form.save()
            messages.success(request, f'Requerimiento {req.numero_ticket} registrado exitosamente.')
            return redirect('inv:formulario_requerimiento')
        return render(request, 'inv/soporte/formulario_requerimiento.html', self._ctx(form))


class RegistroRequerimientosView(LoginRequiredMixin, ListView):
    """Módulo 2 — Tabla con todos los requerimientos registrados + filtros."""
    model = Requerimiento
    template_name = 'inv/soporte/requerimiento_lista.html'
    context_object_name = 'requerimientos'
    paginate_by = 20

    def get_queryset(self):
        qs = Requerimiento.objects.select_related(
            'tipo_requerimiento', 'estado', 'prioridad', 'tecnico', 'area', 'departamento'
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(numero_ticket__icontains=q) |
                Q(persona_reporto__icontains=q) |
                Q(descripcion__icontains=q)
            )
        estado_id = self.request.GET.get('estado', '').strip()
        if estado_id:
            qs = qs.filter(estado_id=estado_id)
        prioridad_id = self.request.GET.get('prioridad', '').strip()
        if prioridad_id:
            qs = qs.filter(prioridad_id=prioridad_id)
        area_id = self.request.GET.get('area', '').strip()
        if area_id:
            qs = qs.filter(area_id=area_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')
        ctx['filtro_prioridad'] = self.request.GET.get('prioridad', '')
        ctx['filtro_area'] = self.request.GET.get('area', '')
        ctx['estados'] = Estado.objects.filter(activo=True)
        ctx['prioridades'] = Prioridad.objects.filter(activo=True)
        ctx['areas'] = Grupo.objects.filter(activo=True)
        ctx['tipos_requerimiento'] = TipoRequerimiento.objects.filter(activo=True)
        ctx['vias_reporte'] = ViaReporte.objects.filter(activo=True)
        ctx['tecnicos'] = Persona.objects.filter(activo=True)
        u = self.request.user
        ctx['puede_editar'] = _tiene_perm(u, 'inv.change_requerimiento')
        ctx['puede_eliminar'] = _tiene_perm(u, 'inv.delete_requerimiento')
        return ctx


@login_required
def requerimiento_json(request, pk):
    obj = get_object_or_404(Requerimiento, pk=pk)
    return JsonResponse({
        'pk': obj.pk,
        'fecha_reporte': obj.fecha_reporte.isoformat() if obj.fecha_reporte else '',
        'persona_reporto': obj.persona_reporto or '',
        'tipo_requerimiento_id': obj.tipo_requerimiento_id or '',
        'via_reporte_id': obj.via_reporte_id or '',
        'descripcion': obj.descripcion,
        'estado_id': obj.estado_id or '',
        'prioridad_id': obj.prioridad_id or '',
        'area_id': obj.area_id or '',
        'departamento_id': obj.departamento_id or '',
        'tecnico_id': obj.tecnico_id or '',
        'fecha_solucion': obj.fecha_solucion.isoformat() if obj.fecha_solucion else '',
        'accion': obj.accion,
        'observaciones': obj.observaciones,
    })


class RequerimientoUpdateView(LoginRequiredMixin, UpdateView):
    model = Requerimiento
    form_class = RequerimientoForm
    success_url = reverse_lazy('inv:registro_requerimientos')

    def dispatch(self, request, *args, **kwargs):
        r = _sin_permiso(request, 'inv.change_requerimiento', 'inv:registro_requerimientos')
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Requerimiento actualizado.')
        return super().form_valid(form)

    def form_invalid(self, form):
        partes = []
        for campo, errores in form.errors.items():
            if campo == '__all__':
                partes.extend(errores)
            else:
                label = form.fields[campo].label or campo
                partes.append(f'{label}: {", ".join(errores)}')
        messages.error(self.request, 'No se pudo guardar. ' + ' | '.join(partes))
        return redirect('inv:registro_requerimientos')


@login_required
@require_POST
def requerimiento_delete(request, pk):
    r = _sin_permiso(request, 'inv.delete_requerimiento', 'inv:registro_requerimientos')
    if r:
        return r
    obj = get_object_or_404(Requerimiento, pk=pk)
    ticket = obj.numero_ticket or f'#{obj.pk}'
    try:
        obj.delete()
        messages.success(request, f'Requerimiento "{ticket}" eliminado.')
    except ProtectedError:
        messages.error(request, f'No se puede eliminar "{ticket}" porque tiene registros asociados.')
    return redirect('inv:registro_requerimientos')
