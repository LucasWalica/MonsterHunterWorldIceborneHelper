"""Configuración del proyecto Monster Hunter World: Iceborne App."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [v for v in os.environ.get(name, default).split(",") if v]


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
)

# Acepta DJANGO_DEBUG (legado) y DEBUG (estándar en Vercel).
DEBUG = env_bool("DJANGO_DEBUG", env_bool("DEBUG", True))

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", os.environ.get("ALLOWED_HOSTS", "*")
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def _postgres_config(host, port, name, user, password):
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        # CONN_MAX_AGE=0: imprescindible con el pooler de Supabase
        # (PgBouncer en modo transacción no soporta conexiones persistentes).
        "CONN_MAX_AGE": 0,
    }


_database_url = (
    os.environ.get("DATABASE_URL")
    # Integración de storage de Vercel: inyecta STORAGE_<PROJECT>_POSTGRES_URL
    # (URL pooled, puerto 6543, correcta para serverless).
    or os.environ.get("STORAGE_MHW_POSTGRES_URL")
)

if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(_database_url, conn_max_age=0)
    }
elif os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": _postgres_config(
            os.environ.get("POSTGRES_HOST", "db"),
            os.environ.get("POSTGRES_PORT", "5432"),
            os.environ.get("POSTGRES_DB", "mhw"),
            os.environ.get("POSTGRES_USER", "mhw"),
            os.environ.get("POSTGRES_PASSWORD", "mhw"),
        )
    }
else:
    # Fallback para desarrollo local sin Docker / checks rápidos.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "es"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"

STATICFILES_DIRS = [BASE_DIR / "static"]

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Producción (Vercel): HTTPS, CSRF y cookies seguras.
# ---------------------------------------------------------------------------

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", os.environ.get("CSRF_TRUSTED_ORIGINS", "")
)

SECURE_SSL_REDIRECT = env_bool(
    "DJANGO_SECURE_SSL_REDIRECT", env_bool("SECURE_SSL_REDIRECT", False)
)

SESSION_COOKIE_SECURE = env_bool(
    "DJANGO_SESSION_COOKIE_SECURE", env_bool("SESSION_COOKIE_SECURE", False)
)

CSRF_COOKIE_SECURE = env_bool(
    "DJANGO_CSRF_COOKIE_SECURE", env_bool("CSRF_COOKIE_SECURE", False)
)
