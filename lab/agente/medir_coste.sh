#!/usr/bin/env bash
# ===========================================================================
# ¿Cuanto le cuesta el agente al servidor? (O2b.2)
# ===========================================================================
#
#   bash lab/agente/medir_coste.sh [segundos]
#
# Es la primera pregunta de cualquier cliente, y no se responde con una
# estimacion. Se mide de /proc, que es de donde sale la verdad:
#
#   CPU      utime + stime de /proc/<pid>/stat, por diferencia. No el %CPU de
#            `ps`, que es la media desde que arranco el proceso y no sirve.
#   Memoria  VmRSS de /proc/<pid>/status: lo que ocupa de verdad en la maquina.
#   Red      bytes que salen por la interfaz, con el agente encendido y
#            apagado. La resta es suya.
set -euo pipefail
export MSYS2_ARG_CONV_EXCL='/proc;/usr;/opt;/etc;/var;/run'

SERVIDOR="${KX_SERVIDOR:-lab_servidor}"
SEGUNDOS="${1:-60}"

en_servidor() { MSYS_NO_PATHCONV=1 docker exec "$SERVIDOR" "$@"; }

PID="$(en_servidor pgrep -x telegraf | head -1 | tr -d '\r')"
[ -n "$PID" ] || { echo "el agente no esta corriendo en $SERVIDOR" >&2; exit 1; }

RELOJ="$(en_servidor getconf CLK_TCK | tr -d '\r')"
NUCLEOS="$(en_servidor nproc | tr -d '\r')"

leer() {   # imprime: <ticks_cpu> <rss_kb> <anon_kb> <fichero_kb> <bytes_salida>
    en_servidor sh -c "
        awk '{print \$14 + \$15}' /proc/$PID/stat
        awk '/^VmRSS/   {print \$2}' /proc/$PID/status
        awk '/^RssAnon/ {print \$2}' /proc/$PID/status
        awk '/^RssFile/ {print \$2}' /proc/$PID/status
        awk -F'[: ]+' '/eth/ {s += \$11} END {print s}' /proc/net/dev
    " 2>/dev/null | tr -d '\r' | tr '\n' ' '
}

echo "midiendo $SEGUNDOS s — agente pid $PID, $NUCLEOS nucleos, $RELOJ ticks/s"

read -r T0 R0 A0 F0 B0 <<< "$(leer)"
INICIO="$(date +%s)"
sleep "$SEGUNDOS"
read -r T1 R1 A1 F1 B1 <<< "$(leer)"
FIN="$(date +%s)"

TRANSCURRIDO=$((FIN - INICIO))
# Porcentaje de UN nucleo, que es como lo mira todo el mundo en `top`.
CPU="$(awk -v t0="$T0" -v t1="$T1" -v s="$TRANSCURRIDO" -v hz="$RELOJ" \
       'BEGIN { printf "%.2f", 100.0 * (t1 - t0) / hz / s }')"
CPU_MAQUINA="$(awk -v c="$CPU" -v n="$NUCLEOS" 'BEGIN { printf "%.3f", c / n }')"
megas() { awk -v r="$1" 'BEGIN { printf "%.1f", r / 1024 }'; }
RSS_MB="$(megas "$R1")"
ANON_MB="$(megas "$A1")"
FICH_MB="$(megas "$F1")"
RED="$(awk -v b0="$B0" -v b1="$B1" -v s="$TRANSCURRIDO" \
       'BEGIN { printf "%.2f", (b1 - b0) / s / 1024 }')"

echo
echo "  CPU            $CPU % de un nucleo   ($CPU_MAQUINA % de la maquina entera)"
echo "  Memoria propia $ANON_MB MB   <- la cifra que le quita memoria al servidor"
echo "  Programa       $FICH_MB MB   (paginas del ejecutable, mapeadas de disco;"
echo "                                el nucleo las descarta si hace falta)"
echo "  Total residente $RSS_MB MB"
echo "  Salida de red  $RED kB/s por las interfaces del servidor"
echo
echo "  (la red incluye TODO lo que sale del servidor en esa ventana, no solo"
echo "   el agente: para su cifra limpia, medir con el agente parado y restar)"
