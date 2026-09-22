#!/usr/bin/env bash
# ===========================================================================
# INSTALADOR DEL AGENTE KINETIX — Linux (O-D20)
# ===========================================================================
#
# Instala Telegraf 1.29.5 como el servicio `kinetix-agente`, corriendo con un
# usuario propio SIN privilegios (O-D19).
#
#   sudo bash instalar_agente.sh \
#        --url http://influxdb:8086 --token <token> --org performance \
#        --cubo infra --cliente laboratorio --host lab_servidor
#
#   --paquete /ruta/telegraf-1.29.5_linux_amd64.tar.gz   para un servidor sin
#                                                        salida a internet
#
# Hace falta ser root para INSTALAR un servicio. El agente NO corre como root:
# eso se comprueba al final y se enseña.
#
# Todo lo que toca esta dentro de estas cuatro rutas, y el desinstalador las
# quita enteras:
#     /opt/kinetix-agente          el programa
#     /etc/kinetix-agente          la configuracion y el token
#     /etc/systemd/system/kinetix-agente.service
#     el usuario kinetix_agente
set -euo pipefail

VERSION="1.29.5"
# Suma calculada por nosotros el 2026-09-22 sobre la descarga oficial.
# InfluxData NO publica un fichero de suma al lado del paquete: esto protege
# contra una corrupcion o una sustitucion posterior, **no** contra que la
# descarga de aquel dia ya viniera manipulada. Si su politica exige procedencia
# firmada por el fabricante, díganoslo: Telegraf tiene repositorio APT/YUM
# firmado con GPG y adaptamos el instalador. Esta declarado en el documento de
# permisos y en el reporte de la etapa.
SUMA="c149973d12fe91b188b9395b3bc3de282ec620a645ca4cd8fe81d8185d463db1"
ORIGEN="https://dl.influxdata.com/telegraf/releases/telegraf-${VERSION}_linux_amd64.tar.gz"

USUARIO="kinetix_agente"
DIR_PROGRAMA="/opt/kinetix-agente"
DIR_CONFIG="/etc/kinetix-agente"
UNIDAD="/etc/systemd/system/kinetix-agente.service"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL="" TOKEN="" ORG="" CUBO="" CLIENTE="" NOMBRE_HOST="" PAQUETE="" CORRIDA="sin-corrida"
TOKEN_EN_ARGV=""

while [ $# -gt 0 ]; do
    case "$1" in
        --url)      URL="$2"; shift 2 ;;
        --token)    TOKEN="$2"; TOKEN_EN_ARGV=1; shift 2 ;;
        # Mientras el instalador corre, un `--token` esta en SU linea de
        # ordenes y cualquiera en el servidor lo ve con `ps`. Son segundos,
        # pero si su politica no los admite, el token entra por fichero y no
        # toca la linea de ordenes en ningun momento.
        --token-fichero) TOKEN="$(cat "$2")"; shift 2 ;;
        --org)      ORG="$2"; shift 2 ;;
        --cubo)     CUBO="$2"; shift 2 ;;
        --cliente)  CLIENTE="$2"; shift 2 ;;
        --host)     NOMBRE_HOST="$2"; shift 2 ;;
        --paquete)  PAQUETE="$2"; shift 2 ;;
        --corrida)  CORRIDA="$2"; shift 2 ;;
        *) echo "opcion desconocida: $1" >&2; exit 2 ;;
    esac
done

for obligatorio in URL TOKEN ORG CUBO CLIENTE; do
    [ -n "${!obligatorio}" ] || { echo "falta --${obligatorio,,}" >&2; exit 2; }
done
NOMBRE_HOST="${NOMBRE_HOST:-$(hostname)}"

[ "$(id -u)" -eq 0 ] || { echo "hay que ser root para instalar un servicio" >&2; exit 1; }

echo "== 1. El usuario del agente (O-D19)"
if id "$USUARIO" >/dev/null 2>&1; then
    echo "   ya existe; no se toca"
else
    useradd --system --no-create-home --shell /usr/sbin/nologin "$USUARIO"
    echo "   creado: sin shell, sin contrasena, sin grupos, sin sudo"
fi
# Que quede dicho y comprobado, no supuesto:
GRUPOS="$(id -nG "$USUARIO")"
echo "   grupos: $GRUPOS"
case " $GRUPOS " in
    *" docker "*|*" sudo "*|*" wheel "*|*" adm "*)
        echo "   el usuario pertenece a un grupo privilegiado: me paro" >&2; exit 1 ;;
esac

echo "== 2. El programa (Telegraf $VERSION)"
mkdir -p "$DIR_PROGRAMA/bin"
TEMPORAL="$(mktemp -d)"
trap 'rm -rf "$TEMPORAL"' EXIT

if [ -n "$PAQUETE" ]; then
    echo "   del paquete local: $PAQUETE"
    cp "$PAQUETE" "$TEMPORAL/telegraf.tar.gz"
else
    echo "   descargando de $ORIGEN"
    curl -fsSL -o "$TEMPORAL/telegraf.tar.gz" "$ORIGEN"
fi

OBTENIDA="$(sha256sum "$TEMPORAL/telegraf.tar.gz" | cut -d' ' -f1)"
if [ "$OBTENIDA" != "$SUMA" ]; then
    echo "   la suma NO coincide; no se instala nada" >&2
    echo "   esperada: $SUMA" >&2
    echo "   obtenida: $OBTENIDA" >&2
    exit 1
fi
echo "   suma verificada"

tar -xzf "$TEMPORAL/telegraf.tar.gz" -C "$TEMPORAL"
BINARIO="$(find "$TEMPORAL" -type f -name telegraf -perm -u+x | head -1)"
[ -n "$BINARIO" ] || { echo "   no encuentro el binario dentro del paquete" >&2; exit 1; }
install -m 755 "$BINARIO" "$DIR_PROGRAMA/bin/telegraf"
echo "   instalado: $("$DIR_PROGRAMA/bin/telegraf" --version)"

echo "== 3. La configuracion"
mkdir -p "$DIR_CONFIG/conf.d"
install -m 644 "$AQUI/agente.conf" "$DIR_CONFIG/agente.conf"

cat > "$DIR_CONFIG/conf.d/00-corrida.conf" <<CONF
# La corrida que se esta midiendo. La cambia \`kinetix-agente-corrida\` y el
# agente la recarga con una senal, sin reiniciarse.
[global_tags]
  corrida = "$CORRIDA"
CONF
chmod 644 "$DIR_CONFIG/conf.d/00-corrida.conf"

# El secreto, aparte y con permisos de secreto.
cat > "$DIR_CONFIG/entorno" <<ENV
KX_HOST=$NOMBRE_HOST
KX_CLIENTE=$CLIENTE
KX_INFLUX_URL=$URL
KX_INFLUX_ORG=$ORG
KX_INFLUX_BUCKET=$CUBO
KX_INFLUX_TOKEN=$TOKEN
ENV
chown root:"$USUARIO" "$DIR_CONFIG/entorno"
chmod 640 "$DIR_CONFIG/entorno"
echo "   el token queda en $DIR_CONFIG/entorno, modo 640, solo root y $USUARIO"

cat > "$DIR_CONFIG/LEEME.txt" <<LEEME
Agente Kinetix (Telegraf $VERSION) — instalado el $(date '+%Y-%m-%d %H:%M').

Mide el rendimiento de ESTE servidor y lo envia a la plataforma de pruebas de
SQA. No lee sus datos, no lee sus registros y no escribe nada en el servidor.

  ver estado     systemctl status kinetix-agente
  parar          systemctl stop kinetix-agente
  quitar         bash desinstalar_agente.sh

Que se envia exactamente: docs/observabilidad/requisitos-con-agente.md
LEEME

# La herramienta para cambiar la corrida sin reiniciar.
cat > /usr/local/bin/kinetix-agente-corrida <<'HERRAMIENTA'
#!/bin/sh
# Cambia la etiqueta `corrida` del agente y le manda una senal para recargar.
[ -n "$1" ] || { echo "uso: kinetix-agente-corrida <nombre-de-corrida>" >&2; exit 2; }
cat > /etc/kinetix-agente/conf.d/00-corrida.conf <<CONF
[global_tags]
  corrida = "$1"
CONF
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet kinetix-agente; then
    systemctl reload kinetix-agente
elif [ -f /run/kinetix-agente.pid ]; then
    kill -HUP "$(cat /run/kinetix-agente.pid)"
fi
echo "corrida = $1"
HERRAMIENTA
chmod 755 /usr/local/bin/kinetix-agente-corrida

echo "== 4. El servicio"
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    install -m 644 "$AQUI/kinetix-agente.service" "$UNIDAD"
    systemctl daemon-reload
    systemctl enable --now kinetix-agente >/dev/null 2>&1
    sleep 2
    if systemctl is-active --quiet kinetix-agente; then
        echo "   servicio de systemd activo y habilitado para el arranque"
    else
        echo "   el servicio NO arranco:" >&2
        systemctl status kinetix-agente --no-pager -l 2>&1 | tail -20 >&2
        exit 1
    fi
else
    # El servidor no tiene systemd —en el laboratorio de Kinetix, porque es un
    # contenedor—. La unidad se deja escrita igualmente, para que el servidor
    # quede preparado, y el agente se arranca a mano.
    install -m 644 "$AQUI/kinetix-agente.service" "$UNIDAD" 2>/dev/null || true
    echo "   AVISO: este servidor no tiene systemd."
    echo "   La unidad queda escrita en $UNIDAD pero NO se registra como servicio."
    echo "   El agente se arranca en segundo plano, como usuario $USUARIO."

    # El token NO viaja en la linea de ordenes: cualquiera en el servidor la ve
    # con `ps`. Lo lee el propio proceso del fichero de entorno, que es suyo y
    # de nadie mas. (Con systemd esto lo resuelve `EnvironmentFile`; aqui hay
    # que hacerlo a mano, y es justo la fuga contra la que avisa el documento
    # de permisos cuando dice que de `ps` leemos `comm` y no `args`.)
    # En una sola linea: `sh -c` trata cada salto como una orden nueva, y
    # partido asi el agente arrancaba sin ver su propia configuracion.
    ARRANQUE="set -a; . $DIR_CONFIG/entorno; set +a; exec $DIR_PROGRAMA/bin/telegraf --config $DIR_CONFIG/agente.conf --config-directory $DIR_CONFIG/conf.d"

    # `setpriv` reemplaza el proceso en vez de crear un hijo: asi el pid que
    # guardamos es el del agente de verdad, no el de un envoltorio.
    if command -v setpriv >/dev/null 2>&1; then
        setpriv --reuid="$USUARIO" --regid="$USUARIO" --init-groups \
            -- /bin/sh -c "$ARRANQUE" >> /var/log/kinetix-agente.log 2>&1 &
    else
        runuser -u "$USUARIO" -- /bin/sh -c "$ARRANQUE" \
            >> /var/log/kinetix-agente.log 2>&1 &
    fi
    echo $! > /run/kinetix-agente.pid
    sleep 3
    if kill -0 "$(cat /run/kinetix-agente.pid)" 2>/dev/null; then
        echo "   arrancado, pid $(cat /run/kinetix-agente.pid)"
    else
        echo "   el agente NO arranco:" >&2
        tail -20 /var/log/kinetix-agente.log >&2
        exit 1
    fi
fi

echo "== 5. Comprobaciones finales"

# `pgrep -x telegraf` mira el NOMBRE del ejecutable, no la linea de ordenes: si
# se mira la linea, un envoltorio que lleve la ruta dentro se cuela y parece que
# el agente corre como root cuando no es verdad.
PROCESO="$(pgrep -x telegraf | head -1)"
[ -n "$PROCESO" ] || { echo "   no encuentro el proceso del agente" >&2; exit 1; }
DUENO="$(ps -o user= -p "$PROCESO" | tr -d ' ')"
echo "   el agente corre como: $DUENO  (pid $PROCESO)"
if [ "$DUENO" = "root" ]; then
    echo "   corre como root: eso no es lo acordado (O-D19)" >&2
    exit 1
fi

# Y el token no puede quedar a la vista de cualquiera que escriba `ps`. Se
# excluye el propio instalador y sus hijos: si se invoco con `--token`, ese
# token esta en SU linea de ordenes mientras dura, y eso se resuelve con
# `--token-fichero`, no callando la comprobacion.
# La foto de `ps` se toma ANTES de buscar en ella: si se encadena
# `ps | grep <token>`, el propio grep lleva el token en su linea de ordenes y
# se encuentra a si mismo.
FOTO="$(ps -eo pid=,ppid=,args=)"
CULPABLES="$(printf '%s\n' "$FOTO" | grep -F "$TOKEN" \
    | awk -v yo="$$" -v padre="$PPID" '$1 != yo && $2 != yo && $1 != padre' || true)"
if [ -n "$CULPABLES" ]; then
    echo "   EL TOKEN ESTA EN LA LINEA DE ORDENES DE:" >&2
    echo "$CULPABLES" | cut -c1-140 >&2
    exit 1
fi
echo "   el token no queda en la linea de ordenes de ningun proceso"
if [ -n "${TOKEN_EN_ARGV:-}" ]; then
    echo "   (aviso: se paso con --token, asi que estuvo visible mientras duro"
    echo "    la instalacion. Use --token-fichero si eso no es admisible.)"
fi

echo
echo "Agente Kinetix instalado."
echo "  host     $NOMBRE_HOST"
echo "  cliente  $CLIENTE"
echo "  corrida  $CORRIDA   (se cambia con: kinetix-agente-corrida <nombre>)"
echo "  destino  $URL  cubo $CUBO"
