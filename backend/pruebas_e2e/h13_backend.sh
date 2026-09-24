#!/bin/sh
# ETAPA H1.3 — el backend de Actividades y Proyectos, por HTTP.
#
#   docker exec -e KX_PWD=... jmeter_backend sh /tmp/e2e/h13_backend.sh
#
# Crea SUS PROPIOS datos de prueba y los borra al final (regla del reporte 38:
# estos endpoints persisten, asi que no se tocan datos de nadie).
# 0 llamadas a la IA.
# H-D76: por defecto, la base de pruebas. El 8001 solo si se pide a mano.
API=${KX_API:-http://localhost:8002/api/v1}
BASE=${KX_DB:-jmeter_analyzer_test}
case "$BASE" in
  *test*) ;;
  *) echo "PARADA: '$BASE' no es una base de pruebas."; exit 1 ;;
esac
export KX_DB="$BASE"
J=/tmp/h13_cookies.txt
FALLOS=0

ok() {   # ok <esperado> <obtenido> <texto>
  if [ "$1" = "$2" ]; then echo "PASA  | $3 ($2)"
  else echo "FALLA | $3 — esperaba $1, obtuvo $2"; FALLOS=$((FALLOS+1)); fi
}

codigo() { echo "$1" | tail -n1; }
cuerpo() { echo "$1" | sed '$d'; }

req() {  # req <metodo> <ruta> [json]
  if [ -n "$3" ]; then
    curl -s -w '\n%{http_code}' -b $J -c $J -X "$1" "$API$2" \
      -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "$3"
  else
    curl -s -w '\n%{http_code}' -b $J -c $J -X "$1" "$API$2" -H "X-CSRF-Token: $CSRF"
  fi
}

echo "=== 0. Sesion ==="
rm -f $J
curl -s -c $J -X POST "$API/auth/login" -d "username=admin&password=$KX_PWD" > /dev/null
CSRF=$(grep csrf_token $J | awk '{print $7}')
R=$(req GET /auth/me); ok 200 "$(codigo "$R")" "login de admin"

echo ""
echo "=== 1. Actividades: las ocho sembradas ==="
# CARGA REAL §3: la siembra pasa de las cinco de H1 a OCHO, y la lista vive en
# `services/horas/sinonimos_actividad.py` (CANONICAS), no aqui: preguntarsela a
# ella es lo que evita que esta prueba y el producto acaben con dos listas.
#
# Se comprueba que **esten las ocho**, no que haya exactamente ocho filas: una
# base de pruebas acumula actividades de pasadas anteriores, y contar filas
# haria fallar a esta suite por algo que no es el seed.
R=$(req GET /time/activities)
ok 200 "$(codigo "$R")" "listar actividades"
FALTAN=$(cuerpo "$R" | python3 -c '
import json, sys
sys.path.insert(0, "/app")
from app.services.horas.sinonimos_actividad import CANONICAS
hay = {a["name"] for a in json.load(sys.stdin) if a["is_active"]}
print(", ".join(sorted(set(CANONICAS) - hay)) or "ninguna")')
ok "ninguna" "$FALTAN" "estan las ocho iniciales, activas — faltan"
cuerpo "$R" | python3 -c 'import json,sys
for a in json.load(sys.stdin): print("    -", a["name"], "· activa" if a["is_active"] else "· inactiva")'

echo ""
echo "=== 2. Crear actividad, y el duplicado normalizado ==="
R=$(req POST /time/activities '{"name":"ZZTEST-Pruebas H1.3"}')
ok 201 "$(codigo "$R")" "crear actividad nueva"
ACT_NUEVA=$(cuerpo "$R" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
R=$(req POST /time/activities '{"name":"  ZZTEST-PRUEBAS H1.3  "}')
ok 409 "$(codigo "$R")" "rechaza el duplicado normalizado (espacios y mayusculas)"
R=$(req POST /time/activities '{"name":"   "}')
ok 400 "$(codigo "$R")" "rechaza el nombre vacio"

echo ""
echo "=== 3. Renombrar y desactivar ==="
R=$(req PUT /time/activities/$ACT_NUEVA '{"name":"ZZTEST-Pruebas H1.3 renombrada"}')
ok 200 "$(codigo "$R")" "renombrar"
R=$(req PUT /time/activities/$ACT_NUEVA '{"is_active":false}')
ok 200 "$(codigo "$R")" "desactivar"
R=$(req PUT /time/activities/$ACT_NUEVA '{"is_active":true}')
ok 200 "$(codigo "$R")" "volver a activar"

echo ""
echo "=== 4. Proyecto: crear con cliente, nombre y actividades ==="
CLI=$(req GET /clients | sed '$d' | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')
ACTS=$(req GET /time/activities | sed '$d' | python3 -c 'import json,sys
a=[x["id"] for x in json.load(sys.stdin)][:2]; print(a[0]+" "+a[1])')
A1=$(echo $ACTS | cut -d" " -f1); A2=$(echo $ACTS | cut -d" " -f2)

R=$(req POST /time/projects "{\"client_id\":\"$CLI\",\"name\":\"ZZTEST-Proyecto H1.3\",\"activities\":[{\"activity_id\":\"$A1\",\"estimated_hours\":40},{\"activity_id\":\"$A2\",\"estimated_hours\":10.5}]}")
ok 201 "$(codigo "$R")" "crear proyecto con dos actividades"
PROY=$(cuerpo "$R" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
cuerpo "$R" | python3 -c 'import json,sys
d=json.load(sys.stdin)
print("    cliente:", d["client_name"], "· estimado total:", d["total_estimated_hours"])
for a in d["activities"]:
    print("    -", a["activity_name"], "est", a["estimated_hours"],
          "consumido", a["consumed_hours"], "restante", a["remaining_hours"])'

echo ""
echo "=== 5. Los errores esperados ==="
R=$(req POST /time/projects "{\"client_id\":\"$CLI\",\"name\":\"  proyecto h1.3 \",\"activities\":[{\"activity_id\":\"$A1\",\"estimated_hours\":5}]}")
ok 409 "$(codigo "$R")" "nombre de proyecto duplicado en el mismo cliente (normalizado)"
R=$(req POST /time/projects "{\"client_id\":\"$CLI\",\"name\":\"Proyecto sin horas\",\"activities\":[{\"activity_id\":\"$A1\",\"estimated_hours\":0}]}")
ok 422 "$(codigo "$R")" "estimacion cero"
R=$(req POST /time/projects "{\"client_id\":\"$CLI\",\"name\":\"Proyecto paso\",\"activities\":[{\"activity_id\":\"$A1\",\"estimated_hours\":0.3}]}")
ok 422 "$(codigo "$R")" "estimacion que no es paso de 0,25"
R=$(req POST /time/projects "{\"client_id\":\"$CLI\",\"name\":\"Proyecto vacio\",\"activities\":[]}")
ok 422 "$(codigo "$R")" "proyecto sin ninguna actividad"
R=$(req DELETE /time/activities/$A1)
ok 409 "$(codigo "$R")" "borrar una actividad que esta en un proyecto"

echo ""
echo "=== 6. Ampliar la estimacion y ver el historial (H-D11) ==="
R=$(req PUT /time/projects/$PROY/actividades "{\"activity_id\":\"$A1\",\"estimated_hours\":60}")
ok 200 "$(codigo "$R")" "ampliar de 40 a 60"
R=$(req GET /time/projects/$PROY/historial)
ok 200 "$(codigo "$R")" "leer el historial"
cuerpo "$R" | python3 -c 'import json,sys
h=json.load(sys.stdin)
print("    filas:", len(h))
for c in h: print("    -", c["change_type"], c["activity_name"],
                  ":", c["previous_hours"], "->", c["new_hours"], "por", c["changed_by_name"])'
N=$(cuerpo "$R" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')
ok 3 "$N" "dos altas y un cambio"

echo ""
echo "=== 7. Quitar una actividad sin horas (H-D12) ==="
R=$(req DELETE /time/projects/$PROY/actividades/$A2)
ok 200 "$(codigo "$R")" "quitar la segunda actividad"
N=$(cuerpo "$R" | python3 -c 'import json,sys; print(json.load(sys.stdin)["activities_count"])')
ok 1 "$N" "queda una actividad"

echo ""
echo "=== 8. Cerrar el proyecto: solo admin (§8) ==="
curl -s -c /tmp/h13_ana.txt -X POST "$API/auth/login" -d "username=${KX_USER_ANA:-zztest_analista}&password=$KX_PWD_ANA" > /dev/null 2>&1
CSRF_ANA=$(grep csrf_token /tmp/h13_ana.txt 2>/dev/null | awk '{print $7}')
if [ -n "$CSRF_ANA" ]; then
  C=$(curl -s -o /dev/null -w '%{http_code}' -b /tmp/h13_ana.txt -X POST \
      "$API/time/projects/$PROY/cerrar" -H "X-CSRF-Token: $CSRF_ANA")
  ok 403 "$C" "un analyst NO puede cerrar"
else
  echo "OMIT  | no se probo el 403 del analyst (sin su clave); el 200 de admin si se prueba"
fi
R=$(req POST /time/projects/$PROY/cerrar)
ok 200 "$(codigo "$R")" "admin cierra el proyecto"
R=$(req PUT /time/projects/$PROY/actividades "{\"activity_id\":\"$A1\",\"estimated_hours\":80}")
ok 409 "$(codigo "$R")" "un proyecto cerrado no admite cambios"
R=$(req POST /time/projects/$PROY/reabrir)
ok 200 "$(codigo "$R")" "admin lo reabre"

echo ""
echo "=== 9. Limpieza ==="
req DELETE /time/projects/$PROY/actividades/$A1 > /dev/null
python3 - "$PROY" "$ACT_NUEVA" <<'PY'
import subprocess, sys, os
sql = f"delete from project_activity_changes where project_id='{sys.argv[1]}'; " \
      f"delete from project_activities where project_id='{sys.argv[1]}'; " \
      f"delete from projects where id='{sys.argv[1]}'; " \
      f"delete from activities where id='{sys.argv[2]}';"
env = {**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"}
subprocess.run(["psql", "-U", "jmeter_user", "-d", os.environ.get("KX_DB", "jmeter_analyzer_test"), "-q", "-c", sql], env=env)
print("    proyecto y actividad de prueba borrados")
PY

echo ""
echo "======================================================================"
if [ $FALLOS -eq 0 ]; then echo "H1.3 — BACKEND DE ACTIVIDADES Y PROYECTOS: TODO PASA"
else echo "$FALLOS FALLO(S)"; fi
echo "======================================================================"
exit $FALLOS
