#!/usr/bin/env python3
"""Rasteriza un HTML a PNG. La verificacion de la Etapa D1 se hace MIRANDO
(D-D10): ningun sub-paso se declara terminado desde el codigo.

    python rasterizar.py <entrada.html> <salida.png> [--ancho 1280] [--alto N]

Sin --alto toma la pagina entera. Con --alto recorta a esa altura (util para
comparar solo la portada contra la captura equivalente de la referencia).
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def rasterizar(entrada: Path, salida: Path, ancho: int = 1280, alto: int | None = None) -> None:
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
        pag = nav.new_page(viewport={"width": ancho, "height": alto or 1400},
                           device_scale_factor=2)
        pag.goto(entrada.resolve().as_uri())
        pag.wait_for_timeout(1200)          # que corran los scripts de graficas
        if alto:
            pag.screenshot(path=str(salida))
        else:
            pag.screenshot(path=str(salida), full_page=True)
        nav.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=")[0][2:]: a.split("=")[1] for a in sys.argv[1:] if "=" in a and a.startswith("--")}
    rasterizar(Path(args[0]), Path(args[1]),
               int(opts.get("ancho", 1280)),
               int(opts["alto"]) if "alto" in opts else None)
    print(f"escrito {args[1]}")
