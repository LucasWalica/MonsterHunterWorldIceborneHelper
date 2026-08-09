from django.shortcuts import render

from core.models import Armor, Charm, Decoration, Skill
from core.services.optimizer import SLOT_ORDER, find_sets, total_skills


def charm_search(request):
    """Autocompletado de amuletos: coincidencias de nombre."""
    q = request.GET.get("q", "").strip()
    charms = []
    if q:
        charms = list(
            Charm.objects.filter(name__icontains=q)
            .prefetch_related("charm_skills__skill")
            .order_by("name")[:20]
        )
    context = {"charms": charms, "q": q}
    return render(request, "core/partials/charm_suggestions.html", context)


def decoration_search(request):
    """Autocompletado de joyas: coincidencias de nombre que encajen en la ranura.

    Con ``q`` vacío y ``limit`` alto devuelve todas las joyas que caben en la
    ranura (agrupadas por talla) para el modal del set builder.
    """
    q = request.GET.get("q", "").strip()
    try:
        max_slot = int(request.GET.get("max_slot", 99))
    except (TypeError, ValueError):
        max_slot = 99
    try:
        limit = min(max(int(request.GET.get("limit", 20)), 1), 500)
    except (TypeError, ValueError):
        limit = 20

    queryset = Decoration.objects.filter(slot__lte=max_slot)
    if q:
        decorations = list(
            queryset.filter(name__icontains=q)
            .prefetch_related("decoration_skills__skill")
            .order_by("slot", "name")[:limit]
        )
    else:
        decorations = list(
            queryset.prefetch_related("decoration_skills__skill")
            .order_by("slot", "-rarity", "name")[:limit]
        )
    context = {
        "decorations": decorations,
        "q": q,
        "slot": request.GET.get("slot", ""),
    }
    return render(request, "core/partials/decoration_suggestions.html", context)


def armor_picker(request):
    """Modal del set builder: lista de armaduras de un slot con sus ranuras."""
    slot = request.GET.get("slot", "")
    if slot not in SLOT_ORDER:
        slot = "head"
    q = request.GET.get("q", "").strip()
    armors = Armor.objects.filter(type=slot).prefetch_related("armor_skills__skill")
    if q:
        armors = armors.filter(name__icontains=q)
    armors = armors.order_by("rank", "-defense_max", "name")
    context = {"slot": slot, "armors": armors, "q": q}
    return render(request, "core/partials/armor_picker_list.html", context)


def _selected_pieces(request):
    """Devuelve (selected_ids, pieces) para los 5 slots."""
    selected = {}
    for slot in SLOT_ORDER:
        value = request.GET.get(slot, "")
        if value.isdigit():
            selected[slot] = int(value)
    pieces = []
    if selected:
        by_id = {
            armor.pk: armor
            for armor in Armor.objects.filter(pk__in=selected.values())
        }
        pieces = [by_id[pk] for pk in selected.values() if pk in by_id]
    return selected, pieces


def _selected_accessories(request):
    """Joyas por ranura física (una por slot de cada pieza) y amuleto.

    Los parámetros llegan como ``decohead-0``, ``decohead-1``, ... donde el
    índice es la posición dentro de ``piece.slots`` (una pieza puede tener
    varias ranuras, p.ej. ``[4, 1]``).
    """
    deco_selected = {}
    for slot in SLOT_ORDER:
        for index in range(5):
            key = f"{slot}-{index}"
            value = request.GET.get(f"deco{key}", "")
            if value.isdigit():
                try:
                    deco_selected[key] = Decoration.objects.get(pk=int(value))
                except Decoration.DoesNotExist:
                    continue

    charm = None
    charm_value = request.GET.get("charm", "")
    if charm_value.isdigit():
        try:
            charm = Charm.objects.get(pk=int(charm_value))
        except Charm.DoesNotExist:
            pass
    return deco_selected, charm


def _set_builder_context(request):
    selected, pieces = _selected_pieces(request)
    deco_selected, charm = _selected_accessories(request)

    armor_by_slot = {}
    for slot in SLOT_ORDER:
        armor_by_slot[slot] = Armor.objects.filter(type=slot).only(
            "id", "name", "rank", "defense_max"
        ).order_by("rank", "-defense_max", "name")

    totals = total_skills(pieces)
    for deco in deco_selected.values():
        for deco_skill in deco.decoration_skills.all():
            name = deco_skill.skill.name
            totals[name] = totals.get(name, 0) + deco_skill.level
    if charm:
        for charm_skill in charm.charm_skills.all():
            name = charm_skill.skill.name
            totals[name] = totals.get(name, 0) + charm_skill.level

    return {
        "armor_by_slot": armor_by_slot,
        "selected": selected,
        "pieces": pieces,
        "piece_by_slot": {piece.type: piece for piece in pieces},
        "decorations": Decoration.objects.order_by("slot", "name"),
        "charms": Charm.objects.order_by("name"),
        "deco_selected": deco_selected,
        "charm_selected": charm,
        "totals": sorted(totals.items(), key=lambda item: -item[1]),
        "total_defense": sum(piece.defense_max for piece in pieces),
        "total_slots": sum(len(piece.slots) for piece in pieces),
    }


def set_builder(request):
    """Simulador de equipamiento: piezas + joyas + amuleto."""
    context = _set_builder_context(request)

    if request.htmx:
        return render(request, "core/partials/set_builder_content.html", context)

    context["skills_choices"] = Skill.objects.order_by("name")
    return render(request, "core/set_builder.html", context)


def optimize(request):
    """Optimizador: busca sets que cumplan las habilidades deseadas."""
    desired = {}
    for i in (1, 2, 3):
        name = request.GET.get(f"skill{i}_name", "").strip()
        level = request.GET.get(f"skill{i}_level", "")
        if name and level.isdigit() and int(level) > 0:
            desired[name] = int(level)

    rank = request.GET.get("rank", "master")
    if rank not in ("low", "high", "master"):
        rank = "master"

    sets = find_sets(desired, rank=rank) if desired else []

    sets_data = []
    for pieces in sets:
        sets_data.append(
            {
                "pieces": pieces,
                "by_slot": {armor.type: armor for armor in pieces},
                "defense": sum(piece.defense_max for piece in pieces),
                "slots": sum(len(piece.slots) for piece in pieces),
                "totals": sorted(
                    total_skills(pieces).items(), key=lambda item: -item[1]
                ),
            }
        )

    context = {
        "sets": sets_data,
        "desired": desired,
        "rank": rank,
    }
    return render(request, "core/partials/optimizer_results.html", context)
