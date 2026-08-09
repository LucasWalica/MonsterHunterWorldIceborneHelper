from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from core.models import (
    ELEMENT_TYPES,
    STATUS_TYPES,
    Monster,
    MonsterWeakness,
)

# Elementos + estados usados como filtros de debilidad.
WEAKNESS_FILTER_CHOICES = ELEMENT_TYPES + STATUS_TYPES


def monster_list(request):
    """Bestiario con búsqueda en tiempo real (HTMX) y filtros."""
    queryset = Monster.objects.all()

    filters = {}

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(species__icontains=q)
        )
        filters["q"] = q

    weakness = request.GET.get("weakness", "")
    if weakness:
        queryset = queryset.filter(weaknesses__element=weakness).distinct()
        filters["weakness"] = weakness

    monster_type = request.GET.get("type", "")
    if monster_type in ("large", "small"):
        queryset = queryset.filter(type=monster_type)
        filters["type"] = monster_type

    monsters = list(queryset.order_by("name"))

    context = {
        "monsters": monsters,
        "count": len(monsters),
        "filters": filters,
        "weakness_choices": WEAKNESS_FILTER_CHOICES,
    }

    if request.htmx:
        return render(request, "core/partials/monster_list.html", context)
    return render(request, "core/monsters.html", context)


def monster_detail(request, pk):
    """Detalle: debilidades, resistencias, estados, ubicaciones y hitzones."""
    monster = get_object_or_404(
        Monster.objects.prefetch_related(
            "weaknesses", "resistances", "ailments", "locations", "hitzones"
        ),
        pk=pk,
    )
    return render(
        request,
        "core/monster_detail.html",
        {
            "monster": monster,
            "elemental_weaknesses": [
                w for w in monster.weaknesses.all()
                if w.element in dict(ELEMENT_TYPES)
            ],
            "status_weaknesses": [
                w for w in monster.weaknesses.all()
                if w.element in dict(STATUS_TYPES)
            ],
            "element_types": dict(ELEMENT_TYPES),
        },
    )
