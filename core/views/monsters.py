from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, render

from core.models import (
    ELEMENT_TYPES,
    STATUS_TYPES,
    Monster,
    MonsterWeakness,
    Skill,
)

# Elementos + estados usados como filtros de debilidad.
WEAKNESS_FILTER_CHOICES = ELEMENT_TYPES + STATUS_TYPES


def monster_list(request):
    """Bestiario con búsqueda en tiempo real (HTMX) y filtros."""
    queryset = Monster.objects.all().prefetch_related("weaknesses")

    filters = {}

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(species__icontains=q)
        )
        filters["q"] = q

    weakness = request.GET.get("weakness", "")
    if weakness:
        # Anotamos el nivel de debilidad al elemento filtrado para poder
        # ordenar de mayor a menor debilidad.
        queryset = queryset.filter(weaknesses__element=weakness).annotate(
            weakness_stars=Max(
                "weaknesses__stars", filter=Q(weaknesses__element=weakness)
            )
        )
        filters["weakness"] = weakness

    monster_type = request.GET.get("type", "")
    if monster_type in ("large", "small"):
        queryset = queryset.filter(type=monster_type)
        filters["type"] = monster_type

    order_by = ("-weakness_stars", "name") if weakness else ("name",)
    monsters = list(queryset.order_by(*order_by))

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
    """Detalle: debilidades, resistencias, estados, ubicaciones, hitzones y drops."""
    monster = get_object_or_404(
        Monster.objects.prefetch_related(
            "weaknesses",
            "resistances",
            "ailments",
            "locations",
            "hitzones",
            "rewards__item",
        ),
        pk=pk,
    )
    rewards = list(monster.rewards.select_related("item").order_by("item__name"))

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
            "rewards": rewards,
        },
    )


def skill_list(request):
    """Librería de habilidades: lista con búsqueda y filtro por max_level."""
    queryset = Skill.objects.all().order_by("name")

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(name__icontains=q)

    max_level = request.GET.get("max_level", "")
    if max_level.isdigit():
        queryset = queryset.filter(max_level=int(max_level))

    skills = list(queryset)

    context = {
        "skills": skills,
        "q": q,
        "max_level": max_level,
        "max_level_choices": range(1, 8),
    }

    if request.htmx:
        return render(request, "core/partials/skill_list.html", context)
    return render(request, "core/skills.html", context)
