#!/usr/bin/env bash
# O-D14 - poner la etiqueta `corrida` en el recolector, sin reiniciarlo.
#
# La misma cadena que Kinetix le da a JMeter en la etiqueta `application`. Esa
# coincidencia es TODA la correlacion: sin ella, la prueba y el servidor son dos
# graficas que no se pueden cruzar.
#
#   bash scripts/lab_corrida.sh laboratorio-tienda-20260921-1600
#   bash scripts/lab_corrida.sh --limpiar        (vuelve a "sin-corrida")
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FICHERO="$RAIZ/lab/colector/telegraf.d/00-corrida.conf"
CONTENEDOR="${KX_COLECTOR:-lab_colector}"

CORRIDA="${1:-}"
[ "$CORRIDA" = "--limpiar" ] && CORRIDA="sin-corrida"
if [ -z "$CORRIDA" ]; then
    echo "uso: bash scripts/lab_corrida.sh <nombre-de-corrida>" >&2
    exit 2
fi

cat > "$FICHERO" <<CONF
# O-D14 - la corrida que se esta midiendo.
#
# Lo reescribe scripts/lab_corrida.sh y Telegraf lo recarga con una senal HUP.
[global_tags]
  corrida = "$CORRIDA"
CONF

if docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
    docker kill -s HUP "$CONTENEDOR" >/dev/null
    echo "corrida = $CORRIDA  (recargado en $CONTENEDOR, modo sin agente)"
else
    echo "corrida = $CORRIDA  ($CONTENEDOR no esta levantado; se aplicara al arrancar)"
fi

# Y en el agente, si esta instalado (O2b). Es la MISMA cadena en los dos modos:
# si discreparan, en el tablero saldrian como dos pruebas distintas.
SERVIDOR="${KX_SERVIDOR:-lab_servidor}"
if docker ps --format '{{.Names}}' | grep -qx "$SERVIDOR" \
   && MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" test -x /usr/local/bin/kinetix-agente-corrida 2>/dev/null; then
    MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" kinetix-agente-corrida "$CORRIDA" >/dev/null
    echo "corrida = $CORRIDA  (recargado en $SERVIDOR, modo agente)"
fi
