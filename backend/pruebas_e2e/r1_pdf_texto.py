"""ETAPA R1 — ¿lleva el PDF exportado lo que debe? Se corre FUERA del contenedor.

Dos usos:

    # R1.1: las marcas de edicion (lista de marcas)
    python r1_pdf_texto.py r1_integrado.pdf r1_marcas.json

    # R1.2: la seleccion ({"presentes": [...], "ausentes": [...]})
    python r1_pdf_texto.py r1_seleccion.pdf r1_seleccion_esperado.json

Los archivos salen de /tmp del contenedor con `docker cp`. Necesita PyMuPDF
(`pip install pymupdf`), que NO esta en la imagen del backend: por eso las suites
dejan el PDF en /tmp y la lectura de su texto va aparte. Cuenta lo que se ve en el
documento, no el HTML que se le paso a WeasyPrint.

Un texto puede partirse en dos lineas (en un guion, o entre palabras); se unen
esos cortes antes de buscar.
"""
import json
import re
import sys

import pymupdf

pdf, esperado = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
texto = " ".join(p.get_text() for p in pymupdf.open(pdf))
texto = re.sub(r"-\s*\n\s*", "-", texto)
texto = re.sub(r"\s+", " ", texto)

if isinstance(esperado, list):   # R1.1
    presentes = [f"{m}-{parte}" for m in esperado
                 for parte in (["gen"] if ("IND" in m or "FALLO" in m) else ["gen", "tx", "img"])]
    ausentes = []
else:                            # R1.2
    presentes, ausentes = esperado.get("presentes", []), esperado.get("ausentes", [])

fallos = 0
for t in presentes:
    ok = t in texto
    fallos += not ok
    print(f"{'PASA ' if ok else 'FALLA'} | el PDF lleva «{t}»")
for t in ausentes:
    ok = t not in texto
    fallos += not ok
    print(f"{'PASA ' if ok else 'FALLA'} | el PDF NO lleva «{t}»")
print("\nTODO PASA" if not fallos else f"\n{fallos} FALLO(S)")
sys.exit(1 if fallos else 0)
