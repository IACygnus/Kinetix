"""Genera el informe INTEGRADO real (PDF y HTML) y comprueba la ETAPA 2 en el."""
import json, re, sys, time
import httpx

API = "http://localhost:8001/api/v1"
RID = sys.argv[1] if len(sys.argv) > 1 else "fa724249-aee1-4b08-b1af-a3aaf58a4eca"
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
hdr = {"X-CSRF-Token": ck.get("csrf_token", "")}

fallos = 0
def comprobar(ok, t):
    global fallos
    print(f"{'PASA ' if ok else 'FALLA'} | {t}")
    fallos += 0 if ok else 1

with httpx.Client(cookies=ck, headers=hdr, timeout=900.0) as cli:
    r = cli.get(f"{API}/reports/integrated-reports/{RID}")
    r.raise_for_status()
    rep = r.json()
    secciones = rep.get("sections") or []
    payload = {"sections": secciones, "report_id": RID, "name": rep.get("name") or "Integrado"}
    print(f"informe '{payload['name']}' con {len(secciones)} secciones")

    t0 = time.time()
    rh = cli.post(f"{API}/reports/integrated/export-html", json=payload)
    print("export-html:", rh.status_code, len(rh.content), "bytes", f"{time.time()-t0:.1f}s")
    if rh.status_code != 200:
        print(rh.text[:500]); sys.exit(1)
    h = rh.text
    open("/tmp/integrado.html", "w", encoding="utf-8").write(h)
    i_tx = h.find("INFORME DE CADA TRANSACCION")
    comprobar("Throughput Over Time" not in h, "HTML integrado: sin la grafica Throughput")
    comprobar("mini-informe" not in h.lower(), "HTML integrado: sin la palabra prohibida")
    comprobar("Conclusiones de la Transaccion" not in h, "HTML integrado: sin conclusiones por transaccion")
    comprobar(">Throughput<" in h or "Throughput</div>" in h, "HTML integrado: el KPI Throughput sigue")

    t0 = time.time()
    rp = cli.post(f"{API}/reports/integrated/export-pdf", json=payload)
    print("export-pdf:", rp.status_code, len(rp.content), "bytes", f"{time.time()-t0:.1f}s")
    if rp.status_code != 200:
        print(rp.text[:500]); sys.exit(1)
    open("/tmp/integrado.pdf", "wb").write(rp.content)
    comprobar(rp.content[:4] == b"%PDF", "PDF integrado: el archivo es un PDF valido")
    comprobar(len(rp.content) > 100000, "PDF integrado: tiene contenido")

print(f"\n=== {'TODO PASA' if not fallos else f'{fallos} FALLOS'} ===")
sys.exit(1 if fallos else 0)
