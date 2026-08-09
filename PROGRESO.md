# Progreso · MHW Iceborne App

App de referencia de Monster Hunter World: Iceborne (Django + HTMX + Tailwind).

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 (`config/`), app `core` |
| Base de datos | Postgres 15 (Docker) · SQLite (dev local) |
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
  templates/core/  páginas + partials HTMX (incl. weapon/decoration/charm/armor/skill/item partials)
static/css/        output.css (compilado por Tailwind)
```

## Endpoints de búsqueda HTMX (sugerencias)

| Endpoint | Qué busca | Notas |
|----------|-----------|-------|
| `GET /calculator/weapons/search/?q=` | Armas por nombre | top 20 por tipo |
| `GET /sets/decorations/search/?q=&max_slot=&slot=` | Joyas por nombre | filtra por talla de ranura; `q` vacío ⇒ joyas populares (mayor rareza) |
| `GET /sets/charms/search/?q=` | Amuletos por nombre | top 20 |
| `GET /sets/armors/picker/?slot=` | Armaduras por slot | para modal del set builder |
| `GET /skills/` | Skills (página + partial) | búsqueda + filtro max_level |
| `GET /items/search/` | Items/materiales (página + partial) | búsqueda por nombre |

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
python manage.py test core             # 33 tests (EFR, optimizer, vistas, búsquedas HTMX)
```

> Nota Docker: Django cachea el URLconf por proceso. Tras añadir rutas nuevas
> (`urls.py`), reiniciar con `docker compose restart web` para evitar `NoReverseMatch`.

## Datos (volcado actual)

Monstruos 58 · Items 1186 · Skills 181 · Armaduras 1677 · Armas 1299 ·
Joyas 405 · Amuletos 314 rangos (109 amuletos) · Materiales 8400 · Hitzones 172 filas (33 monstruos).

## Próximos pasos propuestos

- [ ] Arma dentro del Set Builder (el arma no influye en el build actual).
- [ ] Persistencia de sets (guardar/cargar en localStorage o por usuario).
- [ ] README.md más completo + capturas.
- [ ] Autenticación de usuario y sets privados.

## Despliegue en Vercel

Ver `DEPLOY_VERCEL.md` para la guía completa.

Resumen rápido:

1. Conecta repo a Vercel → detecta `Dockerfile`
2. Configura variables de entorno (`DEBUG=0`, `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS=.vercel.app`, `CSRF_TRUSTED_ORIGINS=https://*.vercel.app`)
3. Usa PostgreSQL con **pooled connection** (Neon, Supabase, Railway)
4. `vercel --prod` o push a `main`
5. Corre migraciones y ETL una vez: `python manage.py migrate && python manage.py etl_mhw_data && python manage.py seed_hitzones`

## Notas de entorno

- El contenedor `css` de Tailwind entró en restart loop por errores
  `posix_spawn` del entorno; el CSS quedó compilado una vez y se recompila en
  el arranque de `web` (`entrypoint.local.sh`). Recuperar con
  `docker compose up -d css` cuando el entorno se estabilice.
- `config/settings.py` usa `ManifestStaticFilesStorage` solo con `DEBUG=False`
  (en dev no requiere `collectstatic`).
- mhw-db no expone hitzones: se cargan con `seed_hitzones` (datos de la
  comunidad en `core/data/hitzones.json`; cubren 33 grandes monstruos).
- Para producción en Vercel: usa `DATABASE_URL` con pooling (puerto 6543 en Neon), `DEBUG=0`, y `collectstatic` corre en el build del Dockerfile.