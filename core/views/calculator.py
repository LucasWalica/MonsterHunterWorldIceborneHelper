from django.shortcuts import render

from core.models import SHARPNESS_ORDER, WEAPON_TYPES, Weapon
from core.services.efr import calculate_efr

SKILL_MAX_LEVELS = {
    "attack_boost": 7,
    "agitator": 7,
    "critical_eye": 7,
    "weakness_exploit": 3,
    "maximum_might": 3,
    "peak_performance": 3,
    "resentment": 5,
    "elemental_attack": 6,
}

MOTION_VALUES = [
    ("MV 0.4", 40),
    ("MV 0.7", 70),
    ("MV 1.0 (basic hit)", 100),
    ("MV 1.4", 140),
    ("MV 1.7", 170),
]


def _int_param(request, name, default):
    try:
        return int(request.GET.get(name, ""))
    except (TypeError, ValueError):
        return default


def weapon_search(request):
    """Autocompletado de armas: devuelve coincidencias de nombre para el buscador."""
    q = request.GET.get("q", "").strip()
    weapons = []
    if q:
        weapons = list(
            Weapon.objects.filter(name__icontains=q)
            .order_by("weapon_type", "name")[:20]
        )
    context = {"weapons": weapons, "q": q}
    return render(request, "core/partials/weapon_suggestions.html", context)


def efr_calculator(request):
    weapon = None
    weapon_id = request.GET.get("weapon", "")
    if weapon_id:
        try:
            weapon = Weapon.objects.get(pk=int(weapon_id))
        except (Weapon.DoesNotExist, ValueError):
            weapon = None

    sharpness = request.GET.get("sharpness", "")
    result = None

    if weapon:
        available = [
            color for color in SHARPNESS_ORDER if weapon.sharpness.get(color)
        ]
        if not available:
            available = list(SHARPNESS_ORDER)
        if sharpness not in available:
            sharpness = available[-1]

        skills = {
            "attack_boost": _int_param(request, "attack_boost", 0),
            "agitator": _int_param(request, "agitator", 0),
            "agitator_active": request.GET.get("agitator_active") == "on",
            "critical_eye": _int_param(request, "critical_eye", 0),
            "weakness_exploit": _int_param(request, "weakness_exploit", 0),
            "maximum_might": _int_param(request, "maximum_might", 0),
            "peak_performance": _int_param(request, "peak_performance", 0),
            "resentment": _int_param(request, "resentment", 0),
            "elemental_attack": _int_param(request, "elemental_attack", 0),
        }
        affinity = request.GET.get("affinity", "").strip() or None
        hitzone_raw = _int_param(request, "hitzone_raw", 60)
        hitzone_elem = _int_param(request, "hitzone_elem", 30)
        motion_value = _int_param(request, "motion_value", 100) / 100.0

        result = calculate_efr(
            weapon,
            sharpness=sharpness,
            affinity_override=affinity,
            skills=skills,
            sample_hitzone=(hitzone_raw, hitzone_elem),
            motion_value=motion_value,
        )
    else:
        available = list(SHARPNESS_ORDER)

    values = {
        "attack_boost": _int_param(request, "attack_boost", 0),
        "agitator": _int_param(request, "agitator", 0),
        "agitator_active": request.GET.get("agitator_active") == "on",
        "critical_eye": _int_param(request, "critical_eye", 0),
        "weakness_exploit": _int_param(request, "weakness_exploit", 0),
        "maximum_might": _int_param(request, "maximum_might", 0),
        "peak_performance": _int_param(request, "peak_performance", 0),
        "resentment": _int_param(request, "resentment", 0),
        "elemental_attack": _int_param(request, "elemental_attack", 0),
        "affinity": request.GET.get("affinity", ""),
        "hitzone_raw": _int_param(request, "hitzone_raw", 60),
        "hitzone_elem": _int_param(request, "hitzone_elem", 30),
        "motion_value": _int_param(request, "motion_value", 100),
    }

    context = {
        "weapon": weapon,
        "sharpness": sharpness,
        "available_sharpness": available,
        "result": result,
        "skill_max_levels": SKILL_MAX_LEVELS,
        "motion_values": MOTION_VALUES,
        "values": values,
    }

    template = "core/partials/efr_result.html"
    if request.htmx:
        return render(request, template, context)
    return render(request, "core/calculator.html", context)
