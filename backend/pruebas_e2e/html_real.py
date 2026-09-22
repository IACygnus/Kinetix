"""Descarga el HTML individual y lo normaliza para poder compararlo."""
import json, os, re, sys, time
import httpx
API = "http://localhost:8001/api/v1"
EID = os.environ.get("KX_EID", "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8")
salida = sys.argv[1]
ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
t0 = time.time()
with httpx.Client(cookies=ck, timeout=600.0) as cli:
    r = cli.get(f"{API}/executions/{EID}/export/html")
print("status", r.status_code, "bytes", len(r.content), f"{time.time()-t0:.1f}s")
s = r.text
# fechas de generacion: cambian entre corridas y no son el objeto de la comparacion
s = re.sub(r"\d{2}/\d{2}/\d{4}[, ]*[\d:]*\s*(a\.?\s?m\.?|p\.?\s?m\.?)?", "FECHA", s)
# los ISO de las series NO se normalizan: son dato, no fecha de generacion
open(salida, "w", encoding="utf-8").write(s)
print(salida, len(s), "chars normalizados")
