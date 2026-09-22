#!/usr/bin/env bash
# ===========================================================================
# ETAPA O2a.3 - la prueba que importa
# ===========================================================================
#
# Lanza carga contra el laboratorio usando la configuracion de «Monitoreo en
# vivo» (O1) y comprueba que el servidor y la base se ven trabajar en el cubo
# `infra` con la MISMA etiqueta de corrida.
#
#   bash scripts/lab_prueba_correlacion.sh
#
# Corre desde el anfitrion porque hay dos cosas que no se pueden hacer desde
# dentro de un contenedor: poner la etiqueta de corrida en el recolector
# (`docker kill -s HUP`) y preguntarle a lab_db con su propio psql.
#
# Regla 34: contra `jmeter_analyzer_test` por el 8002, no contra la base de
# Fredy. Regla 29: la corrida lleva la marca `zztest-`.
set -euo pipefail

# Git Bash en Windows «ayuda» traduciendo cualquier argumento que empiece por
# barra a una ruta de Windows: `/tmp/e2e/x.py` le llega al contenedor como
# `C:/Users/.../tmp/e2e/x.py` y no existe. Se excluyen solo las rutas de DENTRO
# del contenedor: apagar la traduccion entera romperia el `docker cp`, que si
# necesita que `/c/proyectos/...` se vuelva `C:\proyectos\...`. En Linux esta
# variable no molesta.
export MSYS2_ARG_CONV_EXCL='/tmp;KX_SESION=;KX_JMX='

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${KX_BACKEND:-jmeter_backend}"
ENTORNO="$RAIZ/lab/lab.env"

[ -f "$ENTORNO" ] || { echo "falta $ENTORNO: corre scripts/lab_preparar.sh"; exit 1; }
# shellcheck disable=SC1090
. "$ENTORNO"

for contenedor in lab_servidor lab_db lab_colector; do
    docker ps --format '{{.Names}}' | grep -qx "$contenedor" \
        || { echo "$contenedor no esta levantado"; exit 1; }
done

echo "=== 1. La configuracion, pedida a Kinetix como lo hace la pantalla ==="
docker cp "$RAIZ/lab/prueba/zztest_lab.jmx" "$BACKEND:/tmp/zztest_lab.jmx" >/dev/null
SALIDA="$(docker exec \
    -e KX_API=http://localhost:8002/api/v1 \
    -e KX_SESION=/tmp/e2e_sesion_test.json \
    -e KX_TOKEN_ESCRITURA="$KX_TOKEN_ESCRITURA" \
    "$BACKEND" python3 /tmp/e2e/o2a3_config.py)"
echo "$SALIDA"
CORRIDA="$(echo "$SALIDA" | sed -n 's/^APPLICATION=//p')"
[ -n "$CORRIDA" ] || { echo "no se obtuvo el nombre de la corrida"; exit 1; }

echo
echo "=== 2. El recolector pasa a escribir con esa corrida (O-D14) ==="
bash "$RAIZ/scripts/lab_corrida.sh" "$CORRIDA"

echo
echo "=== 3. Reposo, prueba, reposo ==="
docker exec \
    -e KX_REPOSO="${KX_REPOSO:-70}" \
    -e KX_DURACION="${KX_DURACION:-120}" \
    -e KX_USUARIOS="${KX_USUARIOS:-12}" \
    "$BACKEND" python3 /tmp/e2e/o2a3_correlacion.py
CODIGO=$?

echo
echo "=== 4. El rol del recolector no puede leer los datos (O-D12) ==="
if docker exec -e PGPASSWORD="$LAB_PG_LECTOR_PASSWORD" lab_db \
        psql -h localhost -U kinetix_lector -d "$LAB_PG_DB" \
        -tAc 'select count(*) from productos' >/dev/null 2>&1; then
    echo "FALLA | el rol PUEDE leer la tabla productos"
    CODIGO=1
else
    echo "PASA  | leer 'productos' con el rol del recolector da permiso denegado"
fi
if docker exec -e PGPASSWORD="$LAB_PG_LECTOR_PASSWORD" lab_db \
        psql -h localhost -U kinetix_lector -d "$LAB_PG_DB" \
        -tAc 'select count(*) from pg_stat_database' >/dev/null 2>&1; then
    echo "PASA  | pero si puede leer las vistas de estadistica"
else
    echo "FALLA | el rol no puede leer ni las vistas de estadistica"
    CODIGO=1
fi

echo
echo "=== 5. Se suelta la corrida ==="
bash "$RAIZ/scripts/lab_corrida.sh" --limpiar

echo
echo "El tablero: http://localhost:3000/d/kinetix-infraestructura?var-corrida=$CORRIDA"
exit "$CODIGO"
