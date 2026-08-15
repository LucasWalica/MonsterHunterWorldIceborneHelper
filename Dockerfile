# Dockerfile para Vercel (producción)
# Vercel requiere que el contenedor escuche en el puerto 8080
# y que la aplicación esté lista para servir tráfico HTTP.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Dependencias del sistema (PostgreSQL client, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copiar código
COPY . .

# Recopilar estáticos (requiere DEBUG=False)
ENV DEBUG=0
RUN python manage.py collectstatic --noinput

# Crear usuario no-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Gunicorn con threads (un contenedor Vercel tiene 1 vCPU: 2 workers es
# óptimo en memoria/CPU; los threads amortizan el bloqueo en queries DB).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]