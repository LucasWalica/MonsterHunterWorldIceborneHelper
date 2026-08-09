"""Siembra datos de hitzones corporales desde un archivo JSON.

mhw-db no expone hitzones, así que se alimentan con datos de la comunidad.
El archivo ``core/data/hitzones.json`` mapea por nombre de monstruo
(case-insensitive) una lista de partes con los % de daño recibido.

Uso:
    python manage.py seed_hitzones
    python manage.py seed_hitzones --monster anjanath
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Hitzone, Monster

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "hitzones.json"

FIELDS = (
    ("part", "part"),
    ("cut", "cut"),
    ("impact", "impact"),
    ("shot", "shot"),
    ("fire", "fire"),
    ("water", "water"),
    ("thunder", "thunder"),
    ("ice", "ice"),
    ("dragon", "dragon"),
)


class Command(BaseCommand):
    help = "Carga hitzones corporales de los monstruos desde hitzones.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--monster",
            type=str,
            default=None,
            help="Limitar el seed a un monstruo por nombre (parcial).",
        )

    def handle(self, *args, **options):
        if not DATA_FILE.exists():
            raise CommandError(f"No existe el archivo de datos: {DATA_FILE}")

        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        name_lookup = {m.name.lower(): m for m in Monster.objects.all()}

        monster_filter = options["monster"]
        if monster_filter:
            monster_filter = monster_filter.strip().lower()
            if monster_filter not in name_lookup:
                raise CommandError(
                    f"No se encontró ningún monstruo con nombre "
                    f"'{monster_filter}' en la base de datos."
                )
            keys = [monster_filter]
        else:
            keys = [key for key in data if key.lower() in name_lookup]

        seeded = skipped = 0
        for key in keys:
            monster = name_lookup[key.lower()]
            Hitzone.objects.filter(monster=monster).delete()
            for part_data in data[key]:
                defaults = {
                    model_field: int(part_data.get(source, 0))
                    for source, model_field in FIELDS
                    if source != "part"
                }
                Hitzone.objects.create(monster=monster, part=part_data["part"], **defaults)
            seeded += 1

        skipped = len(data) - len(keys)
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Hitzones sembrados para {seeded} monstruo(s)"
                f" ({Hitzone.objects.count()} filas en total)"
            )
        )
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"  {skipped} entradas de datos no coinciden con "
                    "ningún monstruo de la base de datos."
                )
            )
