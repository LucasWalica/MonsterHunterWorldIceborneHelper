from django.shortcuts import get_object_or_404, render

from core.models import Armor, Item, Weapon


def weapon_detail(request, pk):
    """Detalle de arma + árbol de forja (cadena anterior y ramas)."""
    weapon = get_object_or_404(
        Weapon.objects.select_related("previous"), pk=pk
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
        Armor.objects.prefetch_related("armor_skills__skill"), pk=pk
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
