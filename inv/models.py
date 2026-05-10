import unicodedata

from django.contrib.auth.models import User, Group
from django.db import models
from django.utils.crypto import get_random_string

def _limpiar(texto):
    texto = unicodedata.normalize('NFKD', texto)
    return texto.encode('ascii', 'ignore').decode('ascii').lower()


# ============================================================
# ROLES, INSTITUCIONES Y PERSONAS
# ============================================================

class Rol(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    group = models.OneToOneField(Group, on_delete=models.SET_NULL,null=True, blank=True, related_name='rol',)

    class Meta:
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Institucion(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Institución'
        verbose_name_plural = 'Instituciones'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Sede(models.Model):
    nombre = models.CharField(max_length=100)
    institucion = models.ForeignKey(Institucion, on_delete=models.PROTECT, related_name='sedes')
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'
        ordering = ['institucion', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['institucion', 'nombre'],
                name='unique_sede_por_institucion',
            ),
        ]

    def __str__(self):
        return f'{self.institucion.nombre} - {self.nombre}'


class Persona(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,null=True, blank=True, related_name='persona',)
    nombre = models.CharField(max_length=100)
    apellido1 = models.CharField(max_length=100)
    apellido2 = models.CharField(max_length=100, blank=True, default='')
    institucion = models.ForeignKey(Institucion, on_delete=models.PROTECT)
    roles = models.ManyToManyField(Rol, through='Perfil', related_name='personas')
    sedes = models.ManyToManyField(Sede, blank=True, related_name='personas', verbose_name='Sedes asignadas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'
        ordering = ['apellido1', 'apellido2', 'nombre']

    def __str__(self):
        return self.nombres_completos

    @property
    def nombres_completos(self):
        partes = [self.nombre, self.apellido1, self.apellido2]
        return ' '.join(p for p in partes if p)

    def _crear_usuario(self):
        inicial = _limpiar(self.nombre.split()[0])[0]
        base_username = f'{inicial}{_limpiar(self.apellido1)}'
        username = base_username
        contador = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{contador}'
            contador += 1

        self.user = User.objects.create_user(username=username,password=get_random_string(length=12),)

    def save(self, *args, **kwargs):
        if not self.user_id:
            self._crear_usuario()
        super().save(*args, **kwargs)


class Perfil(models.Model):
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'
        ordering = ['-fecha_asignacion']
        constraints = [
            models.UniqueConstraint(
                fields=['persona', 'rol'], name='unique_persona_rol',
            ),
        ]
        indexes = [
            models.Index(fields=['persona', 'activo'], name='perfil_persona_activo_idx'),
        ]

    def __str__(self):
        return f'{self.persona.nombres_completos} - {self.rol.nombre}'


# ============================================================
# MÓDULOS DEL SISTEMA (MENÚ POR ROL)
# ============================================================

class Modulo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    url_name = models.CharField(max_length=100,help_text='Nombre de la URL de Django (ej: "catalogos:clientes_lista")')
    icono = models.CharField(max_length=50, blank=True,help_text='Clase del icono (ej: "fa-users", "bi-people")')
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    roles = models.ManyToManyField(Rol, related_name='modulos', blank=True)

    class Meta:
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['orden', 'nombre']
        indexes = [
            models.Index(fields=['activo', 'orden'], name='modulo_activo_orden_idx'),
        ]

    def __str__(self):
        return self.nombre


# ============================================================
# GRUPOS Y SUBGRUPOS (ubicaciones jerárquicas fijas 2 niveles)
# ============================================================

class Grupo(models.Model):
    nombre = models.CharField(max_length=100)
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='grupos')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        ordering = ['sede', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['sede', 'nombre'], name='unique_grupo_por_sede'),
        ]

    def __str__(self):
        return f'{self.sede.nombre} → {self.nombre}'


class Subgrupo(models.Model):
    nombre = models.CharField(max_length=100)
    grupo = models.ForeignKey(Grupo, on_delete=models.PROTECT, related_name='subgrupos')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Subgrupo'
        verbose_name_plural = 'Subgrupos'
        ordering = ['grupo', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['grupo', 'nombre'], name='unique_subgrupo_por_grupo'),
        ]

    def __str__(self):
        return f'{self.grupo.nombre} → {self.nombre}'


# ============================================================
# CATÁLOGOS DE INVENTARIO
# ============================================================

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class TipoEquipo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tipo de equipo'
        verbose_name_plural = 'Tipos de equipo'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class TipoPeriferico(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tipo de periférico'
        verbose_name_plural = 'Tipos de periférico'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    tipo = models.ForeignKey(TipoEquipo, on_delete=models.PROTECT)
    grupo = models.ForeignKey(Grupo, on_delete=models.PROTECT, null=True, blank=True, related_name='equipos')
    subgrupo = models.ForeignKey(Subgrupo, on_delete=models.PROTECT, null=True, blank=True, related_name='equipos')
    ip = models.CharField(max_length=45, blank=True, verbose_name='Dirección IP')
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def ubicacion(self):
        return self.subgrupo or self.grupo

    @property
    def sede(self):
        if self.subgrupo:
            return self.subgrupo.grupo.sede
        if self.grupo:
            return self.grupo.sede
        return None

    class Meta:
        verbose_name = 'Equipo'
        verbose_name_plural = 'Equipos'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['grupo', 'subgrupo'], name='equipo_grupo_subgrupo_idx'),
        ]

    def __str__(self):
        return f'{self.codigo} - {self.tipo}'


class TipoComponente(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tipo de componente'
        verbose_name_plural = 'Tipos de componente'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class ModeloComponente(models.Model):
    """Catálogo de modelos específicos por tipo (p. ej. Intel Core i5-10400, Kingston DDR4 8GB)."""
    tipo = models.ForeignKey(TipoComponente, on_delete=models.PROTECT, related_name='modelos')
    nombre = models.CharField(max_length=150, help_text='Ej: Intel Core i5-10400, Kingston DDR4')
    capacidad = models.CharField(max_length=50, blank=True, help_text='Ej: 8 GB, 500 GB, 3.6 GHz')
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Modelo de componente'
        verbose_name_plural = 'Modelos de componentes'
        ordering = ['tipo', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'nombre', 'capacidad'],
                name='unique_modelo_componente',
            ),
        ]

    def __str__(self):
        s = f'{self.tipo.nombre} — {self.nombre}'
        if self.capacidad:
            s += f' ({self.capacidad})'
        return s


class Componente(models.Model):
    """Componente interno de un equipo asignado desde el catálogo."""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='componentes')
    modelo = models.ForeignKey(ModeloComponente, on_delete=models.PROTECT, related_name='usos',
                               null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Componente'
        verbose_name_plural = 'Componentes'
        ordering = ['equipo', 'modelo__tipo', 'modelo__nombre']

    def __str__(self):
        return f'{self.modelo} — {self.equipo.codigo}'


class Periferico(models.Model):
    tipo = models.ForeignKey(TipoPeriferico, on_delete=models.PROTECT)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, null=True, blank=True)
    equipo = models.ForeignKey(Equipo, on_delete=models.SET_NULL, null=True, blank=True,related_name='perifericos',help_text='Equipo al que está conectado (puede estar suelto en bodega)')
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Periférico'
        verbose_name_plural = 'Periféricos'
        ordering = ['tipo__nombre']

    def __str__(self):
        marca = f' {self.marca.nombre}' if self.marca_id else ''
        return f'{self.tipo.nombre}{marca}'


class Software(models.Model):
    """Catálogo de software (Windows 11, Office 365, AutoCAD, etc.)."""
    nombre = models.CharField(max_length=150, unique=True)
    fabricante = models.CharField(max_length=100, blank=True)
    requiere_licencia = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Software'
        verbose_name_plural = 'Software'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class InstalacionSoftware(models.Model):
    """Software instalado en un equipo específico, con su licencia."""
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='software_instalado')
    software = models.ForeignKey(Software, on_delete=models.PROTECT)
    version = models.CharField(max_length=50, blank=True)
    fecha_instalacion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Software instalado'
        verbose_name_plural = 'Software instalado'
        constraints = [
            models.UniqueConstraint(
                fields=['equipo', 'software'],
                name='unique_software_por_equipo',
            ),
        ]

    def __str__(self):
        return f'{self.software} en {self.equipo.codigo}'


class Dispositivo(models.Model):
    """Dispositivo de sala/área: proyector, teléfono, impresora, pantalla interactiva, etc."""
    subgrupo = models.ForeignKey(Subgrupo, on_delete=models.PROTECT, related_name='dispositivos')
    tipo = models.ForeignKey(TipoPeriferico, on_delete=models.PROTECT)
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, null=True, blank=True)
    ip = models.CharField(max_length=45, blank=True, verbose_name='Dirección IP')
    extension = models.CharField(max_length=20, blank=True, verbose_name='Extensión')
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dispositivo'
        verbose_name_plural = 'Dispositivos'
        ordering = ['subgrupo__grupo__nombre', 'subgrupo__nombre', 'tipo__nombre']

    def __str__(self):
        marca = f' {self.marca.nombre}' if self.marca_id else ''
        return f'{self.tipo.nombre}{marca} — {self.subgrupo}'


# ============================================================
# HELPERS DE ACCESO POR SEDE
# ============================================================

def sedes_permitidas(user):
    """Devuelve queryset de Sedes visibles para el usuario.
    Superusuario/staff → todas. Usuario normal → solo sus sedes asignadas."""
    if user.is_superuser or user.is_staff:
        return Sede.objects.all()
    if hasattr(user, 'persona'):
        return user.persona.sedes.all()
    return Sede.objects.none()