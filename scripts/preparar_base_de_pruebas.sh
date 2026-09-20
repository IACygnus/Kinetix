#!/bin/sh
# ============================================================================
#  ETAPA H7.2 (H-D76) — la base de pruebas, desde cero
#
#  Las suites automáticas dejan de correr contra la base que usa Fredy. Aquí se
#  crea `jmeter_analyzer_test` en el mismo Postgres y se levanta un SEGUNDO
#  backend contra ella, en el puerto 8002. El backend de siempre, el 8001, sigue
#  intacto apuntando a la base de siempre.
#
#  Nace del incidente del 18 de septiembre de 2026: una prueba y el trabajo de
#  Fredy compartían base, y acabé borrando lo suyo. Ver el reporte 92.
#
#  Se ejecuta DENTRO del contenedor:
#      docker exec jmeter_backend sh /app/../scripts/preparar_base_de_pruebas.sh
#  o, como se usa de verdad, copiándolo a /tmp:
#      docker exec jmeter_backend sh /tmp/preparar_base_de_pruebas.sh
#
#  No toca la base de producción. Solo crea, nunca borra nada de la otra.
# ============================================================================
set -e

export PGHOST="${PGHOST:-postgres}"
export PGPASSWORD="${PGPASSWORD:-jmeter_secure_2024}"
USUARIO="${POSTGRES_USER:-jmeter_user}"
BASE_TEST="${KX_DB_TEST:-jmeter_analyzer_test}"
PUERTO="${KX_PUERTO_TEST:-8002}"

echo "=== 1. La base de pruebas ==="
EXISTE=$(psql -U "$USUARIO" -d postgres -t -A \
  -c "select 1 from pg_database where datname='$BASE_TEST';")
if [ "$EXISTE" = "1" ]; then
  echo "    '$BASE_TEST' ya existe · se reutiliza"
else
  psql -U "$USUARIO" -d postgres -c "create database $BASE_TEST;" >/dev/null
  echo "    '$BASE_TEST' creada"
fi

echo "=== 2. El backend de pruebas, en el puerto $PUERTO ==="
if [ -n "$(ps -o pid= -C uvicorn 2>/dev/null)" ] && nc -z localhost "$PUERTO" 2>/dev/null; then
  echo "    ya estaba escuchando · no se toca"
else
  # `create_all` crea las siete tablas de horas y el seed siembra el catálogo,
  # la jornada, los festivos y el usuario admin. No hace falta ningún SQL a mano.
  DATABASE_URL="postgresql://$USUARIO:$PGPASSWORD@$PGHOST:5432/$BASE_TEST" \
  ENVIRONMENT=development \
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$PUERTO" \
        --app-dir /app > /tmp/backend_test.log 2>&1 &
  echo "    arrancando…"
  i=0
  while [ $i -lt 40 ]; do
    if curl -sf "http://localhost:$PUERTO/health" >/dev/null 2>&1; then
      echo "    listo en el puerto $PUERTO"
      break
    fi
    i=$((i + 1))
    sleep 1
  done
fi

echo "=== 3. Comprobación ==="
psql -U "$USUARIO" -d "$BASE_TEST" -t -A -c \
  "select 'tablas de horas: '||count(*) from information_schema.tables
   where table_schema='public'
     and table_name in ('activities','projects','project_activities',
                        'project_activity_changes','time_entries',
                        'work_calendar','holidays');"
psql -U "$USUARIO" -d "$BASE_TEST" -t -A -c \
  "select 'actividades sembradas: '||count(*) from activities;"
psql -U "$USUARIO" -d "$BASE_TEST" -t -A -c \
  "select 'festivos sembrados: '||count(*) from holidays;"

echo
echo "Las suites se apuntan con:"
echo "    KX_API=http://localhost:$PUERTO/api/v1"
echo "    KX_DB=$BASE_TEST"
echo "    KX_SESION=/tmp/e2e_sesion_test.json"

echo
echo "=== 4. El juego de datos de pruebas (regla 29: todo con ZZTEST-) ==="
KX_API="http://localhost:$PUERTO/api/v1" \
KX_SESION=/tmp/e2e_sesion_test.json \
KX_PWD="${ADMIN_DEFAULT_PASSWORD:-sqa2024}" \
python3 /tmp/e2e/refrescar_sesion.py >/dev/null 2>&1 || true

KX_API="http://localhost:$PUERTO/api/v1" python3 - <<'PYEOF'
import json, os
import httpx

API = os.environ["KX_API"]
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion_test.json"))["cookies"]}
cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=60)

# Clientes: las suites piden el primero de la lista, asi que tiene que haber.
existentes = {c["name"] for c in cli.get(f"{API}/clients").json()}
for nombre in ("ZZTEST-Cliente uno", "ZZTEST-Cliente dos"):
    if nombre not in existentes:
        r = cli.post(f"{API}/clients", json={"name": nombre})
        print(f"    cliente '{nombre}': {r.status_code}")

# Una segunda persona: varias suites comprueban "registrar por otro" (H-D13).
usuarios = {u["username"] for u in cli.get(f"{API}/users").json()}
if "zztest_analista" not in usuarios:
    r = cli.post(f"{API}/users", json={
        "username": "zztest_analista", "email": "zztest.analista@sqasa.co",
        "full_name": "ZZTEST Analista de pruebas",
        "password": "zztest2026", "role": "analyst"})
    print(f"    usuario 'zztest_analista': {r.status_code}")

print(f"    clientes: {len(cli.get(f'{API}/clients').json())} · "
      f"usuarios: {len(cli.get(f'{API}/users').json())} · "
      f"actividades: {len(cli.get(f'{API}/time/activities').json())}")
PYEOF
