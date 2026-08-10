"""ETL de datos de Monster Hunter World: Iceborne (por trozos + bulk).

Consume la API pública de https://mhw-db.com/ y puebla los modelos de la app
``core`` usando ``bulk_create`` con ``update_conflicts`` (upserts idempotentes,
solo PostgreSQL) y checkpoints para poder ejecutarse "por trozos" sin agotar
el límite de tiempo de Vercel. Se recomienda ejecutarlo desde local o un CI
apuntando a la URL no-pooling (puerto 5432 directo) de Supabase/Neon.

Uso:
    python manage.py etl_mhw_data                 # importa entidades pendientes
    python manage.py etl_mhw_data --all           # fuerza re-importar todo
    python manage.py etl_mhw_data --entity armor  # importa un solo trozo
    python manage.py etl_mhw_data --entity weapons --entity monsters
    python manage.py etl_mhw_data --reset-checkpoints
    python manage.py etl_mhw_data --clean         # borra todo antes de importar
    python manage.py etl_mhw_data --limit 10      # import parcial para pruebas

Cada trozo es idempotente: puede re-ejecutarse sin duplicar datos.
"""

import time

import requests
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    Armor,
    ArmorSkill,
    Charm,
    CharmSkill,
    CraftingMaterial,
    Decoration,
    DecorationSkill,
    EtlCheckpoint,
    Hitzone,
    Item,
    Location,
    Monster,
    MonsterAilment,
    MonsterResistance,
    MonsterReward,
    MonsterWeakness,
    Skill,
    SkillRank,
    Weapon,
)

API_BASE_URL = "https://mhw-db.com"

ENDPOINTS = {
    "items": "items",
    "skills": "skills",
    "monsters": "monsters",
    "armor": "armor",
    "weapons": "weapons",
    "decorations": "decorations",
    "charms": "charms",
}

# Orden de importación respetando dependencias (skills antes que armors/joyas/
# amuletos; items antes que materiales/recompensas).
ENTITY_ORDER = [
    "items",
    "skills",
    "monsters",
    "armor",
    "weapons",
    "decorations",
    "charms",
]

BATCH = 500


class Command(BaseCommand):
    help = "Importa datos de Monsters, Items, Skills, Armor y Weapons desde mhw-db.com"

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity",
            action="append",
            choices=ENTITY_ORDER,
            help="Importar solo estas entidades (trozos). Puede repetirse.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-importar todas las entidades, aunque estén completas.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Importar solo N registros por entidad (útil en desarrollo).",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Borrar todas las tablas antes de importar (y los checkpoints).",
        )
        parser.add_argument(
            "--reset-checkpoints",
            action="store_true",
            help="Marcar todas las entidades como pendientes.",
        )

    # ------------------------------------------------------------------
    # Utilidades de red
    # ------------------------------------------------------------------

    def fetch(self, endpoint):
        """GET con reintentos y backoff simple."""
        url = f"{API_BASE_URL}/{endpoint}"
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, timeout=(10, 120))
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                self.stdout.write(
                    self.style.WARNING(
                        f"  Intento {attempt}/3 fallido para {url}: {exc}"
                    )
                )
                time.sleep(2 * attempt)
        raise CommandError(f"No se pudo descargar {url}: {last_error}")

    def process(self, endpoint, label, limit):
        """Descarga una lista, la recorta con --limit y la devuelve."""
        data = self.fetch(endpoint)
        if limit:
            data = data[:limit]
        self.stdout.write(
            self.style.SUCCESS(f"[OK] {label}: {len(data)} registros descargados")
        )
        return data

    @staticmethod
    def to_int(value, default=0):
        """Convierte a entero tolerando strings como "10" o None."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------------
    # Limpieza
    # ------------------------------------------------------------------

    def clean_database(self):
        self.stdout.write(self.style.WARNING("Limpiando base de datos..."))
        # Orden de borrado respetando dependencias (incluidas GenericForeignKey).
        CraftingMaterial.objects.all().delete()
        DecorationSkill.objects.all().delete()
        CharmSkill.objects.all().delete()
        Decoration.objects.all().delete()
        Charm.objects.all().delete()
        ArmorSkill.objects.all().delete()
        SkillRank.objects.all().delete()
        MonsterReward.objects.all().delete()
        Hitzone.objects.all().delete()
        MonsterWeakness.objects.all().delete()
        MonsterResistance.objects.all().delete()
        MonsterAilment.objects.all().delete()
        Monster.objects.all().delete()
        Armor.objects.all().delete()
        Weapon.objects.all().delete()
        Skill.objects.all().delete()
        Item.objects.all().delete()
        Location.objects.all().delete()
        EtlCheckpoint.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("[OK] Base de datos limpia"))

    # ------------------------------------------------------------------
    # Helpers de bulk
    # ------------------------------------------------------------------

    def collect_row_items(self, rows, getter):
        """Recoge los dicts de item anidados en cada fila según un getter."""
        items, seen = [], set()
        for row in rows:
            for item_data in getter(row):
                if not item_data or item_data.get("id") is None:
                    continue
                gid = int(item_data["id"])
                if gid in seen:
                    continue
                seen.add(gid)
                items.append(item_data)
        return items

    def ensure_items(self, item_dicts):
        """Crea los Items referenciados que no existan y devuelve game_id->Item."""
        if not item_dicts:
            return {}
        game_ids = [int(d["id"]) for d in item_dicts]
        existing = set(
            Item.objects.filter(game_id__in=game_ids).values_list("game_id", flat=True)
        )
        objs = [
            Item(
                game_id=int(d["id"]),
                name=d.get("name", ""),
                description=d.get("description", "") or "",
                rarity=self.to_int(d.get("rarity"), 1),
                carry_limit=self.to_int(d.get("carryLimit"), 0),
                value=self.to_int(d.get("value"), 0),
            )
            for d in item_dicts
            if int(d["id"]) not in existing
        ]
        if objs:
            Item.objects.bulk_create(objs, batch_size=BATCH, ignore_conflicts=True)
        return Item.objects.in_bulk(game_ids, field_name="game_id")

    def skills_map(self):
        return {s.game_id: s for s in Skill.objects.all()}

    # ------------------------------------------------------------------
    # Importadores por entidad
    # ------------------------------------------------------------------

    def import_items(self, data):
        objs = [
            Item(
                game_id=int(row["id"]),
                name=row.get("name", ""),
                description=row.get("description", "") or "",
                rarity=self.to_int(row.get("rarity"), 1),
                carry_limit=self.to_int(row.get("carryLimit"), 0),
                value=self.to_int(row.get("value"), 0),
            )
            for row in data
        ]
        Item.objects.bulk_create(
            objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=["name", "description", "rarity", "carry_limit", "value"],
        )
        return len(objs)

    def import_skills(self, data):
        skill_objs = [
            Skill(
                game_id=int(row["id"]),
                name=row.get("name", ""),
                description=row.get("description", "") or "",
                max_level=len(row.get("ranks", [])),
            )
            for row in data
        ]
        Skill.objects.bulk_create(
            skill_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=["name", "description", "max_level"],
        )

        skills_by_id = self.skills_map()
        rank_objs = []
        for row in data:
            skill = skills_by_id.get(int(row["id"]))
            if not skill:
                continue
            for rank in row.get("ranks", []):
                rank_objs.append(
                    SkillRank(
                        skill=skill,
                        level=self.to_int(rank.get("level"), 1),
                        description=rank.get("description", "") or "",
                        modifiers=rank.get("modifiers") or {},
                    )
                )
        SkillRank.objects.bulk_create(
            rank_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["skill", "level"],
            update_fields=["description", "modifiers"],
        )
        return len(skill_objs)

    def import_monsters(self, data):
        monster_objs = [
            Monster(
                game_id=int(row["id"]),
                name=row.get("name", ""),
                type=row.get("type", "large"),
                species=row.get("species", "") or "",
                description=row.get("description", "") or "",
            )
            for row in data
        ]
        Monster.objects.bulk_create(
            monster_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=["name", "type", "species", "description"],
        )
        monsters = Monster.objects.in_bulk(
            [int(r["id"]) for r in data], field_name="game_id"
        )

        # Localizaciones (Location + M2M).
        locations_by_game = {}
        for row in data:
            for loc in row.get("locations", []):
                locations_by_game.setdefault(
                    int(loc["id"]),
                    {
                        "name": loc.get("name", ""),
                        "zone_count": self.to_int(loc.get("zoneCount")),
                    },
                )
        loc_objs = [
            Location(game_id=gid, **values)
            for gid, values in locations_by_game.items()
        ]
        Location.objects.bulk_create(
            loc_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=["name", "zone_count"],
        )
        locations = Location.objects.in_bulk(
            list(locations_by_game), field_name="game_id"
        )

        through = Monster.locations.through
        m2m_objs, seen_m2m = [], set()
        for row in data:
            monster = monsters.get(int(row["id"]))
            if not monster:
                continue
            for loc in row.get("locations", []):
                location = locations.get(int(loc["id"]))
                if not location or (monster.pk, location.pk) in seen_m2m:
                    continue
                seen_m2m.add((monster.pk, location.pk))
                m2m_objs.append(
                    through(monster_id=monster.pk, location_id=location.pk)
                )
        through.objects.bulk_create(m2m_objs, batch_size=BATCH, ignore_conflicts=True)

        # Debilidades.
        weakness_objs = []
        for row in data:
            monster = monsters.get(int(row["id"]))
            if not monster:
                continue
            for weakness in row.get("weaknesses", []):
                element = weakness.get("element")
                if not element:
                    continue
                weakness_objs.append(
                    MonsterWeakness(
                        monster=monster,
                        element=element,
                        condition=weakness.get("condition") or "",
                        stars=self.to_int(weakness.get("stars")),
                    )
                )
        MonsterWeakness.objects.bulk_create(
            weakness_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["monster", "element", "condition"],
            update_fields=["stars"],
        )

        # Resistencias.
        resistance_objs = []
        for row in data:
            monster = monsters.get(int(row["id"]))
            if not monster:
                continue
            for resistance in row.get("resistances", []):
                element = resistance.get("element")
                if not element:
                    continue
                resistance_objs.append(
                    MonsterResistance(
                        monster=monster,
                        element=element,
                        stars=self.to_int(resistance.get("stars")),
                    )
                )
        MonsterResistance.objects.bulk_create(
            resistance_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["monster", "element"],
            update_fields=["stars"],
        )

        # Estados alterados.
        ailment_objs = []
        for row in data:
            monster = monsters.get(int(row["id"]))
            if not monster:
                continue
            for ailment in row.get("ailments", []):
                ailment_objs.append(
                    MonsterAilment(
                        monster=monster,
                        name=ailment.get("name", ""),
                        description=ailment.get("description", "") or "",
                    )
                )
        MonsterAilment.objects.bulk_create(
            ailment_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["monster", "name"],
            update_fields=["description"],
        )

        # Recompensas (crea los items referenciados si faltan).
        reward_items = self.collect_row_items(
            data,
            lambda row: [
                reward.get("item")
                for reward in row.get("rewards", [])
                if reward.get("item")
            ],
        )
        items = self.ensure_items(reward_items)
        reward_objs = []
        for row in data:
            monster = monsters.get(int(row["id"]))
            if not monster:
                continue
            for reward in row.get("rewards", []):
                item_data = reward.get("item")
                if not item_data:
                    continue
                item = items.get(int(item_data["id"]))
                if not item:
                    continue
                reward_objs.append(
                    MonsterReward(
                        monster=monster,
                        item=item,
                        conditions=reward.get("conditions", []),
                    )
                )
        MonsterReward.objects.bulk_create(
            reward_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["monster", "item"],
            update_fields=["conditions"],
        )
        return len(monster_objs)

    def import_armor(self, data, skills_by_id):
        armor_objs = []
        for row in data:
            defenses = row.get("defense") or {}
            resist = row.get("resistances") or {}
            armor_objs.append(
                Armor(
                    game_id=int(row["id"]),
                    name=row.get("name", ""),
                    type=row.get("type", "head"),
                    rank=row.get("rank", "low"),
                    rarity=self.to_int(row.get("rarity"), 1),
                    defense_base=self.to_int(defenses.get("base")),
                    defense_max=self.to_int(defenses.get("max")),
                    defense_augmented=self.to_int(defenses.get("augmented")),
                    resist_fire=self.to_int(resist.get("fire")),
                    resist_water=self.to_int(resist.get("water")),
                    resist_thunder=self.to_int(resist.get("thunder")),
                    resist_ice=self.to_int(resist.get("ice")),
                    resist_dragon=self.to_int(resist.get("dragon")),
                    slots=[
                        slot.get("rank", 1)
                        for slot in row.get("slots", [])
                        if slot.get("rank")
                    ],
                    assets=row.get("assets") or {},
                )
            )
        Armor.objects.bulk_create(
            armor_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=[
                "name",
                "type",
                "rank",
                "rarity",
                "defense_base",
                "defense_max",
                "defense_augmented",
                "resist_fire",
                "resist_water",
                "resist_thunder",
                "resist_ice",
                "resist_dragon",
                "slots",
                "assets",
            ],
        )
        armors = Armor.objects.in_bulk([int(r["id"]) for r in data], field_name="game_id")

        armor_skill_objs = []
        for row in data:
            armor = armors.get(int(row["id"]))
            if not armor:
                continue
            for skill_info in row.get("skills", []):
                skill = skills_by_id.get(int(skill_info.get("skill")))
                if not skill:
                    continue
                armor_skill_objs.append(
                    ArmorSkill(
                        armor=armor,
                        skill=skill,
                        level=self.to_int(skill_info.get("level"), 1),
                    )
                )
        ArmorSkill.objects.bulk_create(
            armor_skill_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["armor", "skill"],
            update_fields=["level"],
        )

        material_items = self.collect_row_items(
            data,
            lambda row: [
                mat.get("item")
                for mat in (row.get("crafting") or {}).get("materials", [])
            ],
        )
        items = self.ensure_items(material_items)
        ct_armor = ContentType.objects.get_for_model(Armor)
        materials = []
        for row in data:
            armor = armors.get(int(row["id"]))
            if not armor:
                continue
            for mat in (row.get("crafting") or {}).get("materials", []):
                item_data = mat.get("item")
                if not item_data:
                    continue
                item = items.get(int(item_data["id"]))
                if not item:
                    continue
                materials.append(
                    CraftingMaterial(
                        content_type=ct_armor,
                        object_id=armor.pk,
                        item=item,
                        quantity=self.to_int(mat.get("quantity"), 1),
                        kind="forge",
                    )
                )
        CraftingMaterial.objects.bulk_create(
            materials,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["content_type", "object_id", "item", "kind"],
            update_fields=["quantity"],
        )
        return len(armor_objs)

    def import_weapons(self, data):
        weapon_objs = []
        for row in data:
            attack = row.get("attack") or {}
            attributes = row.get("attributes") or {}
            elements = row.get("elements") or []

            # Compatibilidad con formatos antiguos: attributes.element.
            legacy_element = attributes.get("element")
            if not elements and legacy_element and legacy_element.get("type"):
                elements = [
                    {
                        "type": legacy_element["type"],
                        "damage": legacy_element.get("damage", 0),
                        "hidden": legacy_element.get("hidden", False),
                    }
                ]

            durability = row.get("durability") or []
            base_sharpness = durability[0] if durability else {}
            damage_type = (
                row.get("damageType") or attributes.get("damageType") or "sever"
            )

            weapon_objs.append(
                Weapon(
                    game_id=int(row["id"]),
                    name=row.get("name", ""),
                    weapon_type=row.get("type", ""),
                    damage_type=damage_type,
                    rarity=self.to_int(row.get("rarity"), 1),
                    attack_display=self.to_int(attack.get("display")),
                    attack_raw=self.to_int(attack.get("raw", attack.get("true"))),
                    affinity=self.to_int(attributes.get("affinity")),
                    defense=self.to_int(attributes.get("defense")),
                    elderseal=attributes.get("elderseal")
                    or row.get("elderseal")
                    or "",
                    elements=elements,
                    sharpness=base_sharpness,
                    slots=[
                        slot.get("rank", 1)
                        for slot in row.get("slots", [])
                        if slot.get("rank")
                    ],
                    craftable=bool((row.get("crafting") or {}).get("craftable", False)),
                    crafting_cost=self.to_int(
                        (row.get("crafting") or {}).get("cost")
                    ),
                    assets=row.get("assets") or {},
                )
            )
        Weapon.objects.bulk_create(
            weapon_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=[
                "name",
                "weapon_type",
                "damage_type",
                "rarity",
                "attack_display",
                "attack_raw",
                "affinity",
                "defense",
                "elderseal",
                "elements",
                "sharpness",
                "slots",
                "craftable",
                "crafting_cost",
                "assets",
            ],
        )
        weapons = Weapon.objects.in_bulk(
            [int(r["id"]) for r in data], field_name="game_id"
        )

        material_items = self.collect_row_items(
            data,
            lambda row: [
                mat.get("item")
                for mat in (row.get("crafting") or {}).get("craftingMaterials", [])
            ]
            + [
                mat.get("item")
                for mat in (row.get("crafting") or {}).get("upgradeMaterials", [])
            ],
        )
        items = self.ensure_items(material_items)
        ct_weapon = ContentType.objects.get_for_model(Weapon)
        materials = []
        for row in data:
            weapon = weapons.get(int(row["id"]))
            if not weapon:
                continue
            crafting = row.get("crafting") or {}
            for mat, kind in [
                (m, "forge") for m in crafting.get("craftingMaterials", [])
            ] + [(m, "upgrade") for m in crafting.get("upgradeMaterials", [])]:
                item_data = mat.get("item")
                if not item_data:
                    continue
                item = items.get(int(item_data["id"]))
                if not item:
                    continue
                materials.append(
                    CraftingMaterial(
                        content_type=ct_weapon,
                        object_id=weapon.pk,
                        item=item,
                        quantity=self.to_int(mat.get("quantity"), 1),
                        kind=kind,
                    )
                )
        CraftingMaterial.objects.bulk_create(
            materials,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["content_type", "object_id", "item", "kind"],
            update_fields=["quantity"],
        )

        # Árbol de forja: previous + branches.
        previous_updates = []
        through = Weapon.branches.through
        branch_rows, seen_branches = [], set()
        for row in data:
            weapon = weapons.get(int(row["id"]))
            if not weapon:
                continue
            crafting = row.get("crafting") or {}
            previous_id = crafting.get("previous")
            if previous_id and previous_id in weapons:
                weapon.previous = weapons[previous_id]
                previous_updates.append(weapon)
            for branch_id in crafting.get("branches", []):
                branch = weapons.get(branch_id)
                if branch and (weapon.pk, branch.pk) not in seen_branches:
                    seen_branches.add((weapon.pk, branch.pk))
                    branch_rows.append(
                        through(from_weapon_id=weapon.pk, to_weapon_id=branch.pk)
                    )
        if previous_updates:
            Weapon.objects.bulk_update(previous_updates, ["previous"], batch_size=BATCH)
        through.objects.bulk_create(branch_rows, batch_size=BATCH, ignore_conflicts=True)
        return len(weapon_objs)

    def import_decorations(self, data, skills_by_id):
        deco_objs = [
            Decoration(
                game_id=int(row["id"]),
                name=row.get("name", ""),
                rarity=self.to_int(row.get("rarity"), 1),
                slot=self.to_int(row.get("slot"), 1),
            )
            for row in data
        ]
        Decoration.objects.bulk_create(
            deco_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id"],
            update_fields=["name", "rarity", "slot"],
        )
        decorations = Decoration.objects.in_bulk(
            [int(r["id"]) for r in data], field_name="game_id"
        )

        skill_objs = []
        for row in data:
            decoration = decorations.get(int(row["id"]))
            if not decoration:
                continue
            for skill_info in row.get("skills", []):
                skill = skills_by_id.get(int(skill_info.get("skill")))
                if not skill:
                    continue
                skill_objs.append(
                    DecorationSkill(
                        decoration=decoration,
                        skill=skill,
                        level=self.to_int(skill_info.get("level"), 1),
                    )
                )
        DecorationSkill.objects.bulk_create(
            skill_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["decoration", "skill"],
            update_fields=["level"],
        )
        return len(deco_objs)

    def import_charms(self, data, skills_by_id):
        charm_objs = []
        for row in data:
            for rank in row.get("ranks", []):
                charm_objs.append(
                    Charm(
                        game_id=int(row["id"]),
                        name=rank.get("name", ""),
                        level=self.to_int(rank.get("level"), 1),
                        rarity=self.to_int(rank.get("rarity"), 1),
                        crafting_cost=self.to_int(
                            (rank.get("crafting") or {}).get("cost")
                        ),
                    )
                )
        Charm.objects.bulk_create(
            charm_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["game_id", "name"],
            update_fields=["name", "level", "rarity", "crafting_cost"],
        )
        base_game_ids = list({int(r["id"]) for r in data})
        charm_map = {
            (c.game_id, c.name): c
            for c in Charm.objects.filter(game_id__in=base_game_ids)
        }

        charm_skill_objs = []
        for row in data:
            for rank in row.get("ranks", []):
                charm = charm_map.get((int(row["id"]), rank.get("name", "")))
                if not charm:
                    continue
                for skill_info in rank.get("skills", []):
                    skill = skills_by_id.get(int(skill_info.get("skill")))
                    if not skill:
                        continue
                    charm_skill_objs.append(
                        CharmSkill(
                            charm=charm,
                            skill=skill,
                            level=self.to_int(skill_info.get("level"), 1),
                        )
                    )
        CharmSkill.objects.bulk_create(
            charm_skill_objs,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["charm", "skill"],
            update_fields=["level"],
        )

        material_items = self.collect_row_items(
            data,
            lambda row: [
                mat.get("item")
                for rank in row.get("ranks", [])
                for mat in (rank.get("crafting") or {}).get("materials", [])
            ],
        )
        items = self.ensure_items(material_items)
        ct_charm = ContentType.objects.get_for_model(Charm)
        materials = []
        for row in data:
            for rank in row.get("ranks", []):
                charm = charm_map.get((int(row["id"]), rank.get("name", "")))
                if not charm:
                    continue
                for mat in (rank.get("crafting") or {}).get("materials", []):
                    item_data = mat.get("item")
                    if not item_data:
                        continue
                    item = items.get(int(item_data["id"]))
                    if not item:
                        continue
                    materials.append(
                        CraftingMaterial(
                            content_type=ct_charm,
                            object_id=charm.pk,
                            item=item,
                            quantity=self.to_int(mat.get("quantity"), 1),
                            kind="forge",
                        )
                    )
        CraftingMaterial.objects.bulk_create(
            materials,
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["content_type", "object_id", "item", "kind"],
            update_fields=["quantity"],
        )

        # Encadenar rangos: Attack Charm 2 -> previous = Attack Charm 1.
        level_map = {(c.game_id, c.level): c for c in charm_map.values()}
        previous_updates = []
        for (game_id, level), charm in level_map.items():
            previous = level_map.get((game_id, level - 1))
            if previous and charm.previous_id != previous.pk:
                charm.previous = previous
                previous_updates.append(charm)
        if previous_updates:
            Charm.objects.bulk_update(previous_updates, ["previous"], batch_size=BATCH)
        return len(charm_objs)

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def pending_entities(self):
        done = set(EtlCheckpoint.objects.values_list("entity", flat=True))
        return [e for e in ENTITY_ORDER if e not in done]

    def run_entity(self, entity, limit):
        self.stdout.write(self.style.MIGRATE_HEADING(f"--- Trozo: {entity} ---"))
        data = self.process(ENDPOINTS[entity], entity, limit)
        with transaction.atomic():
            if entity == "items":
                count = self.import_items(data)
            elif entity == "skills":
                count = self.import_skills(data)
            elif entity == "monsters":
                count = self.import_monsters(data)
            elif entity == "armor":
                count = self.import_armor(data, self.skills_map())
            elif entity == "weapons":
                count = self.import_weapons(data)
            elif entity == "decorations":
                count = self.import_decorations(data, self.skills_map())
            elif entity == "charms":
                count = self.import_charms(data, self.skills_map())
            self.stdout.write(
                self.style.SUCCESS(f"[OK] {entity}: {count} filas importadas")
            )
        if limit is None:
            EtlCheckpoint.objects.update_or_create(
                entity=entity, defaults={"row_count": count}
            )

    def handle(self, *args, **options):
        limit = options["limit"]
        entities = options["entity"] or []

        if options["reset_checkpoints"]:
            EtlCheckpoint.objects.all().delete()
            self.stdout.write(self.style.WARNING("[OK] Checkpoints reiniciados"))

        if options["clean"]:
            self.clean_database()

        if entities:
            # Orden de los trozos pedidos: se reordenan según ENTITY_ORDER
            # para respetar dependencias (p. ej. skills antes que armor).
            order = {name: i for i, name in enumerate(ENTITY_ORDER)}
            entities = sorted(set(entities), key=lambda e: order[e])
        elif options["all"]:
            entities = ENTITY_ORDER
        else:
            entities = self.pending_entities()

        if not entities:
            self.stdout.write(
                self.style.SUCCESS(
                    "Nada pendiente. Usa --all para re-importar todo."
                )
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING("=== ETL mhw-db.com (por trozos) ==="))
        for entity in entities:
            self.run_entity(entity, limit)

        self.stdout.write(self.style.MIGRATE_HEADING("=== ETL finalizado ==="))
        self.stdout.write(
            self.style.SUCCESS(
                f"  Monstruos: {Monster.objects.count()} "
                f"| Items: {Item.objects.count()} "
                f"| Skills: {Skill.objects.count()} "
                f"| Armaduras: {Armor.objects.count()} "
                f"| Armas: {Weapon.objects.count()} "
                f"| Joyas: {Decoration.objects.count()} "
                f"| Amuletos: {Charm.objects.count()} "
                f"| Materiales: {CraftingMaterial.objects.count()}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Nota: mhw-db no expone datos de hitzones corporales; "
                "ejecuta 'python manage.py seed_hitzones' para cargar "
                "los datos de la comunidad incluidos en core/data/hitzones.json."
            )
        )