"""P6 — el caso de la captura MUY ALTA, con imagenes sinteticas (sin base, sin IA).

    docker exec jmeter_backend python3 /app/pruebas_e2e/p6_captura_alta.py

Pasa por `_build_att_html(for_pdf=True)` tres capturas y comprueba en el PDF:
  - la ancha normal (2,3:1)              -> 259 mm de ancho
  - la del limite (259 x 155 mm)         -> 259 mm de ancho y en UNA hoja con su titulo
  - una vertical (1:1,5, 388 mm de alto a todo el ancho) -> limitada a 155 mm de
    alto, en una sola hoja con su titulo, y AVISADA en el log
"""
import io
import os
import sys
import tempfile
import types

sys.path.insert(0, "/app")

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image, ImageDraw
from weasyprint import HTML

from app.api.v1.endpoints.integrated_report import _build_att_html

PT_MM = 25.4 / 72
casos = {"ancha": (1290, 555), "limite": (1000, 598), "vertical": (800, 1200)}
dir_ = tempfile.mkdtemp(dir="/app/media")   # _build_att_html lee de /app/<filepath>
adjuntos = []
for nombre, (w, h) in casos.items():
    im = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(im).rectangle([2, 2, w - 3, h - 3], outline="black", width=4)
    ruta = os.path.join(dir_, f"{nombre}.png")
    im.save(ruta)
    adjuntos.append(types.SimpleNamespace(
        id=nombre, title=f"ZZTEST captura {nombre}", filename=f"{nombre}.png",
        file_type="image/png", filepath=ruta.replace("/app", "", 1), ai_analysis="Texto de prueba. " * 30))

seccion = types.SimpleNamespace(type="monitoring")
cuerpo = _build_att_html(seccion, adjuntos, "", "Métricas de Monitoreo", for_pdf=True)
pdf = HTML(string=f"<html><head><style>@page {{ size: A4 landscape; margin: 1.5cm; }} body {{ margin: 0; }}</style></head>"
                  f"<body>{cuerpo}</body></html>").write_pdf()
for n in casos:
    os.remove(os.path.join(dir_, f"{n}.png"))
os.rmdir(dir_)

doc = pdfium.PdfDocument(io.BytesIO(pdf))
fallos = 0
vistos = {}
for i in range(len(doc)):
    pag = doc[i]
    texto = pag.get_textpage().get_text_range()
    for obj in pag.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        px = tuple(obj.get_px_size())
        nombre = next(k for k, v in casos.items() if v == px)
        l, b, r, t = obj.get_bounds()
        vistos[nombre] = (i + 1, round((r - l) * PT_MM, 1), round((t - b) * PT_MM, 1),
                          f"ZZTEST captura {nombre}" in texto, round((b * PT_MM), 1))


def ok(c, msg):
    global fallos
    fallos += not c
    print(("PASA  | " if c else "FALLA | ") + msg)


for nombre, (pag, ancho, alto, con_titulo, abajo) in vistos.items():
    print(f"      {nombre}: pagina {pag}, {ancho} x {alto} mm, titulo en la misma hoja: {con_titulo}")
ok(vistos["ancha"][1] == 259.0, "la ancha va a 259 mm")
ok(vistos["limite"][1] == 259.0 and abs(vistos["limite"][2] - 154.9) < 0.5, "la del limite va a 259 x 155 mm")
ok(vistos["limite"][3], "la del limite comparte hoja con su titulo")
ok(vistos["vertical"][2] <= 155.0, f"la vertical se limita a 155 mm de alto ({vistos['vertical'][2]})")
ok(vistos["vertical"][3], "la vertical comparte hoja con su titulo")
ok(all(v[4] >= 15 for v in vistos.values()), "ninguna imagen invade el margen inferior")
print("\nTODO PASA" if not fallos else f"\n{fallos} FALLO(S)")
sys.exit(1 if fallos else 0)
