"""Optimizador de equipamiento (Set Builder / Armor Optimizer).

Busca combinaciones de 5 piezas de armadura (cabeza, pecho, brazos,
cintura, piernas) que sumen las habilidades deseadas por el usuario.

Estrategia:
  1. Solo se consideran piezas que aportan al menos una habilidad deseada.
  2. Búsqueda por profundidad con poda y un presupuesto máximo de estados
     para que el algoritmo termine en tiempo razonable.
  3. Los sets encontrados se ordenan por defensa total y ranuras.
"""

from collections import defaultdict

from core.models import Armor

SLOT_ORDER = ("head", "chest", "gloves", "waist", "legs")

DEFAULT_MAX_SETS = 8
DEFAULT_MAX_STATES = 20_000


def find_sets(
    desired,
    *,
    rank="master",
    max_sets=DEFAULT_MAX_SETS,
    max_states=DEFAULT_MAX_STATES,
):
    """Devuelve una lista de sets (5 objetos ``Armor``) que cumplen
    ``desired`` (dict nombre_habilidad -> nivel requerido)."""
    desired = {name: int(level) for name, level in desired.items() if int(level) > 0}
    if not desired:
        return []

    armors = (
        Armor.objects.filter(rank=rank)
        .prefetch_related("armor_skills__skill")
        .order_by("id")
    )

    candidates = defaultdict(list)
    for armor in armors:
        gains = {
            asp.skill.name: asp.level
            for asp in armor.armor_skills.all()
            if asp.skill.name in desired
        }
        if gains:
            candidates[armor.type].append(
                {
                    "armor": armor,
                    "gains": gains,
                    "usefulness": sum(gains.values()),
                }
            )

    if not all(candidates[slot] for slot in SLOT_ORDER):
        return []

    # Las piezas más útiles primero, luego las de más defensa.
    for slot in SLOT_ORDER:
        candidates[slot].sort(
            key=lambda c: (-c["usefulness"], -c["armor"].defense_max)
        )

    results = []
    states = 0

    def dfs(index, chosen, remaining):
        nonlocal states
        if index == len(SLOT_ORDER):
            if all(level <= 0 for level in remaining.values()):
                results.append(list(chosen))
            return

        states += 1
        if states > max_states:
            return

        slot = SLOT_ORDER[index]
        is_last = index == len(SLOT_ORDER) - 1
        for candidate in candidates[slot]:
            gains = candidate["gains"]
            new_remaining = {
                name: max(0, level - gains.get(name, 0))
                for name, level in remaining.items()
            }
            if is_last and any(new_remaining.values()):
                continue
            chosen.append(candidate["armor"])
            dfs(index + 1, chosen, new_remaining)
            chosen.pop()

    dfs(0, [], dict(desired))

    results.sort(
        key=lambda s: (
            -sum(a.defense_max for a in s),
            -sum(len(a.slots) for a in s),
            -sum(a.rarity for a in s),
        )
    )
    return results[:max_sets]


def total_skills(armors):
    """Suma los niveles de habilidad de un conjunto de piezas."""
    totals = defaultdict(int)
    for armor in armors:
        for asp in armor.armor_skills.all():
            totals[asp.skill.name] += asp.level
    return dict(totals)
