"""Genera el PDF real por HTTP y cuenta paginas y bloques."""
import json, os, re, sys, time
import httpx
API = "http://localhost:8001/api/v1"
EID = sys.argv[1] if len(sys.argv) > 1 else "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
t0 = time.time()
with httpx.Client(cookies=ck, timeout=600.0) as cli:
    r = cli.get(f"{API}/executions/{EID}/export/pdf")
print("status", r.status_code, "bytes", len(r.content), f"{time.time()-t0:.1f}s")
if r.status_code != 200:
    print(r.text[:400]); sys.exit(1)
open("/tmp/salida.pdf", "wb").write(r.content)
print("paginas:", len(re.findall(rb"/Type\s*/Page[^s]", r.content)))
