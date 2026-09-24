#!/usr/bin/env bash
# ===========================================================================
#  Las cifras del informe de horas no se mueven solas
# ===========================================================================
#
#   bash scripts/d1_cifras.sh [ref-de-git]
#
# Saca el generador del informe de un commit de referencia, lo mete en el
# contenedor y lanza `pruebas_e2e/diseno/d1_cifras.py`, que genera el informe
# con aquel y con el de ahora —**con los mismos datos**— y compara numero a
# numero.
#
# Corre desde el anfitrion por una razon sola: la referencia se saca de git, y
# el contenedor monta `./backend` en `/app`, no el repositorio. Es la misma
# situacion que las dos suites del laboratorio.
#
#
# LA REFERENCIA, Y POR QUE CAMBIO EN H8.6
# ---------------------------------------
# Nacio en D1.5 apuntando a `f5bf053` —el informe de antes del rediseno— para
# comprobar que el rediseno no movia ningun numero (D-D8). Ese trabajo esta
# hecho. Despues, H8.3b quito a proposito una cifra de la columna de consumo y
# esta prueba lo caza, que es justo para lo que estaba (reporte 111 §4).
#
# En H8.6 la referencia pasa a ser **el informe tal como quedo al cerrar H8**.
# La pregunta ya no es «el rediseno movio algo» sino «se ha movido algo desde
# que H8 cerro». El dia que se regenera no prueba nada —los dos generadores son
# el mismo—; empieza a valer con el primer cambio que venga despues.
#
# Para regenerarla otra vez, mas adelante: cambiar `REFERENCIA` por el commit
# nuevo, y decir en el reporte de esa etapa por que se movio.
set -euo pipefail

# Git Bash en Windows traduce cualquier argumento que empiece por barra a una
# ruta de Windows. Se excluyen solo las rutas de DENTRO del contenedor; apagar
# la traduccion entera rompe el `docker cp`, que si la necesita.
export MSYS2_ARG_CONV_EXCL='/tmp;/app;KX_SESION=;KX_INFORME_ANTES='

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${KX_BACKEND:-jmeter_backend}"

# `v4.2.0` es el cierre de H8. Ver arriba por que es esa y no `f5bf053`.
REFERENCIA="${1:-${KX_INFORME_ANTES_REF:-v4.2.0}}"
GENERADOR="backend/app/services/horas/informe.py"

cd "$RAIZ"
if ! git rev-parse --verify "$REFERENCIA^{commit}" >/dev/null 2>&1; then
    echo "«$REFERENCIA» no es un commit de este repositorio."
    echo "Es la referencia de las cifras del informe; mira la cabecera de este guion."
    exit 1
fi

echo "=== 1. El generador de referencia, de $REFERENCIA ==="
echo "    $(git show "$REFERENCIA:$GENERADOR" | wc -l) lineas"

# Por tuberia y no con `docker cp`: en Git Bash el archivo temporal del
# anfitrion tambien empieza por `/tmp`, igual que el destino de dentro del
# contenedor, y no hay forma de decirle a MSYS2 que traduzca uno y el otro no.
# `docker exec -i` no toca rutas: el archivo entra por la entrada estandar.
docker exec "$BACKEND" mkdir -p /tmp/antes
git show "$REFERENCIA:$GENERADOR" \
    | docker exec -i "$BACKEND" sh -c 'cat > /tmp/antes/informe_antes.py'

echo
echo "=== 2. La comparacion ==="
# Contra el 8001 a proposito: la comparacion necesita **datos de verdad**, y
# solo lee (`GET /time/informe`). El periodo se puede cambiar con KX_DESDE y
# KX_HASTA.
docker exec \
    -e KX_API="${KX_API:-http://localhost:8001/api/v1}" \
    -e KX_SESION="${KX_SESION:-/tmp/e2e_sesion.json}" \
    -e KX_DESDE="${KX_DESDE:-2026-09-01}" \
    -e KX_HASTA="${KX_HASTA:-2026-09-30}" \
    -e KX_INFORME_ANTES=/tmp/antes \
    "$BACKEND" python3 /app/pruebas_e2e/diseno/d1_cifras.py
