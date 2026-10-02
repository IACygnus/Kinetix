#!/bin/sh
# Reinicia el backend de pruebas (8002) SIN --reload, contra jmeter_analyzer_test
# y sin claves de IA en el entorno.
#   docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh
#   docker exec jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh --ia-falsa
#
# --timeout-keep-alive 300, como el 8001 (docker-compose.yml). Reporte 143: el
# corte intermitente de R1.1 («Server disconnected» al exportar el PDF) era el
# keep-alive de 5 s que uvicorn trae por defecto. La suite exporta el HTML y el
# PDF por la MISMA conexion; si el servidor la cerraba entre las dos, el PDF se
# perdia sin llegar al log. La hipotesis del 138 (--reload) quedo descartada.
#
# --ia-falsa (bloque 5, pantalla, reporte 148): la misma app con la IA del chat
# del «Analista IA» sustituida por el guion de /tmp/b5_ia_guion.json
# (app_ia_falsa.py). Sin guion se comporta igual que sin IA.
for p in /proc/[0-9]*; do
  if cat "$p/cmdline" 2>/dev/null | tr '\0' ' ' | grep -q "uvicorn .*--port 8002"; then
    kill "$(basename "$p")" 2>/dev/null
  fi
done
sleep 3
MODULO=app.main:app
DIR=/app
if [ "${1:-}" = "--ia-falsa" ]; then MODULO=app_ia_falsa:app; DIR=/app/pruebas_e2e; fi
cd /app
DATABASE_URL="postgresql://jmeter_user:${PGPASSWORD:-jmeter_secure_2024}@postgres:5432/jmeter_analyzer_test" \
ENVIRONMENT=development GEMINI_API_KEY= OPENAI_API_KEY= \
nohup python3 -m uvicorn "$MODULO" --host 0.0.0.0 --port 8002 --app-dir "$DIR" \
  --timeout-keep-alive 300 > /tmp/backend_test_sinreload.log 2>&1 &
i=0
while [ $i -lt 40 ]; do
  curl -sf http://localhost:8002/health >/dev/null 2>&1 && { echo "8002 listo ($MODULO), sin --reload, keep-alive 300"; exit 0; }
  i=$((i + 1)); sleep 1
done
echo "8002 NO arranco: /tmp/backend_test_sinreload.log"; exit 1
