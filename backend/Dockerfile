FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema (incluye WeasyPrint deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libffi-dev \
    libcairo2 \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar codigo
COPY . .

# Crear directorios
RUN mkdir -p /app/uploads /app/logs

EXPOSE 8001

# Comando
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
