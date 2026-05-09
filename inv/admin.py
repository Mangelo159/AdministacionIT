from django.contrib import admin
from .models import Marca, TipoEquipo, TipoPeriferico, TipoComponente, Modulo, Rol, Software


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(TipoEquipo)
class TipoEquipoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(TipoPeriferico)
class TipoPerifericoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre', 'codigo']


@admin.register(TipoComponente)
class TipoComponenteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre', 'codigo']


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre']


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ['orden', 'nombre', 'url_name', 'icono', 'activo']
    list_display_links = ['nombre']
    list_editable = ['orden', 'activo']
    list_filter = ['activo', 'roles']
    search_fields = ['nombre']
    filter_horizontal = ['roles']


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fabricante', 'requiere_licencia', 'activo']
    list_filter = ['requiere_licencia', 'activo']
    search_fields = ['nombre', 'fabricante']
