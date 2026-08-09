from django.db import connection
from django.shortcuts import render

from core.models import (
    ELEMENT_TYPES,
    SHARPNESS_ORDER,
    STATUS_TYPES,
    WEAPON_TYPES,
    Weapon,
)

ELEMENT_FILTER_CHOICES = ELEMENT_TYPES + STATUS_TYPES

SORT_OPTIONS = {
    "name": "name",
    "attack": "-attack_display",
    "affinity": "-affinity",
    "rarity": "-rarity",
}


def weapon_list(request):
    """Lista y filtro de armas. Con HTMX devuelve solo el partial."""
    queryset = Weapon.objects.all()

    filters = {}

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(name__icontains=q)
        filters["q"] = q

    weapon_type = request.GET.get("type", "")
    if weapon_type in dict(WEAPON_TYPES):
        queryset = queryset.filter(weapon_type=weapon_type)
        filters["type"] = weapon_type

    element = request.GET.get("element", "")
    if element:
        if connection.vendor == "postgresql":
            queryset = queryset.filter(elements__contains=[{"type": element}])
        else:
            # SQLite no soporta el contains JSON: filtramos en Python.
            ids = [
                weapon.pk
                for weapon in queryset
                if any(el.get("type") == element for el in weapon.elements)
            ]
            queryset = Weapon.objects.filter(pk__in=ids)
        filters["element"] = element

    min_attack = request.GET.get("min_attack", "")
    if min_attack.isdigit():
        queryset = queryset.filter(attack_display__gte=int(min_attack))
        filters["min_attack"] = min_attack

    sharpness = request.GET.get("sharpness", "")
    if sharpness in SHARPNESS_ORDER:
        queryset = queryset.filter(**{f"sharpness__{sharpness}__gt": 0})
        filters["sharpness"] = sharpness

    slots = request.GET.get("slots", "")
    if slots.isdigit() and int(slots) > 0:
        queryset = queryset.filter(slots__len__gte=int(slots))
        filters["slots"] = slots

    sort = SORT_OPTIONS.get(request.GET.get("sort", ""), SORT_OPTIONS["name"])
    if sort != "name":
        queryset = queryset.order_by(sort, "name")

    weapons = list(queryset[:300])

    context = {
        "weapons": weapons,
        "count": len(weapons),
        "total": queryset.count(),
        "filters": filters,
        "weapon_types": WEAPON_TYPES,
        "element_choices": ELEMENT_FILTER_CHOICES,
        "sharpness_choices": SHARPNESS_ORDER,
    }

    if request.htmx:
        return render(request, "core/partials/weapon_list.html", context)
    return render(request, "core/weapons.html", context)
