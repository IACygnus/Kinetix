#!/bin/sh
# ============================================================================
#  H8.6 — la regresion completa, EN SERIE
# ============================================================================
#
#      docker exec jmeter_backend sh /app/pruebas_e2e/cierre_h8.sh
#
#  Sucede a `cierre_o2d.sh`: las mismas suites mas las de H8 (los estados, las
#  horas extra en el mapa, el borrado del periodo, el importador de proyectos)
#  y las de la CARGA REAL (el borrado de un proyecto y la tabla de sinonimos).
#
#  Las suites se sincronizan del REPOSITORIO antes de correr (regla 36) y todas
#  las de horas van contra `jmeter_analyzer_test` por el 8002 (regla 34, H-D76).
#  La base de Fredy se fotografia antes y despues: si cambia una fila, se dice.
#
#  LAS DOS DEL LABORATORIO NO ESTAN AQUI, Y NO ES UN OLVIDO
#  -------------------------------------------------------
#  `o2a3_config.py` y `o2a3_correlacion.py` necesitan dos cosas que NO se pueden
#  hacer desde dentro de un contenedor: poner la etiqueta de corrida en el
#  recolector (`docker kill -s HUP lab_colector`) y preguntarle a `lab_db` con
#  su propio psql. Se corren desde el anfitrion, y el recorrido entero es:
#
#      bash scripts/lab_prueba_correlacion.sh
#
#  Al terminar, este guion lo recuerda. Antes ninguna de las dos decia por que
#  no arrancaba: soltaban un `KeyError` y un `FileNotFoundError`. Ahora cada una
#  explica que le falta y quien se lo da (H8.6).
#
#  SIN `set -e`, Y A PROPOSITO
#  --------------------------
#  `cierre_o2d.sh` lo llevaba, y con el la pasada **se para en la primera suite
#  que falla**: no llega al resto, no cuenta nada y el «suites: N · con fallo: M»
#  del final no se imprime. Nunca salto porque hasta ahora ninguna fallaba, que
#  es la peor forma de tener un fallo. Un corredor de regresion tiene que correr
#  las veintiocho y decir cuales fallaron; `correr` ya captura el codigo de cada
#  una y las cuenta.

export KX_API=http://localhost:8002/api/v1
export KX_DB=jmeter_analyzer_test
export KX_SESION=/tmp/e2e_sesion_test.json
export KX_API_PUERTO=8002
export KX_PWD=sqa2024
export KX_PWD_ANA=zztest2026
export PGHOST=postgres
export PGPASSWORD=jmeter_secure_2024

# ---------------------------------------------------------------------------
#  LOS SECRETOS DEL LABORATORIO NO SE ESCRIBEN AQUI
# ---------------------------------------------------------------------------
#  `cierre_o2d.sh` llevaba el token de escritura de InfluxDB **en claro dentro
#  del propio guion versionado**. Esto no lo repite: los tres secretos se toman
#  del entorno, y viven en `lab/lab.env`, que no se versiona.
#
#  Las suites que los necesiten y no los tengan se **SALTAN, con su motivo**, en
#  vez de contarse como fallo. Un fallo es el producto roto; que falte una
#  credencial no lo es, y mezclarlos hace que el resumen final no sirva.
#
#  Para correrlas todas, desde el anfitrion:   bash scripts/regresion_h8.sh
#  —lee `lab/lab.env` y las pasa—.
: "${KX_TOKEN_ESCRITURA:=}"
: "${LAB_PG_LECTOR_PASSWORD:=}"
: "${KX_LLAVE_SSH:=}"

huella() {
  psql -U jmeter_user -d jmeter_analyzer_db -t -A -c \
    "select md5(string_agg(x, '|' order by x)) from (
       select id::text||date::text||hours::text||project_id::text from time_entries) t(x);"
  psql -U jmeter_user -d jmeter_analyzer_db -t -A -c \
    "select (select count(*) from time_entries)||' '||(select count(*) from projects)
          ||' '||(select count(*) from activities)||' '||(select count(*) from clients)
          ||' '||(select count(*) from project_activities)
          ||' '||(select count(*) from project_activity_changes);"
}

echo "=== LA BASE DE FREDY, ANTES ==="
ANTES=$(huella); echo "$ANTES"

sh /app/pruebas_e2e/sincronizar.sh

# La sesion se renueva AQUI, no antes: un `--build` deja el contenedor sin ella
# y trece suites fallarian con «sesion caducada», que no es un fallo del
# producto sino andamiaje que no se sostiene solo.
python3 /app/pruebas_e2e/refrescar_sesion.py

TOTAL=0; MAL=0; SALTADAS=0
saltar() {   # saltar <nombre> <que falta>
  echo ""
  echo "########## $1 ##########"
  echo "SALTADA — falta $2 (esta en lab/lab.env; corre scripts/regresion_h8.sh)"
  SALTADAS=$((SALTADAS+1))
}

correr() {   # correr <nombre> <orden...>
  NOMBRE=$1; shift
  echo ""
  echo "########## $NOMBRE ##########"
  "$@" > /tmp/cierre_$NOMBRE.log 2>&1
  CODIGO=$?
  grep -E "PASA |FALLA " /tmp/cierre_$NOMBRE.log | sed 's/|.*//' | sort | uniq -c | tr '\n' ' '
  echo ""
  tail -3 /tmp/cierre_$NOMBRE.log | grep -E "TODO PASA|FALLO|PASAN" || tail -1 /tmp/cierre_$NOMBRE.log
  TOTAL=$((TOTAL+1))
  if [ $CODIGO -ne 0 ]; then MAL=$((MAL+1)); echo ">>> SALIDA $CODIGO"; fi
}

# ---------- H1 a H7: el modulo de horas de siempre ----------
correr h13_actividades_proyectos   sh       /tmp/e2e/h13_backend.sh
correr h15_pantallas               python3  /tmp/e2e/h15_pantallas.py
correr h22_registro                python3  /tmp/e2e/h22_backend.py
correr h2b2_calendario             python3  /tmp/e2e/h2b2_backend.py
correr h2b3_pantalla_registro      python3  /tmp/e2e/h2b3_pantalla.py
correr h32_consulta                python3  /tmp/e2e/h32_consulta.py
correr h52_datos_informe           python3  /tmp/e2e/h52_informe.py
correr h53_h54_documento           python3  /tmp/e2e/h53_h54_documento.py
correr h6_ajustes                  python3  /tmp/e2e/h6_ajustes.py
correr h71_portada                 python3  /tmp/e2e/h71_portada.py
correr h74_pantallas               python3  /tmp/e2e/h7_pantallas_horas.py

# ---------- H8: el estado del proyecto ----------
correr h82_estados                 python3  /tmp/e2e/h82_estados.py
correr h83_pantallas_estado        python3  /tmp/e2e/h83_pantallas.py
correr h84_mapa                    python3  /tmp/e2e/h84_mapa.py
correr h85_borrado                 python3  /tmp/e2e/h85_borrado.py
correr h85_pantalla_borrado        python3  /tmp/e2e/h85_pantalla.py
correr h85b_proyectos              python3  /tmp/e2e/h85b_proyectos.py
correr h85b_pantalla_proyectos     python3  /tmp/e2e/h85b_pantalla.py

# ---------- La CARGA REAL ----------
correr carga_borrado_proyecto      python3  /tmp/e2e/carga_borrado_proyecto.py
correr carga_actividades_nuevas    python3  /tmp/e2e/carga_actividades_nuevas.py

# ---------- Observabilidad y diseno ----------
if [ -n "$KX_TOKEN_ESCRITURA" ]; then
  correr o16_monitoreo             python3  /tmp/e2e/o16_pantalla.py
else
  saltar o16_monitoreo "KX_TOKEN_ESCRITURA"
fi
# La corrida del tablero **se busca**, no se escribe aqui. `cierre_o2d.sh` la
# llevaba fija y dos dias despues ya no tenia datos en los dos cubos: el panel
# salia vacio y la prueba decia «FALLA» con el tablero perfectamente sano.
KX_CORRIDA="$(python3 /tmp/e2e/corrida_para_tablero.py 2>/tmp/corrida_por_que.txt)"
if [ -n "$KX_CORRIDA" ]; then
  export KX_CORRIDA
  echo ""
  echo "corrida del tablero: $KX_CORRIDA"
  correr o2a4_tablero              python3  /tmp/e2e/probar_tablero.py
else
  saltar o2a4_tablero "una corrida con datos en los dos cubos"
  sed 's/^/    /' /tmp/corrida_por_que.txt
fi
if [ -n "$LAB_PG_LECTOR_PASSWORD" ] && [ -n "$KX_LLAVE_SSH" ]; then
  correr o2c1_servidores           python3  /tmp/e2e/o2c1_backend.py
  correr o2c_pantalla              python3  /tmp/e2e/o2c_pantalla.py
else
  saltar o2c1_servidores "LAB_PG_LECTOR_PASSWORD o KX_LLAVE_SSH"
  saltar o2c_pantalla    "LAB_PG_LECTOR_PASSWORD o KX_LLAVE_SSH"
fi
correr o2d2_sesiones               python3  /tmp/e2e/o2d2_sesiones.py
correr o2d3_jmx                    python3  /tmp/e2e/o2d3_jmx.py
correr o2d5_pantalla               python3  /tmp/e2e/o2d5_pantalla.py
correr d1_diseno                   python3  /tmp/e2e/diseno/d1_diseno.py

# `h83b_informe.py` no entra aqui: necesita que su generador de datos corra
# antes y se limpie despues, y sus cinco registros hacen fallar a `h84_mapa`,
# que cae en los mismos dias. Se corre aparte:
#     python3 /tmp/e2e/h83b_datos_informe.py
#     python3 /tmp/e2e/h83b_informe.py
#     python3 /tmp/e2e/h83b_datos_informe.py limpiar

echo ""
echo "=== LA BASE DE FREDY, DESPUES ==="
DESPUES=$(huella); echo "$DESPUES"
echo ""
if [ "$ANTES" = "$DESPUES" ]; then
  echo "SI — la base de Fredy no cambio ni una fila"
else
  echo "ATENCION — la base de Fredy CAMBIO"
fi
echo "suites: $TOTAL · con fallo: $MAL · saltadas: $SALTADAS"
echo ""
echo "Lo que NO corre desde aqui, y hay que lanzar del anfitrion:"
echo "  bash scripts/lab_prueba_correlacion.sh   las dos del laboratorio (O2a.3)"
echo "  bash scripts/d1_cifras.sh                las cifras del informe"
if [ "$SALTADAS" -gt 0 ]; then
  echo ""
  echo "  bash scripts/regresion_h8.sh             esto mismo, con lab/lab.env cargado,"
  echo "                                           para que no se salte ninguna"
fi
