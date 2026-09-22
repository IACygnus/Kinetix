#!/bin/sh
# ============================================================================
#  Deja una copia de trabajo de las suites en /tmp/e2e — ETAPA O2c
# ============================================================================
#
#      docker exec jmeter_backend sh /app/pruebas_e2e/sincronizar.sh
#
#  POR QUE EXISTE
#  --------------
#  El 22 de septiembre de 2026 un `docker compose up -d --build backend` recreo
#  el contenedor y se llevo por delante `/tmp/e2e`, donde vivian las cuarenta y
#  tantas suites acumuladas desde H1. Se recuperaron del respaldo de
#  `C:\proyectos\Kinetix_pruebas\e2e\`, y ahora **la fuente de verdad es el
#  repositorio** (regla 36).
#
#  Las suites se escribieron abriendo y guardando cosas en `/tmp/e2e/...`
#  —informes descargados, libros de Excel que ellas mismas fabrican, capturas—,
#  asi que en vez de editar cincuenta y siete ficheros se deja ahi una copia de
#  trabajo. `/tmp` es borrador: si se pierde, se vuelve a sincronizar y ya.
set -e

ORIGEN="${KX_ORIGEN:-/app/pruebas_e2e}"
DESTINO="${KX_DESTINO:-/tmp/e2e}"

mkdir -p "$DESTINO"
cp -f "$ORIGEN"/*.py "$ORIGEN"/*.sh "$DESTINO"/ 2>/dev/null || true
chmod +x "$DESTINO"/*.sh 2>/dev/null || true

# Los planes de prueba de JMeter van a /tmp a secas: es donde los buscan las
# suites que los usan. `zztest_o14.jmx` era el otro fichero que se perdio con
# el contenedor y no estaba en el respaldo.
cp -f "$ORIGEN"/*.jmx /tmp/ 2>/dev/null || true

echo "sincronizadas $(ls -1 "$DESTINO"/*.py "$DESTINO"/*.sh 2>/dev/null | wc -l) suites en $DESTINO"

# ---------------------------------------------------------------------------
# Los relevos de red, que las suites de navegador dan por sentados
# ---------------------------------------------------------------------------
# El navegador corre DENTRO de este contenedor, donde ni el 5173 ni el 3000 son
# de nadie. Los relevos los traen aqui para que el origen sea `localhost` y el
# CORS pase. Eran procesos de fondo y el `--build` se los llevo: tres suites
# fallaron con ERR_CONNECTION_REFUSED, que parece un fallo de pantalla y no lo
# era. Ahora se levantan con las suites, no antes y aparte.
levantar_rele() {   # levantar_rele <puerto> <script>
    if python3 -c "
import socket,sys
s=socket.socket()
sys.exit(0 if s.connect_ex(('127.0.0.1', $1)) != 0 else 1)
" 2>/dev/null; then
        nohup python3 "$DESTINO/$2" >/dev/null 2>&1 &
        sleep 1
        echo "    rele del $1 levantado"
    else
        echo "    rele del $1 ya estaba"
    fi
}
levantar_rele 5173 rele_5173.py
levantar_rele 3000 rele_3000.py
