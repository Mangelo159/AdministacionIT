from django.urls import path
from . import views

app_name = 'inv'

urlpatterns = [
    path('', views.home, name='home'),
    path('mantenimientos/', views.mantenimientos, name='mantenimientos'),

    # Marcas
    path('marcas/', views.MarcaListView.as_view(), name='marca_lista'),
    path('marcas/nueva/', views.MarcaCreateView.as_view(), name='marca_crear'),
    path('marcas/<int:pk>/editar/', views.MarcaUpdateView.as_view(), name='marca_editar'),
    path('marcas/<int:pk>/toggle/', views.marca_toggle, name='marca_toggle'),
    path('marcas/<int:pk>/eliminar/', views.marca_delete, name='marca_eliminar'),

    # Tipos de equipo
    path('tipos-equipo/', views.TipoEquipoListView.as_view(), name='tipo_equipo_lista'),
    path('tipos-equipo/nuevo/', views.TipoEquipoCreateView.as_view(), name='tipo_equipo_crear'),
    path('tipos-equipo/<int:pk>/editar/', views.TipoEquipoUpdateView.as_view(), name='tipo_equipo_editar'),
    path('tipos-equipo/<int:pk>/toggle/', views.tipo_equipo_toggle, name='tipo_equipo_toggle'),
    path('tipos-equipo/<int:pk>/eliminar/', views.tipo_equipo_delete, name='tipo_equipo_eliminar'),

    # Tipos de periférico
    path('tipos-periferico/', views.TipoPerifericoListView.as_view(), name='tipo_periferico_lista'),
    path('tipos-periferico/nuevo/', views.TipoPerifericoCreateView.as_view(), name='tipo_periferico_crear'),
    path('tipos-periferico/<int:pk>/editar/', views.TipoPerifericoUpdateView.as_view(), name='tipo_periferico_editar'),
    path('tipos-periferico/<int:pk>/toggle/', views.tipo_periferico_toggle, name='tipo_periferico_toggle'),
    path('tipos-periferico/<int:pk>/eliminar/', views.tipo_periferico_delete, name='tipo_periferico_eliminar'),

    # Instituciones
    path('instituciones/', views.InstitucionListView.as_view(), name='institucion_lista'),
    path('instituciones/nueva/', views.InstitucionCreateView.as_view(), name='institucion_crear'),
    path('instituciones/<int:pk>/editar/', views.InstitucionUpdateView.as_view(), name='institucion_editar'),
    path('instituciones/<int:pk>/toggle/', views.institucion_toggle, name='institucion_toggle'),
    path('instituciones/<int:pk>/eliminar/', views.institucion_delete, name='institucion_eliminar'),

    # Sedes
    path('sedes/', views.SedeListView.as_view(), name='sede_lista'),
    path('sedes/nueva/', views.SedeCreateView.as_view(), name='sede_crear'),
    path('sedes/<int:pk>/editar/', views.SedeUpdateView.as_view(), name='sede_editar'),
    path('sedes/<int:pk>/toggle/', views.sede_toggle, name='sede_toggle'),
    path('sedes/<int:pk>/eliminar/', views.sede_delete, name='sede_eliminar'),

    # Grupos
    path('grupos/', views.GrupoListView.as_view(), name='grupo_lista'),
    path('grupos/nuevo/', views.GrupoCreateView.as_view(), name='grupo_crear'),
    path('grupos/<int:pk>/editar/', views.GrupoUpdateView.as_view(), name='grupo_editar'),
    path('grupos/<int:pk>/toggle/', views.grupo_toggle, name='grupo_toggle'),
    path('grupos/<int:pk>/eliminar/', views.grupo_delete, name='grupo_eliminar'),

    # Subgrupos
    path('subgrupos/nuevo/', views.SubgrupoCreateView.as_view(), name='subgrupo_crear'),
    path('subgrupos/<int:pk>/editar/', views.SubgrupoUpdateView.as_view(), name='subgrupo_editar'),
    path('subgrupos/<int:pk>/toggle/', views.subgrupo_toggle, name='subgrupo_toggle'),
    path('subgrupos/<int:pk>/eliminar/', views.subgrupo_delete, name='subgrupo_eliminar'),

    # Tipos de componente
    path('tipos-componente/', views.TipoComponenteListView.as_view(), name='tipo_componente_lista'),
    path('tipos-componente/nuevo/', views.TipoComponenteCreateView.as_view(), name='tipo_componente_crear'),
    path('tipos-componente/<int:pk>/editar/', views.TipoComponenteUpdateView.as_view(), name='tipo_componente_editar'),
    path('tipos-componente/<int:pk>/toggle/', views.tipo_componente_toggle, name='tipo_componente_toggle'),
    path('tipos-componente/<int:pk>/eliminar/', views.tipo_componente_delete, name='tipo_componente_eliminar'),

    # Roles
    path('roles/', views.RolListView.as_view(), name='rol_lista'),
    path('roles/nuevo/', views.RolCreateView.as_view(), name='rol_crear'),
    path('roles/<int:pk>/editar/', views.RolUpdateView.as_view(), name='rol_editar'),
    path('roles/<int:pk>/eliminar/', views.rol_delete, name='rol_eliminar'),

    # Personas
    path('personas/', views.PersonaListView.as_view(), name='persona_lista'),
    path('personas/nueva/', views.PersonaCreateView.as_view(), name='persona_crear'),
    path('personas/<int:pk>/editar/', views.PersonaUpdateView.as_view(), name='persona_editar'),
    path('personas/<int:pk>/toggle/', views.persona_toggle, name='persona_toggle'),
    path('personas/<int:pk>/eliminar/', views.persona_delete, name='persona_eliminar'),

    # Perfiles
    path('perfiles/', views.PerfilListView.as_view(), name='perfil_lista'),
    path('perfiles/nuevo/', views.PerfilCreateView.as_view(), name='perfil_crear'),
    path('perfiles/<int:pk>/editar/', views.PerfilUpdateView.as_view(), name='perfil_editar'),
    path('perfiles/<int:pk>/toggle/', views.perfil_toggle, name='perfil_toggle'),
    path('perfiles/<int:pk>/eliminar/', views.perfil_delete, name='perfil_eliminar'),

    # Módulos
    path('modulos/', views.ModuloListView.as_view(), name='modulo_lista'),
    path('modulos/nuevo/', views.ModuloCreateView.as_view(), name='modulo_crear'),
    path('modulos/<int:pk>/editar/', views.ModuloUpdateView.as_view(), name='modulo_editar'),
    path('modulos/<int:pk>/toggle/', views.modulo_toggle, name='modulo_toggle'),
    path('modulos/<int:pk>/eliminar/', views.modulo_delete, name='modulo_eliminar'),

    # Software
    path('software/', views.SoftwareListView.as_view(), name='software_lista'),
    path('software/nuevo/', views.SoftwareCreateView.as_view(), name='software_crear'),
    path('software/<int:pk>/editar/', views.SoftwareUpdateView.as_view(), name='software_editar'),
    path('software/<int:pk>/toggle/', views.software_toggle, name='software_toggle'),
    path('software/<int:pk>/eliminar/', views.software_delete, name='software_eliminar'),
]
