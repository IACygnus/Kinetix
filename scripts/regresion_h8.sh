#!/usr/bin/env bash
# ===========================================================================
#  H8.6 — la regresion completa, desde el anfitrion
# ===========================================================================
#
#   bash scripts/regresion_h8.sh
#
# Lanza `backend/pruebas_e2e/cierre_h8.sh` dentro del contenedor, pero **con
# los secretos del laboratorio puestos**, leidos de `lab/lab.env`, que no se
# versiona. Sin ellos, tres suites de observabilidad se saltan.
#
# Por que no estan dentro del guion del contenedor: `cierre_o2d.sh` llevaba el
# token de escritura de InfluxDB en claro dentro del propio archivo versionado.
# Un secreto en un repositorio es un secreto quemado, aunque sea el de un
# laboratorio que solo escucha en 127.0.0.1.
#
# Despues quedan dos cosas que NO pueden correr desde dentro de un contenedor,
# y este guion las lanza tambien:
#
#   - las dos del laboratorio (O2a.3), que necesitan `docker kill -s HUP`
#     sobre el recolector y el psql de `lab_db`;
#   - las cifras del informe, que sacan su referencia de git.
#
# Con `--rapido` se salta esas dos: la del laboratorio tarda unos cinco minutos
# porque lanza carga de verdad.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${KX_BACKEND:-jmeter_backend}"
ENTORNO="$RAIZ/lab/lab.env"
RAPIDO=0
[ "${1:-}" = "--rapido" ] && RAPIDO=1

export MSYS2_ARG_CONV_EXCL='/tmp;/app'

LLAVE="$RAIZ/lab/llaves/kinetix_lector"

if [ -f "$ENTORNO" ]; then
    # shellcheck disable=SC1090
    . "$ENTORNO"
    echo "lab/lab.env cargado"
    # La llave SSH NO esta en lab.env: es un archivo, y lo que las suites de
    # O2c necesitan es su CONTENIDO —es la credencial que se le da de alta al
    # servidor observado—. Se lee aqui y no se imprime nunca.
    if [ -f "$LLAVE" ]; then
        KX_LLAVE_SSH="$(cat "$LLAVE")"
        export KX_LLAVE_SSH
        echo "lab/llaves/kinetix_lector cargada"
    else
        echo "AVISO: no esta $LLAVE — dos suites de O2c se saltaran."
        echo "       Se genera con scripts/lab_preparar.sh"
    fi
else
    echo "AVISO: no esta $ENTORNO — tres suites de observabilidad se saltaran."
    echo "       Se genera con scripts/lab_preparar.sh"
fi

CODIGO=0

# El laboratorio va PRIMERO, y no por gusto: deja una corrida recien escrita en
# los dos cubos, y `o2a4_tablero` la necesita **fresca**. Los paneles miran los
# ultimos 40 minutos, asi que una corrida de ayer no le sirve aunque su etiqueta
# siga ahi. Al reves —el laboratorio al final— el tablero se saltaria siempre.
if [ "$RAPIDO" -eq 0 ]; then
    echo "############################################################"
    echo "#  El laboratorio (O2a.3) — unos cinco minutos             #"
    echo "############################################################"
    bash "$RAIZ/scripts/lab_prueba_correlacion.sh" || CODIGO=1
    echo
fi

echo "############################################################"
echo "#  Las suites de dentro del contenedor                     #"
echo "############################################################"
docker exec \
    -e KX_TOKEN_ESCRITURA="${KX_TOKEN_ESCRITURA:-}" \
    -e LAB_PG_LECTOR_PASSWORD="${LAB_PG_LECTOR_PASSWORD:-}" \
    -e KX_LLAVE_SSH="${KX_LLAVE_SSH:-}" \
    "$BACKEND" sh /app/pruebas_e2e/cierre_h8.sh || CODIGO=1

if [ "$RAPIDO" -eq 1 ]; then
    echo
    echo "--rapido: no se lanzo el laboratorio ni las cifras del informe."
    exit "$CODIGO"
fi

echo
echo "############################################################"
echo "#  Las cifras del informe                                  #"
echo "############################################################"
bash "$RAIZ/scripts/d1_cifras.sh" || CODIGO=1

exit "$CODIGO"
