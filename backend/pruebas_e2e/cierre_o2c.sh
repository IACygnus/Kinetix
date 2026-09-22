#!/bin/sh
# O2c — la regresion completa, EN SERIE (regla 34).
# Las suites se sincronizan del REPOSITORIO antes de correr (regla 36).
# Todas las suites de horas corren contra jmeter_analyzer_test (H-D76).
export KX_API=http://localhost:8002/api/v1
export KX_DB=jmeter_analyzer_test
export KX_SESION=/tmp/e2e_sesion_test.json
export KX_API_PUERTO=8002
export KX_PWD=sqa2024
export KX_PWD_ANA=zztest2026
export KX_TOKEN_ESCRITURA="qYZd1tnpiAguyaDO1wLUDQvpo6kKY0l6a4axiHiR6lusa6p1nX01sNAz3YaGzHAkGnWABsJvenY61uLm0dHkiA=="
export KX_CORRIDA=zztest-o2c-20260922-173115
export PGHOST=postgres
export PGPASSWORD=jmeter_secure_2024

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

# La sesion se renueva AQUI. El `--build` del 22 de septiembre dejo el
# contenedor sin ella y trece suites fallaron con «sesion caducada»: eso no es
# un fallo del producto, es andamiaje que no se sostenia solo.
python3 /app/pruebas_e2e/refrescar_sesion.py

TOTAL=0; MAL=0
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
correr o16_monitoreo               python3  /tmp/e2e/o16_pantalla.py
correr o2a4_tablero                python3  /tmp/e2e/probar_tablero.py
correr o2c1_servidores             python3  /tmp/e2e/o2c1_backend.py
correr o2c_pantalla                python3  /tmp/e2e/o2c_pantalla.py

echo ""
echo "=== LA BASE DE FREDY, DESPUES ==="
DESPUES=$(huella); echo "$DESPUES"
echo ""
if [ "$ANTES" = "$DESPUES" ]; then
  echo "SI — la base de Fredy no cambio ni una fila"
else
  echo "ATENCION — la base de Fredy CAMBIO"
fi
echo "suites: $TOTAL · con fallo: $MAL"
