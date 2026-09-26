#!/bin/sh
# ETAPA R1 — regresion en serie del informe integrado, contra la base de PRUEBAS.
#
#   docker exec jmeter_backend sh /app/pruebas_e2e/cierre_r1.sh
#
# Requisitos (regla 34):
#   - el backend de pruebas en el 8002, SIN clave de IA, para que «Generar informe
#     integrado» no pueda llamar a nadie:
#       docker exec -e GEMINI_API_KEY= -e OPENAI_API_KEY= jmeter_backend \
#            sh /tmp/preparar_base_de_pruebas.sh
#   - Playwright instalado en el contenedor (ver LEEME.md).
# El texto de los PDF se comprueba FUERA del contenedor con r1_pdf_texto.py.
set -u
export PYTHONPATH=/app KX_API=http://localhost:8002/api/v1 KX_API_PUERTO=8002 \
       KX_DB=jmeter_analyzer_test KX_SESION=/tmp/e2e_sesion_test.json
D=/app/pruebas_e2e
fallos=0
correr() {
  echo "=== $1"
  shift
  if "$@" > /tmp/cierre_r1_ultimo.log 2>&1; then
    grep -E "TODO PASA|CABLEADO CORRECTO" /tmp/cierre_r1_ultimo.log | tail -1
  else
    fallos=$((fallos + 1))
    grep -E "FALLA|Error|Traceback" /tmp/cierre_r1_ultimo.log | head -20
  fi
}
python3 $D/r1_datos.py > /dev/null
python3 $D/r1_sesion_test.py > /dev/null
correr "R1.1 guardado"          python3 $D/r1_integrado.py
correr "R1.2 selector"          python3 $D/r1_seleccion.py
correr "R1.3 historial"         python3 $D/r1_historial.py
correr "R1.4 punta a punta"     python3 $D/r1_punta_a_punta.py
correr "C2 integrado"           python3 -c "import sys,threading,time; sys.path.insert(0,'$D'); import r1_integrado as R; threading.Thread(target=R._rele,daemon=True).start(); time.sleep(0.5); import runpy; sys.argv=['c2', R.sql(\"select id from integrated_reports where name='ZZTEST-R1 integrado'\")[0][0].__str__()]; runpy.run_path('$D/cableado_c2_integrado.py', run_name='__main__')"
correr "C2 individual"          python3 -c "import sys,threading,time; sys.path.insert(0,'$D'); import r1_integrado as R; threading.Thread(target=R._rele,daemon=True).start(); time.sleep(0.5); import runpy; sys.argv=['c2', R.sql(\"select id from test_executions where name='ZZTEST-R1 carga'\")[0][0].__str__()]; runpy.run_path('$D/cableado_c2.py', run_name='__main__')"
echo
[ "$fallos" -eq 0 ] && echo "CIERRE R1: TODO PASA" || echo "CIERRE R1: $fallos suite(s) con fallos"
exit "$fallos"
