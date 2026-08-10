# Progreso · MHW Iceborne App

App de referencia de Monster Hunter World: Iceborne (Django + HTMX + Tailwind).

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 (`config/`), app `core` |
| Base de datos | Postgres 15 (Docker) · SQLite (dev local) · Supabase (Producción) |
| Frontend | Tailwind CSS v3 · HTMX (parciales dinámicos) |
| Datos | ETL desde https://mhw-db.com/ (`core/management/commands/etl_mhw_data.py`) |
| Infra | `docker-compose.yml` (db / web / css) · `Dockerfile` (producción/Vercel) |

## Features

| # | Feature | Ruta | Estado |
|---|---------|------|--------|
| 1 | Calculadora EFR (raw + elemental, afilado/afinidad/habilidades, motion values) | `/calculator/` | ✅ |
| 2 | Autocomplete de armas en calculadora (sugerencias HTMX desde BD, debounce, teclado) | `calculator/weapons/search/` | ✅ |
| 3 | Set Builder (piezas + joyas + amuleto) con resumen de skills activas | `/sets/` | ✅ |
| 4 | Autocomplete de joyas (filtro por talla de ranura, populares al enfocar, tooltip con skills, hint "Fits: size N") y amuletos | `sets/decorations/search/` · `sets/charms/search/` | ✅ |
| 5 | Optimizador de sets (búsqueda por habilidades) | `/sets/optimize/` | ✅ |
| 6 | Bestiario (búsqueda, debilidades, resistencias, hitzones) | `/monsters/` | ✅ |
| 7 | Listado/filtro de armas (HTMX) | `/weapons/` | ✅ |
| 8 | Árbol de forja y materiales (arma, armadura, item) | `/weapons/<pk>/` · `/armor/<pk>/` · `/items/<pk>/` | ✅ |
| 9 | Hitzones corporales (datos de la comunidad) | detalle de monstruo | ✅ |
| 10 | Web traducida al inglés (templates, choices de modelos, strings de vistas) | toda la app | ✅ |
| 11 | Tests unitarios (33) | `manage.py test core` | ✅ |
| 12 | **Skills Library** (lista buscable de 181 skills con max_level y descripción) | `/skills/` | ✅ |
| 13 | **Item & Material Search** (buscador HTMX de 1186 items/materiales) | `/items/search/` | ✅ |
| 14 | **Drops en monster_detail** (recompensas/carves por monstruo con condiciones) | `/monsters/<pk>/` | ✅ |
| 15 | **UI mejorada**: nav sticky, footer, loading global, cards hover, tipografía, spacing | toda la app | ✅ |
| 16 | **Despliegue Vercel** (Dockerfile + guía) | `DEPLOY_VERCEL.md` | ✅ |
| 17 | **ETL por trozos + bulk** (reanudable, idempotente, checkpoints) | `etl_mhw_data --entity X` | ✅ |
| 18 | **Migración de datos a Supabase (Vercel)** completada desde local | BD de producción | ✅ |

## Estructura

```text
config/             settings, urls
core/
  models.py         15 modelos (Weapon, Armor, Monster, Item, Skill, Decoration, Charm, ...)
  views/            home · monsters · weapons · calculator · sets · crafting
  services/         efr.py (cálculo EFR) · optimizer.py (búsqueda de sets)
  templatetags/     mhw_extras.py (get_item, element_badge, stars_html)
  management/commands/
    etl_mhw_data.py     ETL por trozos (bulk_create + checkpoints, idempotente)
    seed_hitzones.py    siembra hitzones desde core/data/hitzones.json
  templates/core/   páginas + partials HTMX (incl. weapon/decoration/charm/armor/skill/item partials)
static/css/         output.css (compilado por Tailwind)
