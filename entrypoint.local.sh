#!/bin/sh
# Entrypoint de desarrollo: compila Tailwind, aplica migraciones y arranca Django.
set -e

if command -v tailwindcss >/dev/null 2>&1; then
    echo "==> Compilando Tailwind CSS (one-shot)"
    tailwindcss -i ./src/input.css -o ./static/css/output.css
fi

echo "==> Aplicando migraciones"
python manage.py migrate --noinput

echo "==> Django runserver en 0.0.0.0:8000"
exec python manage.py runserver 0.0.0.0:8000
