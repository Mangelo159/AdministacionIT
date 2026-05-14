from .models import Requerimiento


def mis_reqs_pendientes(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'persona'):
        return {'mis_reqs_pendientes': 0}
    count = Requerimiento.objects.filter(
        tecnico=request.user.persona,
        estado__es_final=False,
    ).count()
    return {'mis_reqs_pendientes': count}
