#!/usr/bin/env bash
# ===========================================================================
# ETAPA O2b.2 — los dos modos, lado a lado
# ===========================================================================
#
#   bash scripts/lab_comparar_modos.sh
#
# Dos preguntas, y las dos se responden con numeros:
#
#   1. ¿Que ve el agente (1 s) que el modo sin agente (10 s) no ve?
#      Se provoca un pico CORTO a proposito —tres segundos de CPU al maximo— y
#      se mira que dice cada modo. Diez segundos de media aplastan un pico de
#      tres: eso no es una opinion, se ve en la cifra.
#
#   2. ¿Cuanto le cuesta el agente al servidor?
#      Se mide antes y durante la prueba. Es la primera pregunta de un cliente.
set -euo pipefail
export MSYS2_ARG_CONV_EXCL='/tmp;/proc;/opt;/etc;/var;/run;KX_SESION=;KX_JMX='

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVIDOR="${KX_SERVIDOR:-lab_servidor}"
INFLUX="${KX_INFLUX_CONTENEDOR:-jmeter_influxdb}"
OPERADOR="${KX_INFLUX_TOKEN:-jmeter-token-2024-super-secret}"
SEGUNDOS_PICO="${KX_PICO:-3}"

flux() { docker exec "$INFLUX" influx query --raw --host http://localhost:8086 \
             -t "$OPERADOR" --org performance "$1" 2>/dev/null; }

en_servidor() { MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" "$@"; }

en_servidor pgrep -x telegraf >/dev/null \
    || { echo "el agente no esta instalado en $SERVIDOR" >&2; exit 1; }

CORRIDA="zztest-comparacion-$(date +%Y%m%d-%H%M%S)"
echo "=== 1. La misma corrida en los dos modos (O-D14) ==="
bash "$RAIZ/scripts/lab_corrida.sh" "$CORRIDA"

echo
echo "=== 2. El coste del agente en reposo ==="
bash "$RAIZ/lab/agente/medir_coste.sh" 40 | sed -n '/CPU/,/Salida/p'

echo
echo "=== 3. Un pico de $SEGUNDOS_PICO segundos, a proposito ==="
INICIO_PICO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# Cada bucle se mata SOLO, con `timeout`. La primera version los lanzaba en
# segundo plano y los mataba con `kill $(jobs -p)`: en un `sh -c` no
# interactivo esa lista sale vacia, los bucles sobrevivieron al guion y
# dejaron la maquina a carga 13 quemando CPU hasta que los vi. Un proceso que
# se apaga solo no depende de que nadie se acuerde de apagarlo.
en_servidor sh -c "
    N=\$(nproc)
    i=0; while [ \$i -lt \$N ]; do
        timeout $SEGUNDOS_PICO sh -c 'while :; do :; done' &
        i=\$((i+1))
    done
    wait" >/dev/null 2>&1 || true
FIN_PICO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "    pico de $INICIO_PICO a $FIN_PICO"
echo "    esperando a que los dos modos publiquen..."
sleep 25

VENTANA_INICIO="$(date -u -d "$INICIO_PICO - 25 seconds" +%Y-%m-%dT%H:%M:%SZ)"
VENTANA_FIN="$(date -u -d "$FIN_PICO + 25 seconds" +%Y-%m-%dT%H:%M:%SZ)"

for MODO in agente sin_agente; do
    echo
    echo "    --- modo=$MODO, CPU en uso alrededor del pico ---"
    flux "
from(bucket: \"infra\")
  |> range(start: $VENTANA_INICIO, stop: $VENTANA_FIN)
  |> filter(fn: (r) => r[\"_measurement\"] == \"cpu\" and r[\"host\"] == \"$SERVIDOR\")
  |> filter(fn: (r) => r[\"modo\"] == \"$MODO\" and r[\"_field\"] == \"usage_idle\")
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> keep(columns: [\"_time\", \"_value\"])
  |> sort(columns: [\"_time\"])" \
    | sed -n 's/^,,0,//p' \
    | awk -F, '{printf "      %s  %6.1f %%\n", substr($1,12,8), $2}'
done

echo
echo "    --- el maximo que ve cada modo ---"
for MODO in agente sin_agente; do
    MAX="$(flux "
from(bucket: \"infra\")
  |> range(start: $VENTANA_INICIO, stop: $VENTANA_FIN)
  |> filter(fn: (r) => r[\"_measurement\"] == \"cpu\" and r[\"host\"] == \"$SERVIDOR\")
  |> filter(fn: (r) => r[\"modo\"] == \"$MODO\" and r[\"_field\"] == \"usage_idle\")
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> max()
  |> keep(columns: [\"_value\"])" | sed -n 's/^,,0,//p' | head -1)"
    printf "      %-11s  %s %%\n" "$MODO" "${MAX:-sin dato}"
done

echo
echo "=== 4. La prueba de carga, con los dos modos escribiendo ==="
docker cp "$RAIZ/lab/prueba/zztest_lab.jmx" "jmeter_backend:/tmp/zztest_lab.jmx" >/dev/null
REGISTRO_JMETER="$(mktemp)"
# En segundo plano desde AQUI, no con `docker exec -d`: aquel se traga la
# salida y un JMeter que no arranca parece un JMeter que arranco.
MSYS_NO_PATHCONV=1 docker exec jmeter_backend /opt/apache-jmeter-5.6.3/bin/jmeter \
    -n -t /tmp/zztest_lab.jmx -l /tmp/zztest_o2b2.jtl \
    "-JinfluxdbUrl=http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter" \
    "-JinfluxdbToken=${KX_TOKEN_ESCRITURA:-}" \
    "-Japplication=$CORRIDA" -Jduracion=90 -Jusuarios=12 \
    > "$REGISTRO_JMETER" 2>&1 &
JMETER_PID=$!
sleep 12
if ! kill -0 "$JMETER_PID" 2>/dev/null; then
    echo "    JMeter no arranco:" >&2
    tail -12 "$REGISTRO_JMETER" >&2
    exit 1
fi
echo "    JMeter lanzado (90 s)"

echo
echo "=== 5. El coste del agente DURANTE la prueba ==="
sleep 15
bash "$RAIZ/lab/agente/medir_coste.sh" 60 | sed -n '/CPU/,/Salida/p'

echo "    esperando a que termine la prueba..."
# Se espera al proceso que lanzamos nosotros. La primera version preguntaba con
# `pgrep` DENTRO de jmeter_backend, que no trae `pgrep` ni `ps`: la orden
# fallaba con codigo 127 y el bucle salia a la primera vuelta, como si la
# prueba hubiera terminado ya.
wait "$JMETER_PID" 2>/dev/null || true
grep "summary =" "$REGISTRO_JMETER" | tail -1 | sed 's/^/    /' \
    || tail -3 "$REGISTRO_JMETER"
rm -f "$REGISTRO_JMETER"
sleep 20

echo
echo "=== 6. Lo que cada modo vio de la prueba ==="
resumen() {   # resumen <modo> <max|mean|count>
    flux "
from(bucket: \"infra\")
  |> range(start: -8m)
  |> filter(fn: (r) => r[\"_measurement\"] == \"cpu\" and r[\"host\"] == \"$SERVIDOR\")
  |> filter(fn: (r) => r[\"corrida\"] == \"$CORRIDA\")
  |> filter(fn: (r) => r[\"modo\"] == \"$1\" and r[\"_field\"] == \"usage_idle\")
  |> map(fn: (r) => ({ r with _value: 100.0 - r._value }))
  |> $2()
  |> keep(columns: [\"_value\"])" | sed -n 's/^,,0,//p' | head -1
}
for MODO in agente sin_agente; do
    printf "    %-11s  maximo %-8.8s  media %-8.8s  puntos %s\n" \
        "$MODO" "$(resumen "$MODO" max)" "$(resumen "$MODO" mean)" \
        "$(resumen "$MODO" count)"
done

echo
echo "=== 7. Se suelta la corrida ==="
bash "$RAIZ/scripts/lab_corrida.sh" --limpiar
echo
echo "Tablero: http://localhost:3000/d/kinetix-infraestructura?var-corrida=$CORRIDA"
