"""Calculadora EFR (Effective Raw) de Monster Hunter World.

Fórmulas base del juego (MHW base / Iceborne simplificado):

  EFR raw = (RawReal + BonusRawHabilidades) * MultiplicadorAfilado * FactorAfinidad
  FactorAfinidad = 1 + (Afinidad% / 100) * (CRITICAL_MULTIPLIER - 1)

  Elemento: el valor de la API es el "display" (ej. 240); el valor real se
  obtiene dividiendo entre 10.

  EFR elemental = (ElementoTrue + BonusHabilidadElemento) * MultiplicadorAfiladoElem

Valores de habilidades según datos oficiales. Las habilidades elementales
se simplifican a una subida lineal (Fire Attack, Ice Attack, ...).
"""

from dataclasses import dataclass

from core.models import (
    CRITICAL_MULTIPLIER,
    SHARPNESS_ELEMENTAL_MULTIPLIER,
    SHARPNESS_RAW_MULTIPLIER,
)

# --- Bonus de Raw por nivel de habilidad ---
ATTACK_BOOST_RAW = {0: 0, 1: 3, 2: 6, 3: 9, 4: 12, 5: 15, 6: 18, 7: 21}
ATTACK_BOOST_AFFINITY = {1: 0, 2: 0, 3: 0, 4: 5, 5: 5, 6: 5, 7: 5}

AGITATOR_RAW = {0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 7: 28}
AGITATOR_AFFINITY = {0: 0, 1: 3, 2: 5, 3: 7, 4: 10, 5: 15, 6: 20, 7: 20}

PEAK_PERFORMANCE_RAW = {0: 0, 1: 5, 2: 10, 3: 20}
RESENTMENT_RAW = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20, 5: 20}

CRITICAL_EYE_AFFINITY = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20, 5: 25, 6: 30, 7: 40}
WEAKNESS_EXPLOIT_AFFINITY = {0: 0, 1: 15, 2: 30, 3: 50}
MAXIMUM_MIGHT_AFFINITY = {0: 0, 1: 10, 2: 20, 3: 30}

# Subida de elemento por nivel (simplificada, sobre el valor display).
ELEMENT_ATTACK_BOOST = {0: 0, 1: 30, 2: 60, 3: 100, 4: 120, 5: 140, 6: 160}

# Value que divide el elemento display para obtener el true element.
ELEMENT_TRUE_DIVISOR = 10

# Hitzones de ejemplo para la estimación de daño por golpe.
DEFAULT_HITZONE_RAW = 60
DEFAULT_HITZONE_ELEM = 30
DEFAULT_MOTION_VALUE = 1.0


@dataclass
class EFRResult:
    """Resultado calculado para un arma y configuración de habilidades."""

    weapon_name: str
    base_raw: int
    raw_after_skills: int
    affinity: int
    affinity_from_skills: int
    sharpness: str
    sharpness_raw_mult: float
    sharpness_elem_mult: float
    effective_raw: float
    elements: list
    effective_element_total: float
    estimated_raw_hit: float
    estimated_element_hit: float
    motion_value: float
    hitzone_raw: int
    hitzone_elem: int

    @property
    def estimated_total_hit(self):
        return self.estimated_raw_hit + self.estimated_element_hit


def _skill_level(skills, key):
    value = skills.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def calculate_efr(
    weapon,
    *,
    sharpness,
    affinity_override=None,
    skills=None,
    sample_hitzone=(DEFAULT_HITZONE_RAW, DEFAULT_HITZONE_ELEM),
    motion_value=DEFAULT_MOTION_VALUE,
):
    """Calcula el EFR de un arma.

    - ``weapon``: instancia de core.models.Weapon.
    - ``sharpness``: color de afilado (red/orange/yellow/green/blue/white/purple).
    - ``affinity_override``: afinidad % forzada por el usuario (si se define).
    - ``skills``: dict con niveles, p.ej.
        {"attack_boost": 7, "agitator": 5, "agitator_active": True,
         "critical_eye": 3, "weakness_exploit": 3, "maximum_might": 2,
         "peak_performance": 1, "resentment": 0, "elemental_attack": 3}
    """
    skills = skills or {}

    attack_boost = _skill_level(skills, "attack_boost")
    agitator = _skill_level(skills, "agitator")
    agitator_active = bool(skills.get("agitator_active"))
    critical_eye = _skill_level(skills, "critical_eye")
    weakness_exploit = _skill_level(skills, "weakness_exploit")
    maximum_might = _skill_level(skills, "maximum_might")
    peak_performance = _skill_level(skills, "peak_performance")
    resentment = _skill_level(skills, "resentment")
    elemental_attack = _skill_level(skills, "elemental_attack")

    # --- Afinidad total ---
    affinity = weapon.affinity
    if affinity_override is not None:
        try:
            affinity = int(affinity_override)
        except (TypeError, ValueError):
            pass

    affinity_from_skills = 0
    affinity_from_skills += ATTACK_BOOST_AFFINITY.get(attack_boost, 0)
    if agitator_active:
        affinity_from_skills += AGITATOR_AFFINITY.get(agitator, 0)
    affinity_from_skills += CRITICAL_EYE_AFFINITY.get(critical_eye, 0)
    affinity_from_skills += WEAKNESS_EXPLOIT_AFFINITY.get(weakness_exploit, 0)
    affinity_from_skills += MAXIMUM_MIGHT_AFFINITY.get(maximum_might, 0)
    affinity += affinity_from_skills
    affinity = min(max(affinity, -100), 100)

    # --- Raw tras habilidades ---
    raw = weapon.attack_raw
    raw += ATTACK_BOOST_RAW.get(attack_boost, 0)
    if agitator_active:
        raw += AGITATOR_RAW.get(agitator, 0)
    raw += PEAK_PERFORMANCE_RAW.get(peak_performance, 0)
    raw += RESENTMENT_RAW.get(resentment, 0)

    sharpness_raw_mult = SHARPNESS_RAW_MULTIPLIER.get(sharpness, 1.0)
    sharpness_elem_mult = SHARPNESS_ELEMENTAL_MULTIPLIER.get(sharpness, 1.0)

    affinity_factor = 1 + (affinity / 100.0) * (CRITICAL_MULTIPLIER - 1)
    effective_raw = raw * sharpness_raw_mult * affinity_factor

    # --- Elementos ---
    elements = []
    for element in weapon.elements:
        base_damage = element.get("damage", 0)
        if not base_damage:
            continue
        boosted = base_damage + ELEMENT_ATTACK_BOOST.get(elemental_attack, 0)
        true_value = boosted / ELEMENT_TRUE_DIVISOR
        effective = true_value * sharpness_elem_mult
        elements.append(
            {
                "type": element.get("type", ""),
                "base": base_damage,
                "boosted": boosted,
                "true_value": true_value,
                "effective": effective,
                "hidden": element.get("hidden", False),
            }
        )
    effective_element_total = sum(el["effective"] for el in elements)

    hitzone_raw, hitzone_elem = sample_hitzone
    estimated_raw_hit = effective_raw * motion_value * hitzone_raw / 100.0
    estimated_element_hit = (
        effective_element_total * motion_value * hitzone_elem / 100.0
    )

    return EFRResult(
        weapon_name=weapon.name,
        base_raw=weapon.attack_raw,
        raw_after_skills=raw,
        affinity=affinity,
        affinity_from_skills=affinity_from_skills,
        sharpness=sharpness,
        sharpness_raw_mult=sharpness_raw_mult,
        sharpness_elem_mult=sharpness_elem_mult,
        effective_raw=effective_raw,
        elements=elements,
        effective_element_total=effective_element_total,
        estimated_raw_hit=estimated_raw_hit,
        estimated_element_hit=estimated_element_hit,
        motion_value=motion_value,
        hitzone_raw=hitzone_raw,
        hitzone_elem=hitzone_elem,
    )
