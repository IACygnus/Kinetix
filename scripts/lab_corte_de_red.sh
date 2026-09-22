#!/usr/bin/env bash
# ===========================================================================
# ETAPA O2b.3 — ¿que pasa si el agente pierde la red? (O-D22)
# ===========================================================================
#
#   bash scripts/lab_corte_de_red.sh [minutos_de_corte]
#
# Un corte de red durante una prueba es lo normal, no la excepcion: un
# cortafuegos que se reinicia, un salto de red, un despliegue. La pregunta que
# hay que responder antes de prometerle nada a un cliente es si en ese rato se
# pierden los datos o solo se retrasan.
#
# El corte es de VERDAD, a nivel de red: se desconecta el servidor de la red por
# la que alcanza a InfluxDB. No se para el agente ni se toca su configuracion.
#
# Durante el corte el servidor sigue trabajando —la carga la genera `lab_db`
# contra la tienda, por la red del laboratorio, que no se toca—, asi que hay
# datos que perder.
set -euo pipefail
export MSYS2_ARG_CONV_EXCL='/tmp;/proc;/opt;/etc;/var;/run'

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVIDOR="${KX_SERVIDOR:-lab_servidor}"
RED_KINETIX="${KX_RED:-kinetix_jmeter_network}"
INFLUX="${KX_INFLUX_CONTENEDOR:-jmeter_influxdb}"
OPERADOR="${KX_INFLUX_TOKEN:-jmeter-token-2024-super-secret}"
MINUTOS="${1:-3}"

flux() { docker exec "$INFLUX" influx query --raw --host http://localhost:8086 \
             -t "$OPERADOR" --org performance "$1" 2>/dev/null; }
ahora() { date -u +%Y-%m-%dT%H:%M:%SZ; }

MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" pgrep -x telegraf >/dev/null \
    || { echo "el agente no esta instalado en $SERVIDOR" >&2; exit 1; }

CORRIDA="zztest-corte-$(date +%Y%m%d-%H%M%S)"
echo "=== 1. La corrida ==="
bash "$RAIZ/scripts/lab_corrida.sh" "$CORRIDA"

echo
echo "=== 2. Carga desde lab_db, por la red del laboratorio ==="
# Se genera desde dentro del laboratorio a proposito: asi la carga NO depende
# de la red que vamos a cortar, y el servidor sigue teniendo trabajo —y por
# tanto metricas que perder— mientras esta incomunicado.
MSYS_NO_PATHCONV=1 docker exec -d lab_db sh -c '
    end=$(( $(date +%s) + 600 ))
    while [ "$(date +%s)" -lt "$end" ]; do
        wget -q -O /dev/null "http://lab_servidor:8080/buscar?q=a1b" 2>/dev/null
        wget -q -O /dev/null "http://lab_servidor:8080/productos?limite=50" 2>/dev/null
    done'
echo "    generando carga (hasta 10 minutos)"
sleep 45

T_ANTES="$(ahora)"
echo
echo "=== 3. EL CORTE: se desconecta $SERVIDOR de $RED_KINETIX ==="
docker network disconnect "$RED_KINETIX" "$SERVIDOR"
T_CORTE="$(ahora)"
echo "    cortado a las $T_CORTE"
echo "    comprobando que de verdad no llega:"
if MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" timeout 8 \
       sh -c 'wget -q -O /dev/null http://influxdb:8086/health' 2>/dev/null; then
    echo "    ATENCION: el servidor TODAVIA alcanza InfluxDB; el corte no es real" >&2
    docker network connect "$RED_KINETIX" "$SERVIDOR"
    exit 1
fi
echo "    confirmado: InfluxDB no se alcanza desde el servidor"

echo "    esperando $MINUTOS minutos con el servidor incomunicado..."
sleep $((MINUTOS * 60))
T_FIN_CORTE="$(ahora)"

echo
echo "=== 4. Se restablece la red ==="
docker network connect "$RED_KINETIX" "$SERVIDOR"
echo "    reconectado a las $(ahora)"
echo "    esperando 90 s a que el agente vacie lo que guardo..."
sleep 90
T_DESPUES="$(ahora)"

echo
echo "=== 5. ¿Cuantos segundos del corte se recuperaron? ==="
DURACION_CORTE=$(( $(date -u -d "$T_FIN_CORTE" +%s) - $(date -u -d "$T_CORTE" +%s) ))
ESPERADOS=$DURACION_CORTE

contar() {   # contar <modo> <desde> <hasta>
    flux "
from(bucket: \"infra\")
  |> range(start: $2, stop: $3)
  |> filter(fn: (r) => r[\"_measurement\"] == \"cpu\" and r[\"host\"] == \"$SERVIDOR\")
  |> filter(fn: (r) => r[\"corrida\"] == \"$CORRIDA\")
  |> filter(fn: (r) => r[\"modo\"] == \"$1\" and r[\"_field\"] == \"usage_idle\")
  |> count()
  |> keep(columns: [\"_value\"])" | sed -n 's/^,,0,//p' | head -1
}

ANTES_AG="$(contar agente "$T_ANTES" "$T_CORTE")"
CORTE_AG="$(contar agente "$T_CORTE" "$T_FIN_CORTE")"
CORTE_SIN="$(contar sin_agente "$T_CORTE" "$T_FIN_CORTE")"

echo "    ventana del corte: $T_CORTE -> $T_FIN_CORTE  ($DURACION_CORTE s)"
echo
printf "    %-34s %s\n" "puntos del agente ANTES del corte" "${ANTES_AG:-0}"
printf "    %-34s %s de %s esperados\n" "puntos del agente DURANTE el corte" \
       "${CORTE_AG:-0}" "$ESPERADOS"
printf "    %-34s %s\n" "puntos SIN AGENTE durante el corte" "${CORTE_SIN:-0}"
echo

PERDIDOS=$(( ESPERADOS - ${CORTE_AG:-0} ))
if [ "${CORTE_AG:-0}" -ge $(( ESPERADOS * 98 / 100 )) ]; then
    echo "    PASA  | el agente recupero el $(( 100 * ${CORTE_AG:-0} / ESPERADOS )) % del corte"
    echo "            (faltan $PERDIDOS segundos: el redondeo de los bordes de la ventana)"
    SALIDA=0
else
    echo "    FALLA | se perdieron $PERDIDOS segundos de $ESPERADOS"
    echo "            O-D22: PARADA. Hay que proponer una alternativa con"
    echo "            colchon en disco antes de prometerle esto a un cliente."
    SALIDA=1
fi

echo
echo "=== 6. Se suelta la corrida y se para la carga ==="
MSYS_NO_PATHCONV=1 docker exec lab_db sh -c "pkill -f 'lab_servidor:8080' 2>/dev/null; pkill wget 2>/dev/null; true" >/dev/null 2>&1 || true
bash "$RAIZ/scripts/lab_corrida.sh" --limpiar >/dev/null
echo "    hecho.  corrida: $CORRIDA"
exit "$SALIDA"
