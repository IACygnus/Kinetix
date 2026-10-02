#!/bin/sh
# BLOQUE 5, cierre (reporte 149) — la regresion completa del modulo de ANALISIS, en serie.
#
#   git -C <repo> show 2dc56bc:backend/app/api/v1/endpoints/upload.py > backend/pruebas_e2e/_upload_base.py
#   docker exec jmeter_backend sh /app/pruebas_e2e/regresion_analisis.sh
#
# Solo suites que corren contra la base de PRUEBAS y el 8002, o en proceso sin
# IA y sin escribir (reglas 34 y 26: ningun login con contrasena). Las de etapas
# viejas que apuntan a ejecuciones de la base de Fredy (E*, Nova) o que entran
# con KX_PWD no estan aqui: ver el reporte 149 §3.
# El 8002 se reinicia al principio (sin --reload, sin IA), se pasa a --ia-falsa
# solo para la pantalla del Analista IA y se deja como estaba al final.
set -u
D=/app/pruebas_e2e
export PYTHONPATH=/app/pruebas_e2e:/app
PRUEBAS="KX_API=http://localhost:8002/api/v1 KX_API_PUERTO=8002 KX_DB=jmeter_analyzer_test KX_SESION=/tmp/e2e_sesion_test.json"
fallos=0
resumen=""
correr() {
  nombre="$1"; shift
  echo "=== $nombre"
  if (cd /app && env $PRUEBAS GEMINI_API_KEY= OPENAI_API_KEY= "$@") > /tmp/regresion_ultimo.log 2>&1; then
    linea=$(grep -E "TODO PASA|CABLEADO CORRECTO|PASA" /tmp/regresion_ultimo.log | tail -1)
    echo "    ok · $linea"
    resumen="$resumen\nok    $nombre"
  else
    fallos=$((fallos + 1))
    grep -E "FALLA|Error|Traceback" /tmp/regresion_ultimo.log | head -12
    resumen="$resumen\nFALLA $nombre"
  fi
}
sh $D/reiniciar_8002.sh
python3 $D/r1_datos.py > /dev/null
python3 $D/r1_sesion_test.py > /dev/null

# En proceso, sin IA y sin escribir
correr "estructura de los prompts (2.2-2.5)"     python3 $D/estructura_prompts.py
correr "conclusion unica del integrado (3)"       python3 $D/conclusion_unica.py
correr "series y hechos de R2"                    python3 $D/r2_series.py
correr "zona horaria de los informes (146)"       python3 $D/zona_horaria_informes.py
if [ -f $D/_upload_base.py ]; then
  correr "/upload igual que antes del bloque 5"   env DATABASE_URL=postgresql://jmeter_user:jmeter_secure_2024@postgres:5432/jmeter_analyzer_test python3 $D/b5_equivalencia_upload.py
fi
# Contra el 8002 y la base de pruebas
correr "F1 aviso de respaldo (backend)"           python3 $D/f1_respaldo.py
correr "F2 aviso de respaldo (pantallas)"         python3 $D/f2_pantallas.py
correr "vinetas en las exportaciones (2.3)"       python3 $D/vinetas_export.py
correr "pantalla de la conclusion unica (3.5)"    python3 $D/pantalla_conclusion_unica.py
correr "cierre R1 (integrado, C2)"                sh $D/cierre_r1.sh
correr "cierre B5 (Analista IA, backend)"         sh $D/cierre_b5.sh
# La pantalla del Analista IA, con la IA del chat sustituida
sh $D/reiniciar_8002.sh --ia-falsa
correr "pantalla del Analista IA (148)"           python3 $D/b5_pantalla.py
echo "[]" > /tmp/b5_ia_guion.json
sh $D/reiniciar_8002.sh

echo
printf "$resumen\n"
echo
[ "$fallos" -eq 0 ] && echo "REGRESION ANALISIS: TODO PASA" || echo "REGRESION ANALISIS: $fallos suite(s) con fallos"
exit "$fallos"
