#!/bin/sh
# BLOQUE 5 — las suites del «Analista IA», contra la base de PRUEBAS y el 8002.
#
#   docker exec jmeter_backend sh /app/pruebas_e2e/cierre_b5.sh
#
# El 8002 tiene que correr SIN clave de IA y con --reload (regla 34). La de
# equivalencia de /upload (b5_equivalencia_upload.py) no va aqui: necesita la
# version de antes sacada de git, que el contenedor no ve.
set -u
export PYTHONPATH=/app/pruebas_e2e:/app KX_API=http://localhost:8002/api/v1 KX_DB=jmeter_analyzer_test
export DATABASE_URL=postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_test
D=/app/pruebas_e2e
fallos=0
correr() {
  echo "=== $1"
  shift
  if (cd /app && env GEMINI_API_KEY= OPENAI_API_KEY= "$@") > /tmp/cierre_b5_ultimo.log 2>&1; then
    grep -E "TODO PASA" /tmp/cierre_b5_ultimo.log | tail -1
  else
    fallos=$((fallos + 1))
    grep -E "FALLA|Error|Traceback" /tmp/cierre_b5_ultimo.log | head -20
  fi
}
correr "A sesion y ficha"       python3 $D/b5_a_sesion.py
correr "B adjuntos de errores"  python3 $D/b5_b_adjuntos.py
correr "C prompts"              python3 $D/b5_c_prompts.py
correr "D chat y generar"       python3 $D/b5_d_chat.py
correr "E adjuntos v2 (150)"    python3 $D/b5_e_adjuntos_v2.py
correr "F criterios v2 (150)"   python3 $D/b5_f_criterios_v2.py
correr "G el informe usa los criterios (150)" python3 $D/b5_g_informe_criterios.py
correr "H reparto del esfuerzo (151)" python3 $D/b5_h_reparto.py
correr "I percentiles (151)" python3 $D/b5_i_percentiles.py
echo
[ "$fallos" -eq 0 ] && echo "CIERRE B5: TODO PASA" || echo "CIERRE B5: $fallos suite(s) con fallos"
exit "$fallos"
