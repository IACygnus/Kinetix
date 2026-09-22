"""Crea el informe integrado de la validacion y lo exporta en PDF y HTML."""
import json, sys, time
import httpx
API = "http://localhost:8001/api/v1"
E2 = "59e25069-5104-4b23-9b79-d305f5b38abd"      # E2-validacion
BASE2 = "3c0cc246-6705-4fd9-b95b-dc6205e41371"   # E1.3-baseline-2
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
hdr = {"X-CSRF-Token": ck.get("csrf_token", "")}
secciones = [
    {"order": 0, "type": "load_test", "source_id": E2, "source_name": "E2-validacion"},
    {"order": 1, "type": "load_test", "source_id": BASE2, "source_name": "E1.3-baseline-2"},
]
with httpx.Client(cookies=ck, headers=hdr, timeout=1200.0) as cli:
    t0 = time.time()
    r = cli.post(f"{API}/reports/integrated/generate-consolidated",
                 json={"sections": secciones, "name": "E2-validacion + E1.3-baseline-2"})
    print("consolidado:", r.status_code, f"{time.time()-t0:.1f}s")
    if r.status_code != 200:
        print(r.text[:400]); sys.exit(1)
    cons = r.json()["consolidated_analysis"]
    rid = cons["__report_id"]
    tipos = [k for k in cons if not k.startswith("__")]
    print("  informe:", rid, "· grupos:", tipos)
    for k in tipos:
        print(f"  {k}: conclusiones {len(cons[k]['conclusions'])} chars · "
              f"recomendaciones {len(cons[k]['recommendations'])} chars")
    payload = {"sections": secciones, "report_id": rid, "name": "E2-validacion + E1.3-baseline-2"}
    for salida in ("pdf", "html"):
        t0 = time.time()
        rr = cli.post(f"{API}/reports/integrated/export-{salida}", json=payload)
        print(f"export-{salida}: {rr.status_code} {len(rr.content)} bytes {time.time()-t0:.1f}s")
        if rr.status_code != 200:
            print(rr.text[:300]); sys.exit(1)
        open(f"/tmp/integrado_e2.{salida}", "wb").write(rr.content)
    print("REPORT_ID", rid)
