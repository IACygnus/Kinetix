#!/usr/bin/env python3
"""Genera el informe de horas —HTML y PDF— para poder MIRARLO (D-D10).

    python generar.py <prefijo_salida> [--desde=2026-09-01] [--hasta=2026-09-30]

Pide los datos a `/time/informe`, que es una LECTURA: no escribe nada en la base
(regla 25). Con ellos arma el documento llamando al mismo generador que usa el
producto, no a una copia.

Deja tres archivos: `<prefijo>.html`, `<prefijo>.pdf` y `<prefijo>_cifras.json`
—todas las cifras del informe, para comprobar en D1.5 que ninguna cambió—.
"""
import json
import os
import sys

import httpx

sys.path.insert(0, "/app")

API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")


def cifras(d: dict) -> dict:
    """Todo número del informe, en un solo objeto ordenado. Es la huella que
    D1.5 compara antes y después: si cambia una sola, el rediseño tocó
    contenido, y eso es una parada (D-D8)."""
    return {
        "resumen": d["resumen"],
        "capacidad": d["capacidad"],
        "personas": d["personas"],
        "facturacion": d["facturacion"],
        "por_cliente": d["por_cliente"],
        "por_actividad": d["por_actividad"],
        "proyectos": d["proyectos"],
        "mapa": d["mapa"],
        "detalle_total": d["detalle_total"],
        "detalle": d["detalle"],
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=")[0][2:]: a.split("=")[1]
            for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    prefijo = args[0]
    par = {"desde": opts.get("desde", "2026-09-01"),
           "hasta": opts.get("hasta", "2026-09-30")}

    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, timeout=180)
    r = cli.get(f"{API}/time/informe", params=par)
    r.raise_for_status()
    d = r.json()

    from weasyprint import HTML as WeasyHTML

    from app.schemas.time_tracking import InformeDatos
    from app.services.horas.informe import (CLAVES, documento_html,
                                            documento_pdf_html)

    datos = InformeDatos(**d)
    html = documento_html(datos)
    open(f"{prefijo}.html", "w", encoding="utf-8").write(html)
    WeasyHTML(string=documento_pdf_html(
        datos, [c for c in CLAVES if c != "detalle"])).write_pdf(f"{prefijo}.pdf")
    json.dump(cifras(d), open(f"{prefijo}_cifras.json", "w"),
              ensure_ascii=False, indent=1, sort_keys=True, default=str)

    print(f"{prefijo}.html   {len(html):,} bytes")
    print(f"{prefijo}.pdf    {os.path.getsize(f'{prefijo}.pdf'):,} bytes")
    print(f"{prefijo}_cifras.json escrito")


if __name__ == "__main__":
    main()
