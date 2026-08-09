"""Modelos de datos del universo Monster Hunter World: Iceborne.

Los modelos están diseñados para soportar:
  1. Calculadora EFR (Effective Raw).
  2. Simulador/optimizador de equipamiento (Set Builder).
  3. Guía de monstruos con hitzones y debilidades.
  4. Árbol de forja y materiales (crafting tree).
  5. Buscador/filtro dinámico de armas.

El ETL (management/commands/etl_mhw_data.py) puebla estas tablas desde
la API pública de https://mhw-db.com/.
"""

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

# ---------------------------------------------------------------------------
# Constantes compartidas
# ---------------------------------------------------------------------------

ELEMENT_TYPES = (
    ("fire", "Fire"),
    ("water", "Water"),
    ("thunder", "Thunder"),
    ("ice", "Ice"),
    ("dragon", "Dragon"),
)

STATUS_TYPES = (
    ("poison", "Poison"),
    ("paralysis", "Paralysis"),
    ("sleep", "Sleep"),
    ("blast", "Blast"),
    ("stun", "Stun"),
)

# mhw-db devuelve en "weaknesses" tanto elementos como estados.
WEAKNESS_KINDS = ELEMENT_TYPES + STATUS_TYPES

WEAPON_TYPES = (
    ("great-sword", "Great Sword"),
    ("long-sword", "Long Sword"),
    ("sword-and-shield", "Sword & Shield"),
    ("dual-blades", "Dual Blades"),
    ("hammer", "Hammer"),
    ("hunting-horn", "Hunting Horn"),
    ("lance", "Lance"),
    ("gunlance", "Gunlance"),
    ("switch-axe", "Switch Axe"),
    ("charge-blade", "Charge Blade"),
    ("insect-glaive", "Insect Glaive"),
    ("light-bowgun", "Light Bowgun"),
    ("heavy-bowgun", "Heavy Bowgun"),
    ("bow", "Bow"),
)

DAMAGE_TYPES = (
    ("sever", "Sever"),
    ("blunt", "Blunt"),
    ("ammo", "Ammo"),
)

ARMOR_SLOTS = (
    ("head", "Head"),
    ("chest", "Chest"),
    ("gloves", "Arms"),
    ("waist", "Waist"),
    ("legs", "Legs"),
)

ARMOR_RANKS = (
    ("low", "Low Rank"),
    ("high", "High Rank"),
    ("master", "Master Rank"),
)

MONSTER_TYPES = (
    ("large", "Large"),
    ("small", "Small"),
)

# Orden visual del afilado (de peor a mejor).
SHARPNESS_ORDER = ("red", "orange", "yellow", "green", "blue", "white", "purple")

# Factores de afilado para la calculadora EFR (raw / elemental).
# Referencia: bludgeoner y mecánicas oficiales de MHW.
SHARPNESS_RAW_MULTIPLIER = {
    "red": 0.50,
    "orange": 0.75,
    "yellow": 1.00,
    "green": 1.05,
    "blue": 1.20,
    "white": 1.32,
    "purple": 1.39,
}
SHARPNESS_ELEMENTAL_MULTIPLIER = {
    "red": 0.25,
    "orange": 0.50,
    "yellow": 0.75,
    "green": 1.00,
    "blue": 1.0625,
    "white": 1.125,
    "purple": 1.20,
}
CRITICAL_MULTIPLIER = 1.25


class Location(models.Model):
    """Mapa / ecosistema donde aparece un monstruo."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100)
    zone_count = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Monster(models.Model):
    """Monstruo del bestiario (grandes y pequeños)."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    type = models.CharField(max_length=20, choices=MONSTER_TYPES, default="large")
    species = models.CharField(max_length=100, blank=True, default="", db_index=True)
    description = models.TextField(blank=True, default="")
    locations = models.ManyToManyField(Location, related_name="monsters", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def element_weaknesses(self):
        return self.weaknesses.filter(
            element__in=[e[0] for e in ELEMENT_TYPES]
        ).order_by("-stars")

    @property
    def status_weaknesses(self):
        return self.weaknesses.filter(
            element__in=[s[0] for s in STATUS_TYPES]
        ).order_by("-stars")


class MonsterWeakness(models.Model):
    """Debilidad a un elemento o estado (estrellas 0-3).

    mhw-db mezcla en un único array elementos y estados: el campo
    ``element`` guarda el nombre exacto que devuelve la API
    (fire, water, ..., poison, sleep, ...).
    """

    monster = models.ForeignKey(
        Monster, on_delete=models.CASCADE, related_name="weaknesses"
    )
    element = models.CharField(max_length=20, db_index=True)
    stars = models.PositiveSmallIntegerField(default=0)
    condition = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-stars"]
        constraints = [
            models.UniqueConstraint(
                fields=["monster", "element", "condition"],
                name="uniq_monster_element_weakness",
            )
        ]

    def __str__(self):
        return f"{self.monster} - {self.element} ({self.stars}★)"


class MonsterResistance(models.Model):
    """Resistencia elemental (estrellas)."""

    monster = models.ForeignKey(
        Monster, on_delete=models.CASCADE, related_name="resistances"
    )
    element = models.CharField(max_length=20, db_index=True)
    stars = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["element"]

    def __str__(self):
        return f"{self.monster} resiste {self.element} ({self.stars}★)"


class MonsterAilment(models.Model):
    """Estado alterado que inflige el monstruo (Fuego, Veneno, ...)."""

    monster = models.ForeignKey(
        Monster, on_delete=models.CASCADE, related_name="ailments"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.monster} - {self.name}"


class MonsterReward(models.Model):
    """Item que suelta un monstruo con sus condiciones (carve/reward/...).

    Las condiciones (tipo, rango, cantidad y probabilidad) se guardan como
    JSON para no acoplar el esquema al formato de mhw-db.
    """

    monster = models.ForeignKey(
        Monster, on_delete=models.CASCADE, related_name="rewards"
    )
    item = models.ForeignKey(
        "Item", on_delete=models.CASCADE, related_name="monster_rewards"
    )
    conditions = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["monster", "item"]

    def __str__(self):
        return f"{self.monster} -> {self.item}"


class Hitzone(models.Model):
    """Zona corporal del monstruo y % de daño recibido por tipo.

    Valores 0-100 (100 = daño completo). mhw-db NO proporciona estos datos,
    por lo que se dejan para ser sembrados con datos de la comunidad.
    """

    monster = models.ForeignKey(
        Monster, on_delete=models.CASCADE, related_name="hitzones"
    )
    part = models.CharField(max_length=100, db_index=True)
    cut = models.PositiveSmallIntegerField(default=0, verbose_name="Corte")
    impact = models.PositiveSmallIntegerField(default=0, verbose_name="Impacto")
    shot = models.PositiveSmallIntegerField(default=0, verbose_name="Disparo")
    fire = models.PositiveSmallIntegerField(default=0)
    water = models.PositiveSmallIntegerField(default=0)
    thunder = models.PositiveSmallIntegerField(default=0)
    ice = models.PositiveSmallIntegerField(default=0)
    dragon = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["part"]
        constraints = [
            models.UniqueConstraint(
                fields=["monster", "part"], name="uniq_monster_hitzone_part"
            )
        ]

    def __str__(self):
        return f"{self.monster} - {self.part}"


class Item(models.Model):
    """Material / objeto consumible del juego (usado en crafteo)."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default="")
    rarity = models.PositiveSmallIntegerField(default=1)
    carry_limit = models.PositiveSmallIntegerField(default=0)
    value = models.PositiveIntegerField(default=0, verbose_name="Precio de venta")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(models.Model):
    """Habilidad de armadura con su descripción y nivel máximo."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default="")
    max_level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SkillRank(models.Model):
    """Cada nivel de una habilidad (descripción y modificadores JSON)."""

    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="ranks")
    level = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True, default="")
    modifiers = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["skill", "level"]
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "level"], name="uniq_skill_level"
            )
        ]

    def __str__(self):
        return f"{self.skill} Lv{self.level}"


class Armor(models.Model):
    """Pieza de armadura (cabeza, pecho, brazos, cintura, piernas)."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    type = models.CharField(max_length=20, choices=ARMOR_SLOTS, db_index=True)
    rank = models.CharField(
        max_length=20, choices=ARMOR_RANKS, default="low", db_index=True
    )
    rarity = models.PositiveSmallIntegerField(default=1)
    defense_base = models.PositiveIntegerField(default=0)
    defense_max = models.PositiveIntegerField(default=0)
    defense_augmented = models.PositiveIntegerField(default=0)
    resist_fire = models.SmallIntegerField(default=0)
    resist_water = models.SmallIntegerField(default=0)
    resist_thunder = models.SmallIntegerField(default=0)
    resist_ice = models.SmallIntegerField(default=0)
    resist_dragon = models.SmallIntegerField(default=0)
    # Ranuras para joyas: lista de rangos, p.ej. [3, 1]
    slots = models.JSONField(default=list, blank=True)
    skills = models.ManyToManyField(
        Skill, through="ArmorSkill", related_name="armors", blank=True
    )
    assets = models.JSONField(default=dict, blank=True)
    crafting_materials = GenericRelation(
        "CraftingMaterial", related_query_name="armor"
    )

    class Meta:
        ordering = ["rank", "name"]

    def __str__(self):
        return self.name

    @property
    def max_slot(self):
        return max(self.slots, default=0)


class ArmorSkill(models.Model):
    """Relación Armor <-> Skill con el nivel que otorga la pieza."""

    armor = models.ForeignKey(
        Armor, on_delete=models.CASCADE, related_name="armor_skills"
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="armor_skills"
    )
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["armor", "skill"]

    def __str__(self):
        return f"{self.armor} -> {self.skill} Lv{self.level}"


class Weapon(models.Model):
    """Arma con todos los atributos relevantes para el cálculo de daño."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    weapon_type = models.CharField(max_length=30, choices=WEAPON_TYPES, db_index=True)
    damage_type = models.CharField(
        max_length=20, choices=DAMAGE_TYPES, default="sever"
    )
    rarity = models.PositiveSmallIntegerField(default=1, db_index=True)
    attack_display = models.PositiveIntegerField(default=0, verbose_name="Daño mostrado")
    attack_raw = models.PositiveIntegerField(default=0, verbose_name="Raw real")
    affinity = models.SmallIntegerField(default=0, verbose_name="Afinidad %")
    defense = models.PositiveIntegerField(default=0, verbose_name="Bono de defensa")
    elderseal = models.CharField(max_length=20, blank=True, default="")
    # Lista de {type, damage, hidden} — p.ej. [{"type": "fire", "damage": 240, "hidden": false}]
    elements = models.JSONField(default=list, blank=True)
    # Niveles de afilado: dict {red, orange, yellow, green, blue, white, purple}
    sharpness = models.JSONField(default=dict, blank=True)
    # Ranuras para joyas: lista de rangos, p.ej. [2, 1]
    slots = models.JSONField(default=list, blank=True)
    craftable = models.BooleanField(default=False)
    crafting_cost = models.PositiveIntegerField(default=0, verbose_name="Coste zenny")
    # Árbol de forja: de qué arma procede y en qué armas se ramifica.
    previous = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Arma anterior (upgrade)",
    )
    branches = models.ManyToManyField(
        "self", symmetrical=False, related_name="upgrades_from", blank=True
    )
    crafting_materials = GenericRelation(
        "CraftingMaterial", related_query_name="weapon"
    )
    assets = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def element_types(self):
        return [el.get("type") for el in self.elements]

    @property
    def sharpness_levels(self):
        """Colores de afilado disponibles (longitud > 0)."""
        return [c for c, v in self.sharpness.items() if v]

    @property
    def has_white(self):
        return bool(self.sharpness.get("white"))

    @property
    def has_purple(self):
        return bool(self.sharpness.get("purple"))


class Charm(models.Model):
    """Amuleto: otorga habilidades sin ocupar ranura.

    mhw-db estructura los amuletos por rangos (p.ej. Attack Charm 1..5):
    se guarda un ``Charm`` por rango, con ``name`` = nombre del rango.
    """

    game_id = models.IntegerField(db_index=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    level = models.PositiveSmallIntegerField(default=1, verbose_name="Nivel/rango")
    rarity = models.PositiveSmallIntegerField(default=1)
    skills = models.ManyToManyField(
        Skill, through="CharmSkill", related_name="charms", blank=True
    )
    crafting_cost = models.PositiveIntegerField(default=0, verbose_name="Coste zenny")
    # Rango anterior del mismo amuleto (p.ej. Attack Charm 1 -> 2).
    previous = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Amuleto anterior",
    )
    crafting_materials = GenericRelation(
        "CraftingMaterial", related_query_name="charm"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["game_id", "name"], name="uniq_charm_game_name"
            )
        ]

    def __str__(self):
        return self.name


class CharmSkill(models.Model):
    """Relación Charm <-> Skill con el nivel que otorga el amuleto."""

    charm = models.ForeignKey(
        Charm, on_delete=models.CASCADE, related_name="charm_skills"
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="charm_skills"
    )
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["charm", "skill"]

    def __str__(self):
        return f"{self.charm} -> {self.skill} Lv{self.level}"


class Decoration(models.Model):
    """Joya equipable en las ranuras de armas y armaduras."""

    game_id = models.IntegerField(unique=True, verbose_name="ID en mhw-db")
    name = models.CharField(max_length=100, db_index=True)
    rarity = models.PositiveSmallIntegerField(default=1)
    # Ranura mínima requerida (1-4): una joya de ranura 2 encaja en 2, 3 o 4.
    slot = models.PositiveSmallIntegerField(default=1, verbose_name="Ranura")
    skills = models.ManyToManyField(
        Skill, through="DecorationSkill", related_name="decorations", blank=True
    )

    class Meta:
        ordering = ["slot", "name"]

    def __str__(self):
        return f"{self.name} [{self.slot}]"


class DecorationSkill(models.Model):
    """Relación Decoration <-> Skill con el nivel que otorga la joya."""

    decoration = models.ForeignKey(
        Decoration, on_delete=models.CASCADE, related_name="decoration_skills"
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="decoration_skills"
    )
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["decoration", "skill"]

    def __str__(self):
        return f"{self.decoration} -> {self.skill} Lv{self.level}"


class CraftingMaterial(models.Model):
    """Material genérico usado para forjar armas o armaduras.

    Usa GenericForeignKey para poder referenciar tanto ``Weapon`` como
    ``Armor`` sin duplicar tablas.
    """

    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="used_in"
    )
    quantity = models.PositiveIntegerField(default=1)
    kind = models.CharField(
        max_length=20,
        choices=(
            ("forge", "Forja"),
            ("upgrade", "Mejora"),
        ),
        default="forge",
        verbose_name="Tipo de material",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    owner = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["item"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "item", "kind"],
                name="uniq_crafting_material",
            )
        ]

    def __str__(self):
        return f"{self.quantity}× {self.item}"
