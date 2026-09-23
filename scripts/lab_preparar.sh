#!/usr/bin/env bash
# ===========================================================================
# ETAPA O2a - preparar el laboratorio ANTES de levantarlo
# ===========================================================================
#
# Es idempotente: se puede volver a ejecutar sin miedo. No borra nada y no toca
# ni un dato de Kinetix.
#
#   1. La pareja de llaves SSH del lector (O-D11). La privada NO se versiona.
#   2. El cubo `infra` en InfluxDB y un token de SOLO ESCRITURA para el (O-D15).
#      El token maestro no se usa ni se copia a ningun sitio.
#   3. `lab/lab.env` con las contrasenas del laboratorio. Tampoco se versiona.
#
# Uso:  bash scripts/lab_preparar.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLAVES="$RAIZ/lab/llaves"
ENTORNO="$RAIZ/lab/lab.env"

INFLUX_CONTENEDOR="${KX_INFLUX_CONTENEDOR:-jmeter_influxdb}"
INFLUX_ORG="${INFLUXDB_ORG:-performance}"
INFLUX_CUBO="${LAB_INFLUX_BUCKET:-infra}"
INFLUX_MAESTRO="${INFLUXDB_TOKEN:-jmeter-token-2024-super-secret}"
RETENCION="${LAB_INFLUX_RETENCION:-720h}"

influx_en_contenedor() {
    docker exec "$INFLUX_CONTENEDOR" influx "$@" \
        --host http://localhost:8086 -t "$INFLUX_MAESTRO"
}

clave_al_azar() {
    # Sin `head` en mitad de la tuberia: cierra el grifo, el proceso de la
    # izquierda recibe SIGPIPE y con `pipefail` eso mata el script entero.
    dd if=/dev/urandom bs=96 count=1 2>/dev/null \
        | base64 | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-28
}

# ---------------------------------------------------------------------------
echo "== 1. Llaves SSH del lector (O-D11)"
mkdir -p "$LLAVES"
if [ -f "$LLAVES/kinetix_lector" ]; then
    echo "   ya existen; no se tocan"
else
    ssh-keygen -t ed25519 -N '' -C 'kinetix_lector@laboratorio' \
        -f "$LLAVES/kinetix_lector" >/dev/null
    echo "   creadas: $LLAVES/kinetix_lector{,.pub}"
fi
chmod 600 "$LLAVES/kinetix_lector" 2>/dev/null || true

# ---------------------------------------------------------------------------
echo "== 2. Cubo '$INFLUX_CUBO' y token de solo escritura (O-D15)"
if influx_en_contenedor bucket list --name "$INFLUX_CUBO" >/dev/null 2>&1; then
    echo "   el cubo ya existe; no se recrea"
else
    influx_en_contenedor bucket create \
        --name "$INFLUX_CUBO" --org "$INFLUX_ORG" --retention "$RETENCION" >/dev/null
    echo "   cubo creado con retencion $RETENCION"
fi

CUBO_ID="$(influx_en_contenedor bucket list --name "$INFLUX_CUBO" \
    | awk 'NR==2 {print $1}')"
[ -n "$CUBO_ID" ] || { echo "   no se pudo leer el id del cubo"; exit 1; }
echo "   id del cubo: $CUBO_ID"

DESCRIPCION="kinetix-infra-escritura"
# Columna 2 la descripcion, columna 3 el token. La tabla se alinea con varios
# tabuladores seguidos, asi que se parte por espacios, no por `-F'\t'`.
TOKEN_EXISTENTE="$(influx_en_contenedor auth list 2>/dev/null \
    | awk -v d="$DESCRIPCION" '$2 == d { print $3; exit }' || true)"

if [ -n "${TOKEN_EXISTENTE:-}" ]; then
    LAB_INFLUX_TOKEN="$TOKEN_EXISTENTE"
    echo "   el token '$DESCRIPCION' ya existia; se reutiliza"
else
    LAB_INFLUX_TOKEN="$(influx_en_contenedor auth create \
        --org "$INFLUX_ORG" \
        --write-bucket "$CUBO_ID" \
        --description "$DESCRIPCION" \
        --json | tr -d ' \n' | sed 's/.*"token":"\([^"]*\)".*/\1/')"
    echo "   token creado: solo escritura, solo el cubo '$INFLUX_CUBO'"
fi
[ -n "$LAB_INFLUX_TOKEN" ] || { echo "   no se pudo obtener el token"; exit 1; }

# ---------------------------------------------------------------------------
echo "== 3. Token de SOLO LECTURA para las graficas de Kinetix (O-D33)"
#
# Lee los DOS cubos: `infra` para las metricas de los servidores y `jmeter`
# para las de la prueba. La pantalla de sesiones (O2d) las pinta en el mismo
# eje de tiempo, y con un token que solo leyera `infra` la mitad de arriba
# saldria vacia con un 404.
#
# No escribe en ninguno: para eso estan los de escritura, que siguen siendo
# otros y siguen siendo de solo escritura.
if [ -f "$ENTORNO" ]; then
    echo "   ya existe; solo se actualiza el token"
    # shellcheck disable=SC1090
    . "$ENTORNO"
    PG_PASSWORD="${LAB_PG_PASSWORD:-$(clave_al_azar)}"
    PG_LECTOR="${LAB_PG_LECTOR_PASSWORD:-$(clave_al_azar)}"
else
    PG_PASSWORD="$(clave_al_azar)"
    PG_LECTOR="$(clave_al_azar)"
fi

# El token de escritura del cubo `jmeter` es el de O-D2, el que ya usa la
# pantalla de Monitoreo en vivo. Aqui solo se recoge para la prueba de O2a.3;
# no se crea ninguno nuevo.
TOKEN_JMETER="$(influx_en_contenedor auth list 2>/dev/null \
    | awk '$2 == "kinetix-jmeter-escritura" { print $3; exit }' || true)"
CUBO_JMETER="$(influx_en_contenedor bucket list --name jmeter 2>/dev/null \
    | awk 'NR==2 {print $1}')"
TOKEN_LECTURA="$(influx_en_contenedor auth list 2>/dev/null \
    | awk '$2 == "kinetix-lectura" { print $3; exit }' || true)"
if [ -n "${TOKEN_LECTURA:-}" ]; then
    echo "   el token 'kinetix-lectura' ya existia; se reutiliza"
else
    TOKEN_LECTURA="$(influx_en_contenedor auth create \
        --org "$INFLUX_ORG" \
        --read-bucket "$CUBO_ID" \
        --read-bucket "$CUBO_JMETER" \
        --description "kinetix-lectura" \
        --json | tr -d ' \n' | sed 's/.*"token":"\([^"]*\)".*/\1/')"
    echo "   token creado: solo lectura, cubos 'infra' y 'jmeter'"
fi
[ -n "$TOKEN_LECTURA" ] || { echo "   no se pudo obtener el token de lectura"; exit 1; }

# ---------------------------------------------------------------------------
echo "== 4. lab/lab.env"

cat > "$ENTORNO" <<ENV
# Laboratorio de observabilidad - ETAPA O2a.
# Lo genera scripts/lab_preparar.sh. NO se versiona (ver lab/.gitignore).
LAB_CLIENTE=laboratorio
LAB_PG_DB=tienda
LAB_PG_USER=tienda
LAB_PG_PASSWORD=$PG_PASSWORD
LAB_PG_LECTOR_PASSWORD=$PG_LECTOR
LAB_INFLUX_BUCKET=$INFLUX_CUBO
LAB_INFLUX_TOKEN=$LAB_INFLUX_TOKEN
INFLUXDB_ORG=$INFLUX_ORG
# El de O-D2, solo para la prueba de correlacion de O2a.3.
KX_TOKEN_ESCRITURA=$TOKEN_JMETER
# El de solo lectura, el que dibuja las graficas de la pantalla de sesiones.
KX_TOKEN_LECTURA=$TOKEN_LECTURA
ENV
chmod 600 "$ENTORNO" 2>/dev/null || true
echo "   escrito: $ENTORNO"

echo
echo "Listo. Ahora, el comando que levanta el laboratorio:"
echo
echo "   docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml up -d --build"
echo
