#!/bin/sh
# Reinicia el backend de pruebas (8002) SIN --reload, contra jmeter_analyzer_test
# y sin claves de IA en el entorno. Reporte 138: con --reload y un proceso de
# larga vida, R1.1 se cortaba de forma intermitente al exportar el PDF.
#   docker exec -e GEMINI_API_KEY= -e OPENAI_API_KEY= jmeter_backend sh /app/pruebas_e2e/reiniciar_8002.sh
for p in /proc/[0-9]*; do
  if tr '\0' ' ' < "$p/cmdline" 2>/dev/null | grep -q "uvicorn app.main:app .*--port 8002"; then
    kill "$(basename "$p")" 2>/dev/null
  fi
done
sleep 3
cd /app
DATABASE_URL="postgresql://jmeter_user:${PGPASSWORD:-jmeter_secure_2024}@postgres:5432/jmeter_analyzer_test" \
ENVIRONMENT=development GEMINI_API_KEY= OPENAI_API_KEY= \
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --app-dir /app \
  > /tmp/backend_test_sinreload.log 2>&1 &
i=0
while [ $i -lt 40 ]; do
  curl -sf http://localhost:8002/health >/dev/null 2>&1 && { echo "8002 listo, sin --reload"; exit 0; }
  i=$((i + 1)); sleep 1
done
echo "8002 NO arranco: /tmp/backend_test_sinreload.log"; exit 1
