#!/usr/bin/env python3
"""Rasteriza un PDF a PNG, una imagen por pagina (D-D10).

    python pdf_a_png.py <entrada.pdf> <prefijo_salida> [--escala=2] [--paginas=1,2]

Necesita `pypdfium2` (pip install pypdfium2), anotado en LEEME.md.
"""
import sys
import pypdfium2 as pdfium

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = {a.split("=")[0][2:]: a.split("=")[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
doc = pdfium.PdfDocument(args[0])
quiere = ({int(n) for n in opts["paginas"].split(",")} if "paginas" in opts
          else set(range(1, len(doc) + 1)))
for i in range(len(doc)):
    if i + 1 not in quiere:
        continue
    salida = f"{args[1]}_p{i + 1}.png"
    doc[i].render(scale=float(opts.get("escala", 2))).to_pil().save(salida)
    print(f"escrito {salida}")
print(f"paginas totales: {len(doc)}")
