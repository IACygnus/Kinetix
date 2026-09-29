#!/usr/bin/env bash
# ===========================================================================
# ETAPA O2e.3 — el agente del laboratorio escribiendo por la ruta de ingesta
# ===========================================================================
#
#   bash scripts/lab_ingesta_o2e3.sh
#
# El agente de `lab_servidor` (O2b) deja de escribir en InfluxDB y pasa a
# escribir en `http://jmeter_backend:8002/api/v1/ingesta` —el backend de
# PRUEBAS (regla 34)— con un token de ingesta del cliente ZZTEST-Laboratorio O2e.
# El TLS de produccion lo pone nginx y no cambia nada aqui (O-D52).
#
# Casos (O-D52), cada uno medido en `infra`, en el log del agente y en el del
# backend de pruebas:
#   A. token bueno            llega un punto por segundo
#   B. etiqueta cambiada      400, no entra nada
#   C. token de otro cliente  400, no entra nada
#   D. cuerpo grande          corte de red de 4 min con lotes sin tope: al
#                             volver, 413 — ¿parte Telegraf 1.29.5 el lote?
#   E. ritmo excesivo         un relleno con el mismo token satura el cupo:
#                             429 con Retry-After, y el agente no pierde nada
#   F. token revocado         401, deja de entrar
#
# Al final el agente vuelve EXACTAMENTE a como estaba (se comprueba la huella
# de su `entorno`) y se imprime el entorno original junto al modificado, con el
# token tapado. **En InfluxDB no se borra nada** (regla 35, Fredy): lo escrito
# queda con `cliente=ZZTEST-Laboratorio O2e` y la retencion se lo lleva.
#
# Los tokens no pasan nunca por una linea de ordenes: viajan por stdin.
set -euo pipefail
export MSYS_NO_PATHCONV=1

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVIDOR="lab_servidor"
BACKEND="jmeter_backend"
INFLUX="jmeter_influxdb"
RED="kinetix_jmeter_network"
OPERADOR="${INFLUXDB_TOKEN:-jmeter-token-2024-super-secret}"
CLIENTE="ZZTEST-Laboratorio O2e"
URL_INGESTA="http://jmeter_backend:8002/api/v1/ingesta"
DIR="/etc/kinetix-agente"
CORTE_S="${KX_CORTE_S:-240}"
LOG_BACKEND="/tmp/backend_test.log"

en_servidor() { docker exec -i "$SERVIDOR" "$@"; }
ayudante() {
    docker exec -i -e KX_API=http://localhost:8002/api/v1 \
        -e KX_SESION=/tmp/e2e_sesion_test.json "$BACKEND" \
        python3 /app/pruebas_e2e/o2e3_ayudante.py "$1"
}
flux() { docker exec "$INFLUX" influx query --raw --host http://localhost:8086 \
             -t "$OPERADOR" --org performance "$1" 2>/dev/null | sed -n 's/^,,0,//p'; }
ahora() { date -u +%Y-%m-%dT%H:%M:%SZ; }

FALLOS=0
ok() { if [ "$1" = 1 ]; then echo "PASA  | $2"; else echo "FALLA | $2"; FALLOS=$((FALLOS+1)); fi; }

# Puntos de CPU (uno por segundo) de este cliente entre dos instantes.
segundos() {
    local n
    n=$(flux "from(bucket: \"infra\") |> range(start: $1, stop: $2)
  |> filter(fn: (r) => r._measurement == \"cpu\" and r._field == \"usage_idle\")
  |> filter(fn: (r) => r.host == \"$SERVIDOR\" and r.cliente == \"${3:-$CLIENTE}\")
  |> group() |> count() |> keep(columns: [\"_value\"])" | tr -d '\r')
    echo "${n:-0}"
}
# El hueco mas largo entre dos puntos seguidos, en segundos.
hueco_mayor() {
    local n
    n=$(flux "from(bucket: \"infra\") |> range(start: $1, stop: $2)
  |> filter(fn: (r) => r._measurement == \"cpu\" and r._field == \"usage_idle\")
  |> filter(fn: (r) => r.host == \"$SERVIDOR\" and r.cliente == \"$CLIENTE\")
  |> group() |> sort(columns: [\"_time\"]) |> elapsed(unit: 1s)
  |> max(column: \"elapsed\") |> keep(columns: [\"elapsed\"])" | tr -d '\r' | tail -1)
    echo "${n:-?}"
}

log_agente_desde() { en_servidor sh -c "wc -l < /var/log/kinetix-agente.log"; }
log_agente() { en_servidor sh -c "tail -n +$(( $1 + 1 )) /var/log/kinetix-agente.log"; }
log_backend_desde() { docker exec "$BACKEND" sh -c "wc -c < $LOG_BACKEND"; }
log_backend() {
    docker exec "$BACKEND" sh -c "tail -c +$(( $1 + 1 )) $LOG_BACKEND" \
        | grep -a "ingesta cliente=" || true
}

detener() {
    en_servidor sh -c '
        p=$(pgrep -x telegraf || true)
        [ -n "$p" ] && kill $p
        i=0; while pgrep -x telegraf >/dev/null && [ $i -lt 30 ]; do sleep 0.5; i=$((i+1)); done
        ! pgrep -x telegraf >/dev/null'
}

# Igual que el instalador cuando no hay systemd (instalar_agente.sh:201).
arrancar() {
    local conf="$1"
    en_servidor sh -c "
        setpriv --reuid=kinetix_agente --regid=kinetix_agente --init-groups -- \
          /bin/sh -c 'set -a; . $DIR/entorno; set +a; exec /opt/kinetix-agente/bin/telegraf --config $conf --config-directory $DIR/conf.d' \
          >> /var/log/kinetix-agente.log 2>&1 &
        echo \$! > /run/kinetix-agente.pid
        sleep 3
        kill -0 \$(cat /run/kinetix-agente.pid)"
}

# El entorno del agente. El cliente va ENTRE COMILLAS: sin ellas, un nombre con
# espacio deja KX_CLIENTE vacio al hacer `. entorno` (hallazgo de O2e.3; el
# instalador de O2b lo escribe sin comillas).
configurar() {   # $1 cliente  $2 token (por stdin)
    local token; token="$(cat)"
    printf "KX_HOST=%s\nKX_CLIENTE='%s'\nKX_INFLUX_URL=%s\nKX_INFLUX_ORG=performance\nKX_INFLUX_BUCKET=infra\nKX_INFLUX_TOKEN=%s\n" \
        "$SERVIDOR" "$1" "$URL_INGESTA" "$token" \
        | en_servidor sh -c "cat > $DIR/entorno && chown root:kinetix_agente $DIR/entorno && chmod 640 $DIR/entorno"
}

# El entorno, con el token tapado: su largo y el principio de su huella.
entorno_visible() {
    en_servidor sh -c "cat $1" | while IFS= read -r linea; do
        case "$linea" in
            KX_INFLUX_TOKEN=*)
                v="${linea#KX_INFLUX_TOKEN=}"
                echo "KX_INFLUX_TOKEN=<oculto: ${#v} caracteres, sha256 $(printf %s "$v" | sha256sum | cut -c1-12)>" ;;
            *) echo "$linea" ;;
        esac
    done
}

token_de() { docker exec -i "$BACKEND" python3 -c "import json,sys; print(json.load(sys.stdin)['$1']['$2'])" <<<"$TOKENS"; }

# ===========================================================================
echo "=== 0. Estado de partida ==="
en_servidor true || { echo "$SERVIDOR no responde"; exit 1; }
ESTABA_EN_MARCHA=0
en_servidor pgrep -x telegraf >/dev/null && ESTABA_EN_MARCHA=1
echo "    agente en marcha al empezar: $ESTABA_EN_MARCHA"
HUELLA_ORIGINAL="$(en_servidor sha256sum $DIR/entorno | cut -c1-64)"
en_servidor sh -c "[ -e $DIR/entorno.o2e3.original ] || cp -p $DIR/entorno $DIR/entorno.o2e3.original"
echo "    copia del entorno: $DIR/entorno.o2e3.original"

# Si algo falla a mitad, la red vuelve y el agente recupera su entorno. Al final
# del guion la copia ya no existe y esto no hace nada.
deshacer() {
    docker network connect "$RED" "$SERVIDOR" 2>/dev/null || true
    if docker exec "$SERVIDOR" test -e $DIR/entorno.o2e3.original 2>/dev/null; then
        echo "!!! el guion no termino: se devuelve el agente a su estado original"
        detener || true
        docker exec "$SERVIDOR" sh -c "cp -p $DIR/entorno.o2e3.original $DIR/entorno && rm -f $DIR/entorno.o2e3.original $DIR/agente.o2e3.conf"
        ayudante revocar-restos </dev/null || true
    fi
}
trap deshacer EXIT

echo
echo "=== 1. Foto de infra ANTES (regla 35) ==="
for t in cliente host modo; do
    printf "    %-8s " "$t"
    flux "import \"influxdata/influxdb/schema\"
schema.tagValues(bucket: \"infra\", tag: \"$t\", start: -30d)" | cut -d, -f2 | tr -d '\r' | paste -sd' '
done

echo
echo "=== 2. Backend de pruebas: token de infra, cliente y dos tokens de ingesta ==="
TOKENS="$(grep '^LAB_INFLUX_TOKEN=' "$RAIZ/lab/lab.env" | cut -d= -f2- | ayudante preparar)"
echo "    bueno: $(token_de bueno prefijo)…  (${CLIENTE})"
echo "    otro:  $(token_de otro prefijo)…  ($(token_de otro cliente))"
ayudante token | sed 's/^/    infra: /'
LB0="$(log_backend_desde)"

detener || true
cp_conf() {   # una copia de agente.conf con cambios, para no tocar el original
    en_servidor sh -c "sed -e '$1' $DIR/agente.conf > $DIR/agente.o2e3.conf && chmod 644 $DIR/agente.o2e3.conf"
}
cp_conf "s/x/x/"

# ===========================================================================
echo
echo "=== A. Token bueno ==="
token_de bueno token | configurar "$CLIENTE"
ENTORNO_MODIFICADO="$(entorno_visible $DIR/entorno)"
LA="$(log_agente_desde)"
arrancar "$DIR/agente.o2e3.conf"
sleep 5; A_INI="$(ahora)"; sleep 45; A_FIN="$(ahora)"; sleep 8
N="$(segundos "$A_INI" "$A_FIN")"
ok $([ "$N" -ge 43 ] && echo 1 || echo 0) "45 s con el token bueno: $N puntos de CPU (uno por segundo)"
ACEPTADOS="$(log_backend "$LB0" | grep -c "cliente='$CLIENTE'.*resultado=aceptado" || true)"
ok $([ "$ACEPTADOS" -ge 8 ] && echo 1 || echo 0) "el backend deja constancia de $ACEPTADOS lotes aceptados"
log_backend "$LB0" | grep "resultado=aceptado" | tail -2 | sed 's/^.*ingesta/    ingesta/'
ERRORES_A="$(log_agente "$LA" | grep -c ' E! ' || true)"
ok $([ "$ERRORES_A" = 0 ] && echo 1 || echo 0) "el agente no registra errores: $ERRORES_A"
detener

# ===========================================================================
echo
echo "=== B. Etiqueta cambiada: token bueno, cliente distinto ==="
token_de bueno token | configurar "ZZTEST-Nombre cambiado"
LA="$(log_agente_desde)"; LB="$(log_backend_desde)"
arrancar "$DIR/agente.o2e3.conf"
B_INI="$(ahora)"; sleep 20; B_FIN="$(ahora)"
detener
N="$(segundos "$B_INI" "$B_FIN")"
N2="$(segundos "$B_INI" "$B_FIN" "ZZTEST-Nombre cambiado")"
ok $([ "$N" = 0 ] && [ "$N2" = 0 ] && echo 1 || echo 0) "no entra nada: $N con el cliente bueno, $N2 con el cambiado"
log_agente "$LA" | grep -m1 "400" | cut -c1-260 | sed 's/^/    agente: /'
ok $(log_backend "$LB" | grep -q "rechazado_400.*ZZTEST-Nombre cambiado" && echo 1 || echo 0) \
   "el backend lo rechaza con el recuento del cliente cambiado"

# ===========================================================================
echo
echo "=== C. Token de otro cliente ==="
token_de otro token | configurar "$CLIENTE"
LA="$(log_agente_desde)"; LB="$(log_backend_desde)"
arrancar "$DIR/agente.o2e3.conf"
C_INI="$(ahora)"; sleep 20; C_FIN="$(ahora)"
detener
N="$(segundos "$C_INI" "$C_FIN")"
ok $([ "$N" = 0 ] && echo 1 || echo 0) "no entra nada: $N puntos"
log_agente "$LA" | grep -m1 "400" | cut -c1-260 | sed 's/^/    agente: /'
ok $(log_backend "$LB" | grep -q "cliente='$(token_de otro cliente)'.*rechazado_400" && echo 1 || echo 0) \
   "el backend lo rechaza a nombre del cliente del token"

# ===========================================================================
echo
echo "=== D. Cuerpo grande: corte de red de $CORTE_S s y lotes sin tope ==="
cp_conf "s/metric_batch_size = 2000/metric_batch_size = 50000/"
en_servidor grep -E "metric_(batch_size|buffer_limit)" $DIR/agente.o2e3.conf | sed 's/^/    /'
token_de bueno token | configurar "$CLIENTE"
LA="$(log_agente_desde)"; LB="$(log_backend_desde)"
arrancar "$DIR/agente.o2e3.conf"
sleep 12
D_INI="$(ahora)"
docker network disconnect "$RED" "$SERVIDOR"
echo "    red cortada a las $D_INI"
sleep "$CORTE_S"
docker network connect "$RED" "$SERVIDOR"
D_FIN="$(ahora)"
echo "    red de vuelta a las $D_FIN; esperando a que el agente vacie lo acumulado..."
sleep 60
N="$(segundos "$D_INI" "$D_FIN")"
ESPERADOS=$(( $(date -d "$D_FIN" +%s) - $(date -d "$D_INI" +%s) ))
echo "    en el backend:"
log_backend "$LB" | sed 's/ motivo=.*//; s/^.*ingesta/      ingesta/' | uniq -c | sed 's/^/  /' | tail -12
echo "    en el agente:"
log_agente "$LA" | grep -E "413|split|too large|Retrying" | cut -c1-200 | head -6 | sed 's/^/      /'
ok $(log_backend "$LB" | grep -q "rechazado_413" && echo 1 || echo 0) "el lote acumulado llega grande y el backend contesta 413"
ok $(log_agente "$LA" | grep -qi "split" && echo 1 || echo 0) "Telegraf dice que parte el lote"
ok $([ "$N" -ge $(( ESPERADOS - 2 )) ] && echo 1 || echo 0) \
   "no se pierde nada: $N de ~$ESPERADOS segundos del corte estan en infra"
echo "    hueco mayor en la ventana del corte: $(hueco_mayor "$D_INI" "$D_FIN") s"
detener

# ===========================================================================
echo
echo "=== E. Ritmo: un relleno con el mismo token satura el cupo ==="
cp_conf "s/x/x/"
token_de bueno token | configurar "$CLIENTE"
LA="$(log_agente_desde)"; LB="$(log_backend_desde)"
arrancar "$DIR/agente.o2e3.conf"
sleep 5
E_INI="$(ahora)"
# El relleno: ~7 escrituras por segundo durante 150 s (420 por minuto con el
# mismo token). Se apaga solo con `timeout` (leccion de O2b). El token va en un
# fichero de cabeceras, no en la linea de ordenes de curl.
token_de bueno token | en_servidor sh -c "
    umask 077; f=\$(mktemp); printf 'Authorization: Token %s\n' \"\$(cat)\" > \$f
    timeout 150 sh -c 'while :; do
        curl -s -o /dev/null -H @'\$f' -X POST \"$URL_INGESTA/api/v2/write?bucket=infra\" \
             --data-binary \"zztest_o2e3_relleno,cliente=ZZTEST-Laboratorio\\\\ O2e,host=zztest-relleno valor=1i\" &
        sleep 0.14
    done' >/dev/null 2>&1 || true
    wait; rm -f \$f"
E_FIN="$(ahora)"
echo "    relleno de $E_INI a $E_FIN; esperando a que el agente se ponga al dia..."
sleep 70
N="$(segundos "$E_INI" "$E_FIN")"
ESPERADOS=$(( $(date -d "$E_FIN" +%s) - $(date -d "$E_INI" +%s) ))
R429="$(log_backend "$LB" | grep -c "rechazado_429" || true)"
A429="$(log_agente "$LA" | grep -c "429" || true)"
echo "    429 en el backend: $R429 · lineas con 429 en el log del agente: $A429"
log_agente "$LA" | grep -m2 "429" | cut -c1-220 | sed 's/^/      /'
ok $([ "$R429" -gt 0 ] && echo 1 || echo 0) "el cupo salta: hay 429"
ok $([ "$A429" -gt 0 ] && echo 1 || echo 0) "y le llegan al agente"
ok $([ "$N" -ge $(( ESPERADOS - 2 )) ] && echo 1 || echo 0) \
   "el agente no pierde nada: $N de ~$ESPERADOS segundos estan en infra"
echo "    hueco mayor en la ventana: $(hueco_mayor "$E_INI" "$E_FIN") s"

# ===========================================================================
echo
echo "=== F. Token revocado (con el agente en marcha) ==="
LA="$(log_agente_desde)"; LB="$(log_backend_desde)"
printf '{"ids": ["%s"]}' "$(token_de bueno id)" | ayudante revocar | sed 's/^/    /'
F_INI="$(ahora)"; sleep 25; F_FIN="$(ahora)"
detener
# Unos segundos de gracia: lo que ya estaba en camino al revocar.
N="$(segundos "$(date -u -d "@$(( $(date -d "$F_INI" +%s) + 6 ))" +%Y-%m-%dT%H:%M:%SZ)" "$F_FIN")"
ok $([ "$N" = 0 ] && echo 1 || echo 0) "tras revocar no entra nada: $N puntos"
log_agente "$LA" | grep -m1 "401" | cut -c1-220 | sed 's/^/    agente: /'
ok $(log_backend "$LB" | grep -q "rechazado_401.*revocado" && echo 1 || echo 0) "el backend dice que esta revocado"

# ===========================================================================
echo
echo "=== 3. El agente vuelve a como estaba ==="
echo "    --- entorno ORIGINAL ---"
entorno_visible $DIR/entorno.o2e3.original | sed 's/^/    /'
echo "    --- entorno MODIFICADO (casos A, D, E y F) ---"
echo "$ENTORNO_MODIFICADO" | sed 's/^/    /'
en_servidor sh -c "cp -p $DIR/entorno.o2e3.original $DIR/entorno && rm -f $DIR/entorno.o2e3.original $DIR/agente.o2e3.conf"
HUELLA_FINAL="$(en_servidor sha256sum $DIR/entorno | cut -c1-64)"
ok $([ "$HUELLA_FINAL" = "$HUELLA_ORIGINAL" ] && echo 1 || echo 0) "el entorno es byte a byte el original (sha256 ${HUELLA_FINAL:0:12})"
ok $(en_servidor stat -c '%U:%G %a' $DIR/entorno | grep -q "root:kinetix_agente 640" && echo 1 || echo 0) \
   "con su dueno y sus permisos: $(en_servidor stat -c '%U:%G %a' $DIR/entorno)"
ok $(en_servidor sh -c "ls $DIR" | tr '\n' ' ' | grep -qx "LEEME.txt agente.conf conf.d entorno " && echo 1 || echo 0) \
   "no queda nada de la prueba en $DIR: $(en_servidor sh -c "ls $DIR" | tr '\n' ' ')"
if [ "$ESTABA_EN_MARCHA" = 1 ]; then arrancar "$DIR/agente.conf"; fi
ok $([ "$(en_servidor pgrep -x telegraf >/dev/null && echo 1 || echo 0)" = "$ESTABA_EN_MARCHA" ] && echo 1 || echo 0) \
   "el agente queda como estaba (en marcha: $ESTABA_EN_MARCHA)"
printf '{"ids": ["%s"]}' "$(token_de otro id)" | ayudante revocar | sed 's/^/    /'

echo
echo "=== 4. Foto de infra DESPUES ==="
for t in cliente host modo; do
    printf "    %-8s " "$t"
    flux "import \"influxdata/influxdb/schema\"
schema.tagValues(bucket: \"infra\", tag: \"$t\", start: -30d)" | cut -d, -f2 | tr -d '\r' | paste -sd' '
done

echo
echo "RESULTADO: $([ "$FALLOS" = 0 ] && echo "TODO BIEN" || echo "$FALLOS FALLOS")"
exit $([ "$FALLOS" = 0 ] && echo 0 || echo 1)
