# ============================================================================
# Sprint 2.5a — Multi-stage build
#
# Stage 1 (jmeter-base): descarga Apache JMeter 5.6.3 + Plugins Manager + jpgc
#   plugins. Se cachea porque las versiones son fijas — solo se reinstala
#   cuando estas lineas cambian.
# Stage 2 (app): la imagen runtime — python:3.11-slim + apt deps de la app +
#   openjdk-17-jre-headless + JMeter copiado del stage 1.
#
# El stage 1 usa eclipse-temurin:17-jre-jammy solo durante el build (Java
# 17 + apt para wget/unzip). El stage 2 reusa python:3.11-slim para
# preservar el entorno Python/FastAPI tal como estaba pre-2.5a.
# ============================================================================


# ----------------------------------------------------------------------------
# Stage 1: jmeter-base
# ----------------------------------------------------------------------------
FROM eclipse-temurin:17-jre-jammy AS jmeter-base

ARG JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/apache-jmeter-${JMETER_VERSION}
ENV PATH="${JMETER_HOME}/bin:${PATH}"

# Herramientas para descargar/extraer JMeter y plugins
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        unzip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Apache JMeter 5.6.3 (descarga oficial Apache Archive)
RUN cd /opt && \
    wget -q "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz" && \
    tar -xzf "apache-jmeter-${JMETER_VERSION}.tgz" && \
    rm "apache-jmeter-${JMETER_VERSION}.tgz"

# Plugin Manager (necesario para instalar los demas plugins desde CLI)
RUN cd ${JMETER_HOME}/lib/ext && \
    wget -q "https://jmeter-plugins.org/get/" -O jmeter-plugins-manager-1.10.jar

# CMDRunner — requerido por PluginsManagerCMD para correr desde CLI
RUN cd ${JMETER_HOME}/lib && \
    wget -q "https://repo1.maven.org/maven2/kg/apc/cmdrunner/2.3/cmdrunner-2.3.jar"

# Instalar el wrapper PluginsManagerCMD.sh
RUN java -cp ${JMETER_HOME}/lib/ext/jmeter-plugins-manager-1.10.jar \
        org.jmeterplugins.repository.PluginManagerCMDInstaller && \
    chmod +x ${JMETER_HOME}/bin/PluginsManagerCMD.sh

# Plugins jpgc:
#   - jpgc-casutg: Custom Thread Groups (Stepping, Ultimate, Concurrency, Arrivals).
#   - jpgc-functions: funciones extra (__strReplace, __unescapeHtml, etc.).
#   - jpgc-graphs-basic: Response Times Over Time, Transactions Per Second, etc.
#   - jpgc-tst: Throughput Shaping Timer.
# Si la instalacion parcial falla, no abortamos el build — el smoke test
# de la PARTE 5 confirma cuales quedaron disponibles.
RUN ${JMETER_HOME}/bin/PluginsManagerCMD.sh install \
        jpgc-casutg,jpgc-functions,jpgc-graphs-basic,jpgc-tst \
    || echo "WARN: instalacion de plugins parcial — el smoke confirma."

# Verificacion local (no abortar si grep no encuentra — solo log)
RUN ${JMETER_HOME}/bin/jmeter -v 2>&1 | head -10 || true


# ----------------------------------------------------------------------------
# Stage 2: app — imagen runtime
#
# Reproduce el Dockerfile pre-2.5a (python:3.11-slim + apt deps de la app)
# y agrega openjdk-17-jre-headless + JMeter copiado del stage 1.
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS app

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instalar dependencias del sistema (incluye WeasyPrint deps + Java 21 para JMeter).
# Nota: python:3.11-slim usa Debian trixie, donde openjdk-17 ya no esta en
# el repo principal — se usa openjdk-21-jre-headless (JMeter 5.6.3 esta
# oficialmente soportado en Java 17 y 21).
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
    tesseract-ocr \
    tesseract-ocr-spa \
    openjdk-21-jre-headless \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Sprint 2.5a — copiar JMeter completo desde el stage anterior
COPY --from=jmeter-base /opt/apache-jmeter-5.6.3 /opt/apache-jmeter-5.6.3
ENV JMETER_HOME=/opt/apache-jmeter-5.6.3
ENV PATH="${JMETER_HOME}/bin:${PATH}"

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
