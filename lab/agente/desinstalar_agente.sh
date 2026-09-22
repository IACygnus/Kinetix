#!/usr/bin/env bash
# ===========================================================================
# DESINSTALADOR DEL AGENTE KINETIX — Linux (O-D20)
# ===========================================================================
#
#   sudo bash desinstalar_agente.sh
#
# Deja el servidor **exactamente como estaba**: ni servicio, ni usuario, ni
# archivos, ni procesos. Y no lo dice: lo comprueba al final, una por una, y
# sale con error si algo sobrevivio.
set -uo pipefail

USUARIO="kinetix_agente"
DIR_PROGRAMA="/opt/kinetix-agente"
DIR_CONFIG="/etc/kinetix-agente"
UNIDAD="/etc/systemd/system/kinetix-agente.service"
HERRAMIENTA="/usr/local/bin/kinetix-agente-corrida"
REGISTRO="/var/log/kinetix-agente.log"
PID="/run/kinetix-agente.pid"

[ "$(id -u)" -eq 0 ] || { echo "hay que ser root" >&2; exit 1; }

echo "== 1. Parar el servicio"
if command -v systemctl >/dev/null 2>&1 && [ -f "$UNIDAD" ]; then
    systemctl stop kinetix-agente 2>/dev/null
    systemctl disable kinetix-agente 2>/dev/null
    echo "   servicio parado y deshabilitado"
fi
if [ -f "$PID" ]; then
    kill "$(cat "$PID")" 2>/dev/null
    sleep 2
    kill -9 "$(cat "$PID")" 2>/dev/null
    rm -f "$PID"
    echo "   proceso suelto terminado"
fi
# Por si quedara alguno huerfano de un arranque anterior.
pkill -f "$DIR_PROGRAMA/bin/telegraf" 2>/dev/null && sleep 2

echo "== 2. Quitar los archivos"
rm -f "$UNIDAD" "$HERRAMIENTA" "$REGISTRO"
rm -rf "$DIR_PROGRAMA" "$DIR_CONFIG"
command -v systemctl >/dev/null 2>&1 && systemctl daemon-reload 2>/dev/null
command -v systemctl >/dev/null 2>&1 && systemctl reset-failed 2>/dev/null
echo "   quitados el programa, la configuracion, la unidad y el registro"

echo "== 3. Quitar el usuario"
if id "$USUARIO" >/dev/null 2>&1; then
    userdel "$USUARIO" 2>/dev/null
    groupdel "$USUARIO" 2>/dev/null
    echo "   usuario $USUARIO eliminado"
else
    echo "   el usuario ya no estaba"
fi

echo
echo "== 4. Comprobacion: ¿queda algo?"
RESTOS=0
comprobar() {  # comprobar <descripcion> <orden que NO debe encontrar nada>
    if eval "$2" >/dev/null 2>&1; then
        echo "FALLA | queda: $1"
        RESTOS=$((RESTOS + 1))
    else
        echo "PASA  | no queda: $1"
    fi
}
comprobar "el usuario"                  "id $USUARIO"
comprobar "el grupo"                    "getent group $USUARIO"
comprobar "el directorio del programa"  "test -e $DIR_PROGRAMA"
comprobar "el directorio de config"     "test -e $DIR_CONFIG"
comprobar "la unidad de systemd"        "test -e $UNIDAD"
comprobar "la herramienta de corrida"   "test -e $HERRAMIENTA"
comprobar "el registro"                 "test -e $REGISTRO"
comprobar "el fichero de pid"           "test -e $PID"
comprobar "algun proceso del agente"    "pgrep -f kinetix-agente"
if command -v systemctl >/dev/null 2>&1; then
    comprobar "el servicio en systemd" \
        "systemctl list-unit-files 2>/dev/null | grep -q kinetix-agente"
fi

echo
if [ "$RESTOS" -gt 0 ]; then
    echo "QUEDAN $RESTOS RESTOS. El servidor NO esta como estaba."
    exit 1
fi
echo "El agente Kinetix se ha ido del todo. El servidor esta como estaba."
