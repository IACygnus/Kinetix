"""ETAPA 7.1 — que muestra hoy el informe integrado (read-only).

    docker exec jmeter_backend python3 /tmp/e2e/diag_integrado_71.py

Compara, sobre los dos integrados reales, lo que sale por CADA canal:
  - el HTML exportado del integrado,
  - el HTML del PDF del integrado,
  - y lo que la pantalla pinta (eso lo mide el script de Playwright aparte).

0 llamadas a la IA: solo se vuelve a exportar lo ya guardado.
"""
import json
import re
import sys

import httpx

API = "http://localhost:8001/api/v1"
INTEGRADOS = sys.argv[1:] or [
    "8713aad1-5de9-4dcb-b294-360ce8ecaee8",     # E3-estilo (una ejecucion con 3 tx)
    "998090d0-9bab-4935-8a2e-ffd7f23000fb",     # E2-validacion + E1.3-baseline-2
]

ck = {c["name"]: c["value"] for c in json.load(open("/tmp/e2e_sesion.json"))["cookies"]}
hdr = {"X-CSRF-Token": ck.get("csrf_token", "")}


def bloques_tx_html(h):
    """Los titulos de bloque por transaccion del HTML (fondo navy, 1.5rem)."""
    return [x.strip() for x in re.findall(r'font-size:1\.5rem;font-weight:700">([^<]+)</div>', h)]


def bloques_tx_pdfhtml(h):
    """Lo mismo en el HTML que se le entrega a WeasyPrint."""
    return [x.strip() for x in re.findall(
        r'page-break-before:always;background:#0a1628[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)', h)]


with httpx.Client(cookies=ck, headers=hdr, timeout=1800.0) as cli:
    for rid in INTEGRADOS:
        r = cli.get(f"{API}/reports/integrated-reports/{rid}")
        r.raise_for_status()
        rep = r.json()
        secciones = rep.get("sections") or []
        print("=" * 78)
        print(f"{rep.get('name')}  ({rid})")
        print("=" * 78)
        for s in secciones:
            ov = s.get("overrides") or {}
            an = list((ov.get("analysis") or {}).keys())
            print(f"  seccion {s.get('order')}: {s.get('type'):12s} {s.get('source_name')}")
            print(f"      overrides.analysis: {an or 'ninguno'}")
            # Las claves de override que existen hoy son columnas de la ejecucion.
            tx_keys = [k for k in an if k.startswith("tx|")]
            print(f"      de ellas, por transaccion: {tx_keys or 'ninguna'}")

        payload = {"sections": secciones, "report_id": rid, "name": rep.get("name") or "Integrado"}

        rh = cli.post(f"{API}/reports/integrated/export-html", json=payload)
        h = rh.text if rh.status_code == 200 else ""
        bh = bloques_tx_html(h)
        print(f"\n  HTML exportado : {rh.status_code}, {len(h):,} chars")
        print(f"      bloques por transaccion: {len(bh)} -> {bh}")

        rp = cli.post(f"{API}/reports/integrated/export-pdf", json=payload)
        print(f"  PDF exportado  : {rp.status_code}, {len(rp.content):,} bytes")

print("\n" + "=" * 78)
print("Nota: lo que pinta la PANTALLA se mide con pantalla_integrado_71.py")
print("=" * 78)
