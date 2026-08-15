from django.shortcuts import get_object_or_404, render

from core.models import Armor, Item, Weapon


def weapon_detail(request, pk):
    """Detalle de arma + árbol de forja (cadena anterior y ramas)."""
    weapon = get_object_or_404(
        Weapon.objects.select_related("previous").prefetch_related(
            "crafting_materials__item__monster_rewards__monster"
        ),
        pk=pk,
    )

    chain = []
    node = weapon
    seen = set()
    while node is not None and node.pk not in seen:
        seen.add(node.pk)
        chain.insert(0, node)
        node = node.previous

    materials = weapon.crafting_materials.select_related("item").order_by("kind")

    return render(
        request,
        "core/weapon_detail.html",
        {
            "weapon": weapon,
            "chain": chain,
            "branches": weapon.branches.all()[:24],
            "materials": materials,
            "materials_kinds": [("forge", "Forge"), ("upgrade", "Upgrade")],
        },
    )


def armor_detail(request, pk):
    """Detalle de pieza de armadura + materiales de forja."""
    armor = get_object_or_404(
        Armor.objects.prefetch_related(
            "armor_skills__skill",
            "crafting_materials__item__monster_rewards__monster",
        ),
        pk=pk,
    )
    return render(
        request,
        "core/armor_detail.html",
        {
            "armor": armor,
            "materials": armor.crafting_materials.select_related("item"),
            "resistances": [
                ("Fire", armor.resist_fire),
                ("Water", armor.resist_water),
                ("Thunder", armor.resist_thunder),
                ("Ice", armor.resist_ice),
                ("Dragon", armor.resist_dragon),
            ],
        },
    )


def item_detail(request, pk):
    """Detalle de item + monstruos que lo sueltan (dropean)."""
    item = get_object_or_404(Item, pk=pk)
    rewards = (
        item.monster_rewards.select_related("monster")
        .order_by("monster__name")
        .all()
    )
    return render(
        request,
        "core/item_detail.html",
        {"item": item, "rewards": rewards},
    )


def item_search(request):
    """Buscador de items/materiales (HTMX)."""
    q = request.GET.get("q", "").strip()
    items = []
    if q:
        items = list(
            Item.objects.filter(name__icontains=q)
            .order_by("name")[:50]
        )
    context = {"items": items, "q": q}
    if request.htmx:
        return render(request, "core/partials/item_search_results.html", context)
    return render(request, "core/item_search.html", context)
