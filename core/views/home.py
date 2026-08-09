from django.http import HttpResponse
from django.shortcuts import render

from core.models import Armor, Monster, Skill, Weapon


def home(request):
    """Página de inicio con estadísticas de la base de datos."""
    context = {
        "monster_count": Monster.objects.count(),
        "weapon_count": Weapon.objects.count(),
        "armor_count": Armor.objects.count(),
        "skill_count": Skill.objects.count(),
    }
    return render(request, "core/index.html", context)


def ping(request):
    """Endpoint de prueba para verificar que HTMX responde sin recargar."""
    return HttpResponse("Pong · respuesta del servidor vía HTMX")
