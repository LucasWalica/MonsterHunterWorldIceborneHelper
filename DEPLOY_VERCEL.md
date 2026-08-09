# Despliegue en Vercel (Docker)

Este proyecto está listo para desplegarse en Vercel usando un contenedor Docker.

## Requisitos previos

1. Cuenta en [Vercel](https://vercel.com)
2. [Vercel CLI](https://vercel.com/docs/cli) instalado: `npm i -g vercel`
3. Base de datos PostgreSQL (recomendado: [Neon](https://neon.tech), [Supabase](https://supabase.com), [Railway](https://railway.app), o [PlanetScale](https://planetscale.com) para MySQL)
4. El repositorio en GitHub/GitLab/Bitbucket

## Variables de entorno necesarias

Configura estas variables en **Vercel Dashboard → Project → Settings → Environment Variables**:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DEBUG` | `0` en producción | `0` |
| `SECRET_KEY` | Clave secreta de Django (genera una nueva) | `django-insecure-xxx...` |
| `ALLOWED_HOSTS` | Dominios permitidos (separados por coma) | `tu-app.vercel.app,localhost` |
| `DATABASE_URL` | URL de conexión PostgreSQL (pooler) | `postgresql://user:pass@host/db?sslmode=require` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes de confianza para CSRF | `https://tu-app.vercel.app` |
| `SECURE_SSL_REDIRECT` | Forzar HTTPS | `1` |
| `SESSION_COOKIE_SECURE` | Cookies solo HTTPS | `1` |
| `CSRF_COOKIE_SECURE` | Cookie CSRF solo HTTPS | `1` |

### Generar `SECRET_KEY`

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Despliegue paso a paso

### 1. Conectar repositorio a Vercel

```bash
# En la raíz del proyecto
vercel login
vercel link
```

O desde el dashboard de Vercel: **Add New → Project → Import Git Repository**.

### 2. Configurar el proyecto

- **Framework Preset**: `Other`
- **Build Command**: (vacío, usa Dockerfile)
- **Output Directory**: (vacío)
- **Install Command**: (vacío)

Vercel detectará automáticamente el `Dockerfile` y usará la construcción de contenedor.

### 3. Variables de entorno

En **Settings → Environment Variables**, añade todas las variables de la tabla anterior para **Production**, **Preview** y **Development**.

### 4. Base de datos PostgreSQL

#### Opción A: Neon (recomendado, gratis)
1. Crea proyecto en https://neon.tech
2. Copia la **Connection string** (pooled)
3. Añade como `DATABASE_URL` en Vercel

#### Opción B: Supabase
1. Crea proyecto en https://supabase.com
2. Settings → Database → Connection pooling → URI
3. Añade como `DATABASE_URL`

#### Opción C: Railway / Render / Fly.io
Similar, obtén la URL de conexión con pooling.

> **Importante**: Usa siempre el **pooled connection string** (puerto 5432 o 6543), no el directo, para evitar agotar conexiones en serverless.

### 5. Desplegar

```bash
vercel --prod
```

O haz push a la rama principal (`main`/`master`) y Vercel desplegará automáticamente.

## Migraciones y datos iniciales

La primera vez (o tras cambios de modelo), ejecuta migraciones y ETL:

```bash
# En local con acceso a la BD de producción (usa DATABASE_URL de Vercel)
export DATABASE_URL="postgresql://..."
python manage.py migrate
python manage.py etl_mhw_data
python manage.py seed_hitzones
```

O crea un **Vercel Cron Job** / GitHub Action para correr esto periódicamente.

## Comandos útiles

```bash
# Ver logs en producción
vercel logs <deployment-url>

# Ejecutar comando en el contenedor (requiere Vercel Pro)
vercel exec <deployment-url> python manage.py shell

# Redesplegar sin cambios
vercel redeploy <deployment-url>

# Ver variables de entorno
vercel env ls
```

## Limitaciones en Vercel (serverless)

| Límite | Valor | Mitigación |
|--------|-------|------------|
| Timeout | 60s (Hobby) / 300s (Pro) | Optimiza consultas lentas; usa `select_related`/`prefetch_related` |
| Tamaño del bundle | 250MB | El Dockerfile es ligero (~150MB) |
| Conexiones DB | Limitadas | Usa **pooled connection** (PgBouncer) |
| Sistema de archivos | Solo lectura | No guardes archivos en `/app`; usa S3/Cloudflare R2 |

## Configuración de `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`

Para que funcione en `tu-app.vercel.app` y previews:

```bash
# En Vercel Dashboard, añade:
ALLOWED_HOSTS=.vercel.app,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
```

El punto inicial en `.vercel.app` permite subdominios (previews).

## Health check

Vercel verifica `/` por defecto. La vista `home` responde 200 OK.

## Dominio personalizado

En **Settings → Domains**, añade tu dominio y configura DNS según instrucciones de Vercel.

## Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| `DisallowedHost` | `ALLOWED_HOSTS` incorrecto | Añade `.vercel.app` y tu dominio |
| `CSRF verification failed` | `CSRF_TRUSTED_ORIGINS` | Añade `https://*.vercel.app` |
| `Connection timeout` DB | Pool agotado / sin pooling | Usa connection string pooled (puerto 6543 en Neon) |
| `Static files 404` | `collectstatic` no corrió | El Dockerfile lo hace en build; verifica `DEBUG=0` |
| `TemplateDoesNotExist` | Rutas de templates | Verifica `TEMPLATES['DIRS']` en `settings.py` |

## Archivos relevantes

- `Dockerfile` — Imagen de producción (Gunicorn + WhiteNoise)
- `requirements.txt` — Dependencias Python
- `config/settings.py` — Configuración Django (lee variables de entorno)
- `docker-compose.yml` — Solo para desarrollo local (Postgres + Tailwind watch)

## Desarrollo local con Docker Compose

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py etl_mhw_data
docker compose exec web python manage.py seed_hitzones
# http://localhost:8000
```

## Desarrollo local sin Docker (SQLite)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py etl_mhw_data --limit 100  # rápido para test
python manage.py seed_hitzones
python manage.py runserver
```

---

**¡Listo!** Tu app MHW Iceborne estará corriendo en Vercel con auto-deploy en cada push.