"""ETL de datos de Monster Hunter World: Iceborne.

Consume la API pública de https://mhw-db.com/ y puebla los modelos de la app
``core``. Limpia la base de datos antes de cada ejecución para evitar
duplicados.

Uso:
    python manage.py etl_mhw_data
    python manage.py etl_mhw_data --limit 10   # import parcial para pruebas
"""

import time

import requests
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from core.models import (
    Armor,
    ArmorSkill,
    Charm,
    CharmSkill,
    CraftingMaterial,
    Decoration,
    DecorationSkill,
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


class Command(BaseCommand):
    help = "Importa datos de Monsters, Items, Skills, Armor y Weapons desde mhw-db.com"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Importar solo N registros por entidad (útil en desarrollo).",
        )
        parser.add_argument(
            "--skip-clean",
            action="store_true",
            help="No limpiar la base de datos antes de importar.",
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
        self.stdout.write(self.style.SUCCESS("[OK] Base de datos limpia"))

    # ------------------------------------------------------------------
    # Importadores por entidad
    # ------------------------------------------------------------------

    def import_items(self, data):
        for row in data:
            Item.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "description": row.get("description", "") or "",
                    "rarity": row.get("rarity", 1),
                    "carry_limit": row.get("carryLimit", 0),
                    "value": row.get("value", 0),
                },
            )
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Items importados: {len(data)}")
        )

    def import_skills(self, data):
        for row in data:
            ranks = row.get("ranks", [])
            skill, _ = Skill.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "description": row.get("description", "") or "",
                    "max_level": len(ranks),
                },
            )
            for rank in ranks:
                SkillRank.objects.update_or_create(
                    skill=skill,
                    level=rank.get("level", 1),
                    defaults={
                        "description": rank.get("description", "") or "",
                        "modifiers": rank.get("modifiers") or {},
                    },
                )
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Skills importadas: {len(data)}")
        )

    def import_monsters(self, data):
        for row in data:
            monster, _ = Monster.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "type": row.get("type", "large"),
                    "species": row.get("species", "") or "",
                    "description": row.get("description", "") or "",
                },
            )

            for loc_data in row.get("locations", []):
                location, _ = Location.objects.update_or_create(
                    game_id=loc_data["id"],
                    defaults={
                        "name": loc_data.get("name", ""),
                        "zone_count": loc_data.get("zoneCount", 0),
                    },
                )
                monster.locations.add(location)

            for weakness in row.get("weaknesses", []):
                element = weakness.get("element")
                if not element:
                    continue
                MonsterWeakness.objects.update_or_create(
                    monster=monster,
                    element=element,
                    condition=weakness.get("condition") or "",
                    defaults={"stars": weakness.get("stars", 0)},
                )

            for resistance in row.get("resistances", []):
                element = resistance.get("element")
                if not element:
                    continue
                MonsterResistance.objects.update_or_create(
                    monster=monster,
                    element=element,
                    defaults={"stars": resistance.get("stars", 0)},
                )

            for ailment in row.get("ailments", []):
                MonsterAilment.objects.update_or_create(
                    monster=monster,
                    name=ailment.get("name", ""),
                    defaults={
                        "description": ailment.get("description", "") or "",
                    },
                )

            for reward in row.get("rewards", []):
                item_data = reward.get("item")
                if not item_data:
                    continue
                item, _ = Item.objects.get_or_create(
                    game_id=item_data["id"],
                    defaults={
                        "name": item_data.get("name", ""),
                        "description": item_data.get("description", "") or "",
                        "rarity": item_data.get("rarity", 1),
                        "carry_limit": item_data.get("carryLimit", 0),
                        "value": item_data.get("value", 0),
                    },
                )
                MonsterReward.objects.update_or_create(
                    monster=monster,
                    item=item,
                    defaults={"conditions": reward.get("conditions", [])},
                )
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Monstruos importados: {len(data)}")
        )

    def import_armor(self, data, skills_by_id):
        for row in data:
            defenses = row.get("defense") or {}
            resist = row.get("resistances") or {}
            armor, _ = Armor.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "type": row.get("type", "head"),
                    "rank": row.get("rank", "low"),
                    "rarity": row.get("rarity", 1),
                    "defense_base": defenses.get("base", 0),
                    "defense_max": defenses.get("max", 0),
                    "defense_augmented": defenses.get("augmented", 0),
                    "resist_fire": resist.get("fire", 0),
                    "resist_water": resist.get("water", 0),
                    "resist_thunder": resist.get("thunder", 0),
                    "resist_ice": resist.get("ice", 0),
                    "resist_dragon": resist.get("dragon", 0),
                    "slots": [
                        slot.get("rank", 1)
                        for slot in row.get("slots", [])
                        if slot.get("rank")
                    ],
                    "assets": row.get("assets") or {},
                },
            )

            for skill_info in row.get("skills", []):
                skill = skills_by_id.get(skill_info.get("skill"))
                if not skill:
                    continue
                ArmorSkill.objects.update_or_create(
                    armor=armor,
                    skill=skill,
                    defaults={"level": skill_info.get("level", 1)},
                )

            crafting = row.get("crafting") or {}
            for mat in crafting.get("materials", []):
                self.create_material(mat, armor, kind="forge")
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Armaduras importadas: {len(data)}")
        )

    def import_weapons(self, data):
        # Primera pasada: crear todos los objetos Weapon.
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
                row.get("damageType")
                or attributes.get("damageType")
                or "sever"
            )

            weapon, _ = Weapon.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "weapon_type": row.get("type", ""),
                    "damage_type": damage_type,
                    "rarity": self.to_int(row.get("rarity"), 1),
                    "attack_display": self.to_int(attack.get("display")),
                    "attack_raw": self.to_int(
                        attack.get("raw", attack.get("true"))
                    ),
                    "affinity": self.to_int(attributes.get("affinity")),
                    "defense": self.to_int(attributes.get("defense")),
                    "elderseal": attributes.get("elderseal")
                    or row.get("elderseal")
                    or "",
                    "elements": elements,
                    "sharpness": base_sharpness,
                    "slots": [
                        slot.get("rank", 1)
                        for slot in row.get("slots", [])
                        if slot.get("rank")
                    ],
                    "craftable": (row.get("crafting") or {}).get(
                        "craftable", False
                    ),
                    "crafting_cost": self.to_int(
                        (row.get("crafting") or {}).get("cost")
                    ),
                    "assets": row.get("assets") or {},
                },
            )

            crafting = row.get("crafting") or {}
            for mat in crafting.get("craftingMaterials", []):
                self.create_material(mat, weapon, kind="forge")
            for mat in crafting.get("upgradeMaterials", []):
                self.create_material(mat, weapon, kind="upgrade")

        # Segunda pasada: resolver el árbol de forja (previous/branches).
        weapons_by_id = {w.game_id: w for w in Weapon.objects.all()}
        resolved = 0
        for row in data:
            weapon = weapons_by_id.get(row["id"])
            if not weapon:
                continue
            crafting = row.get("crafting") or {}
            previous_id = crafting.get("previous")
            if previous_id and previous_id in weapons_by_id:
                weapon.previous = weapons_by_id[previous_id]
            for branch_id in crafting.get("branches", []):
                branch = weapons_by_id.get(branch_id)
                if branch:
                    weapon.branches.add(branch)
            if weapon.previous or weapon.branches.exists():
                weapon.save()
                resolved += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Armas importadas: {len(data)} "
                f"(árbol de forja resuelto en {resolved})"
            )
        )

    def import_decorations(self, data, skills_by_id):
        """Importa joyas (decorations) con la habilidad y nivel que otorgan."""
        for row in data:
            decoration, _ = Decoration.objects.update_or_create(
                game_id=row["id"],
                defaults={
                    "name": row.get("name", ""),
                    "rarity": row.get("rarity", 1),
                    "slot": row.get("slot", 1),
                },
            )
            for skill_info in row.get("skills", []):
                skill = skills_by_id.get(skill_info.get("skill"))
                if not skill:
                    continue
                DecorationSkill.objects.update_or_create(
                    decoration=decoration,
                    skill=skill,
                    defaults={"level": skill_info.get("level", 1)},
                )
        self.stdout.write(
            self.style.SUCCESS(f"[OK] Joyas importadas: {len(data)}")
        )

    def import_charms(self, data, skills_by_id):
        """Importa amuletos (charms): un Charm por rango (Attack Charm 1..5)."""
        charms_by_key = {}
        for row in data:
            for rank in row.get("ranks", []):
                charm, _ = Charm.objects.update_or_create(
                    game_id=row["id"],
                    name=rank.get("name", ""),
                    defaults={
                        "level": rank.get("level", 1),
                        "rarity": rank.get("rarity", 1),
                        "crafting_cost": (rank.get("crafting") or {}).get(
                            "cost", 0
                        ),
                    },
                )
                charms_by_key[(row["id"], rank.get("level", 1))] = charm

                for skill_info in rank.get("skills", []):
                    skill = skills_by_id.get(skill_info.get("skill"))
                    if not skill:
                        continue
                    CharmSkill.objects.update_or_create(
                        charm=charm,
                        skill=skill,
                        defaults={"level": skill_info.get("level", 1)},
                    )
                for mat in (rank.get("crafting") or {}).get("materials", []):
                    self.create_material(mat, charm, kind="forge")

        # Encadenar rangos: Attack Charm 2 -> previous = Attack Charm 1.
        for (game_id, level), charm in charms_by_key.items():
            previous = charms_by_key.get((game_id, level - 1))
            if previous:
                charm.previous = previous
                charm.save(update_fields=["previous"])

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Amuletos importados: {Charm.objects.count()} rangos"
            )
        )

    def create_material(self, mat_data, owner, kind="forge"):
        """Crea un CraftingMaterial con GenericForeignKey hacia el owner."""
        item_data = mat_data.get("item")
        if not item_data:
            return
        item, _ = Item.objects.get_or_create(
            game_id=item_data["id"],
            defaults={
                "name": item_data.get("name", ""),
                "description": item_data.get("description", "") or "",
                "rarity": item_data.get("rarity", 1),
                "carry_limit": item_data.get("carryLimit", 0),
                "value": item_data.get("value", 0),
            },
        )
        CraftingMaterial.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(owner.__class__),
            object_id=owner.pk,
            item=item,
            kind=kind,
            defaults={"quantity": mat_data.get("quantity", 1)},
        )

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        limit = options["limit"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== ETL mhw-db.com ==="))
        if not options["skip_clean"]:
            self.clean_database()

        items = self.process("items", "Items", limit)
        self.import_items(items)

        skills = self.process("skills", "Skills", limit)
        self.import_skills(skills)
        skills_by_id = {s.game_id: s for s in Skill.objects.all()}

        monsters = self.process("monsters", "Monstruos", limit)
        self.import_monsters(monsters)

        armor = self.process("armor", "Armaduras", limit)
        self.import_armor(armor, skills_by_id)

        weapons = self.process("weapons", "Armas", limit)
        self.import_weapons(weapons)

        decorations = self.process("decorations", "Joyas", limit)
        self.import_decorations(decorations, skills_by_id)

        charms = self.process("charms", "Amuletos", limit)
        self.import_charms(charms, skills_by_id)

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
