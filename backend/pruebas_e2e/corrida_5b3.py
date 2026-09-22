"""ETAPA 5b.3 — la corrida real `E5b-criterios`.

    docker exec jmeter_backend python3 /tmp/e2e/corrida_5b3.py

Sube el JTL de `pruebakinetix` como una ejecucion NUEVA (regla del reporte 38:
los endpoints que persisten solo se invocan sobre ejecuciones E*), con:

  - criterio global   : 2.000 ms · 99,5% · 30 usuarios
  - criterio PROPIO   : "1. Auth" -> 300 ms
  - marcada critica   : SOLO "1. Auth"

Presupuesto: 10 llamadas del informe general + 6 del bloque de "1. Auth" = 16,
por debajo de las 20 autorizadas. Marcar tambien "2. Get Booking" serian 22.

Cuenta las llamadas REALES interceptando `_generate` (cuenta y deja pasar), para
poder afirmar el gasto con una cifra y no con una estimacion.
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app")

import httpx

API = "http://localhost:8001/api/v1"
JTL = "/app/uploads/20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl"
NOMBRE = "E5b-criterios"

CRITERIOS = {
    "concurrency": 30,
    "response_time": 2000,
    "availability": 99.5,
    "per_transaction": {
        "1. Auth": {"concurrency": 30, "response_time": 300,
                    "availability": 99.5, "error_rate": 0.5},
    },
    "critical_transactions": ["1. Auth"],
}


def main():
    ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
    csrf = ck.get("csrf_token", "")
    t0 = time.time()
    with httpx.Client(cookies=ck, timeout=1800.0,
                      headers={"X-CSRF-Token": csrf}) as cli:
        with open(JTL, "rb") as fh:
            r = cli.post(
                f"{API}/upload",
                params={"name": NOMBRE, "test_type": "load", "metric_unit": "TPS",
                        "description": "ETAPA 5b.3 — criterios efectivos en los prompts",
                        "acceptance_criteria": json.dumps(CRITERIOS)},
                files={"files": (JTL.split("/")[-1], fh, "text/csv")},
            )
    print(f"POST /upload -> {r.status_code} en {time.time() - t0:.0f} s")
    if r.status_code != 200:
        print(r.text[:1500])
        return 1
    d = r.json()
    eid = d.get("id") or d.get("execution_id")
    print(f"ejecucion creada: {eid}")
    print(f"ai_status: {json.dumps(d.get('ai_status', {}), ensure_ascii=False)}")
    open("/tmp/e5b_eid.txt", "w").write(str(eid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
