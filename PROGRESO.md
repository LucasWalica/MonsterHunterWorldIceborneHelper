# Progreso · MHW Iceborne App

App de referencia de Monster Hunter World: Iceborne (Django + HTMX + Tailwind).

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 (`config/`), app `core` |
| Base de datos | Postgres 15 (Docker) · SQLite (dev local) |
| Frontend | Tailwind CSS v3 · HTMX (parciales dinámicos) |
| Datos | ETL desde https://mhw-db.com/ (`core/management/commands/etl_mhw_data.py`) |
| Infra | `docker-compose.yml` (db / web / css) |

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
| 11 | Tests unitarios (29) | `manage.py test core` | ✅ |

## Estructura

```
config/            settings, urls
core/
  models.py       15 modelos (Weapon, Armor, Monster, Item, Skill, Decoration, Charm, ...)
  views/          home · monsters · weapons · calculator · sets · crafting
  services/       efr.py (cálculo EFR) · optimizer.py (búsqueda de sets)
  templatetags/   mhw_extras.py (get_item, element_badge, stars_html)
  management/commands/
    etl_mhw_data.py    importa mhw-db
    seed_hitzones.py   siembra hitzones desde core/data/hitzones.json
  templates/core/  páginas + partials HTMX (incl. weapon/decoration/charm_suggestions)
static/css/        output.css (compilado por Tailwind)
```

## Endpoints de búsqueda HTMX (sugerencias)

| Endpoint | Qué busca | Notas |
|----------|-----------|-------|
| `GET /calculator/weapons/search/?q=` | Armas por nombre | top 20 por tipo |
| `GET /sets/decorations/search/?q=&max_slot=&slot=` | Joyas por nombre | filtra por talla de ranura; `q` vacío ⇒ joyas populares (mayor rareza) |
| `GET /sets/charms/search/?q=` | Amuletos por nombre | top 20 |

## Cómo ejecutar

### Docker (Postgres)
```bash
docker compose up -d --build          # db + web + css (watch de Tailwind)
docker compose exec web python manage.py etl_mhw_data
docker compose exec web python manage.py seed_hitzones
# http://localhost:8000
```

### Local (SQLite)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py etl_mhw_data          # opcional: --limit 10 para pruebas
python manage.py seed_hitzones
python manage.py runserver
```

### Tests
```bash
python manage.py test core             # 29 tests (EFR, optimizer, vistas, búsquedas HTMX)
```

> Nota Docker: Django cachea el URLconf por proceso. Tras añadir rutas nuevas
> (`urls.py`), reiniciar con `docker compose restart web` para evitar `NoReverseMatch`.

## Datos (volcado actual)

Monstruos 58 · Items 1186 · Skills 181 · Armaduras 1677 · Armas 1299 ·
Joyas 405 · Amuletos 314 rangos (109 amuletos) · Materiales 8400 · Hitzones 172 filas (33 monstruos).

## Próximos pasos propuestos

- [ ] Librería de habilidades: lista de Skills con niveles y descripción.
- [ ] Buscador de items/materiales (reutilizar el patrón de autocomplete HTMX ya existente).
- [ ] Drops por monstruo: listar recompensas/carves en `monster_detail`
      (hoy solo se ven desde `item_detail`).
- [ ] Arma dentro del Set Builder (el arma no influye en el build actual).
- [ ] Persistencia de sets (guardar/cargar en localStorage o por usuario).
- [ ] README.md más completo + capturas.

## Notas de entorno

- El contenedor `css` de Tailwind entró en restart loop por errores
  `posix_spawn` del entorno; el CSS quedó compilado una vez y se recompila en
  el arranque de `web` (`entrypoint.local.sh`). Recuperar con
  `docker compose up -d css` cuando el entorno se estabilice.
- `config/settings.py` usa `ManifestStaticFilesStorage` solo con `DEBUG=False`
  (en dev no requiere `collectstatic`).
- mhw-db no expone hitzones: se cargan con `seed_hitzones` (datos de la
  comunidad en `core/data/hitzones.json`; cubren 33 grandes monstruos).
