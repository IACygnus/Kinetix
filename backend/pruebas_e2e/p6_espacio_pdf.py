"""Punto 6 del diagnostico 120 — el espacio de las capturas en el PDF del integrado.

    docker exec jmeter_backend python3 /app/pruebas_e2e/p6_espacio_pdf.py <etiqueta> [report_id]

Genera el PDF de un integrado EN PROCESO (`export_integrated_pdf` no hace commit;
la sesion acaba en rollback: no se escribe nada), lo rasteriza y mide, pagina a
pagina, lo que se ve:

  - cuantas CAPTURAS hay (imagenes del PDF cuyo tamano en pixeles coincide con
    el de un adjunto del integrado; las graficas del cuerpo no cuentan),
  - a que tamano se imprime cada una (mm) y a cuantos ppp,
  - hasta donde llega el contenido y cuantos mm quedan en blanco.

Salida: /tmp/p6/<etiqueta>.pdf, /tmp/p6/<etiqueta>_p<N>.png y /tmp/p6/<etiqueta>.json.
Por defecto, el integrado del diagnostico 120: 42505814.
"""
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, "/app")

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from app.db.session import AsyncSessionLocal
from app.db.models.integrated_report import IntegratedReport
from app.db.models.attachment import ExecutionAttachment
from app.api.v1.endpoints.integrated_report import (
    export_integrated_pdf, IntegratedReportRequest, SectionInput)
from sqlalchemy import select

ETIQUETA = sys.argv[1] if len(sys.argv) > 1 else "prueba"
RID = sys.argv[2] if len(sys.argv) > 2 else "42505814-77aa-438f-9ac5-ea111b0e808c"
SALIDA = "/tmp/p6"
PT_MM = 25.4 / 72
ESCALA = 2
MARGEN_INF_MM = 15      # @page del integrado: lo de debajo es el numero de pagina


async def generar():
    async with AsyncSessionLocal() as db:
        rep = await db.get(IntegratedReport, uuid.UUID(RID))
        secs = [SectionInput(order=s["order"], type=s["type"], source_id=s["source_id"],
                             source_name=s["source_name"], seleccion=s.get("seleccion"))
                for s in rep.sections]
        ids = [uuid.UUID(s["source_id"]) for s in rep.sections]
        adjuntos = (await db.execute(select(ExecutionAttachment).where(
            ExecutionAttachment.execution_id.in_(ids)))).scalars().all()
        tamanos = {}
        for a in adjuntos:
            ruta = os.path.join("/app", a.filepath.lstrip("/"))
            if a.file_type and a.file_type.startswith("image/") and os.path.exists(ruta):
                tamanos[Image.open(ruta).size] = a.title or a.filename
        req = IntegratedReportRequest(sections=secs, report_id=RID, name=rep.name)
        r = await export_integrated_pdf(req, db=db, current_user=None)
        await db.rollback()
    return r.body, tamanos


def medir(pdf_path, tamanos):
    doc = pdfium.PdfDocument(pdf_path)
    paginas = []
    for i in range(len(doc)):
        page = doc[i]
        w_pt, h_pt = page.get_size()
        caps = []
        for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
            px = obj.get_px_size()  # pixeles de la imagen incrustada
            if tuple(px) in tamanos:
                l, b, r, t = obj.get_bounds()
                ancho_mm, alto_mm = (r - l) * PT_MM, (t - b) * PT_MM
                caps.append({"titulo": tamanos[tuple(px)][:50], "px": list(px),
                             "mm": [round(ancho_mm, 1), round(alto_mm, 1)],
                             "ppp": round(px[0] / (ancho_mm / 25.4))})
        png = f"{SALIDA}/{ETIQUETA}_p{i + 1}.png"
        img = page.render(scale=ESCALA).to_pil().convert("L")
        img.save(png)
        # Ultima fila con tinta por encima del margen inferior (el pie no cuenta).
        alto_px = img.height
        limite = int(alto_px * (1 - MARGEN_INF_MM / (h_pt * PT_MM)))
        fin = 0
        datos = img.load()
        for y in range(limite - 1, -1, -1):
            if any(datos[x, y] < 235 for x in range(0, img.width, 3)):
                fin = y
                break
        fin_mm = fin / alto_px * h_pt * PT_MM
        util_mm = h_pt * PT_MM - MARGEN_INF_MM
        paginas.append({"pagina": i + 1, "capturas": caps, "contenido_hasta_mm": round(fin_mm, 1),
                        "blanco_mm": round(util_mm - fin_mm, 1)})
    return paginas, round(doc[0].get_size()[0] * PT_MM), round(doc[0].get_size()[1] * PT_MM)


def main():
    os.makedirs(SALIDA, exist_ok=True)
    pdf, tamanos = asyncio.run(generar())
    ruta = f"{SALIDA}/{ETIQUETA}.pdf"
    open(ruta, "wb").write(pdf)
    paginas, w, h = medir(ruta, tamanos)
    con = [p for p in paginas if p["capturas"]]
    n_caps = sum(len(p["capturas"]) for p in con)
    print(f"{ETIQUETA}: {len(pdf):,} bytes, {len(paginas)} paginas de {w}x{h} mm; "
          f"{n_caps} capturas en {len(con)} paginas")
    print(f"{'pag':>3} {'caps':>4} {'hasta':>6} {'blanco':>6}  capturas (ancho x alto mm, ppp)")
    for p in paginas:
        det = "; ".join(f"{c['mm'][0]}x{c['mm'][1]} {c['ppp']}ppp" for c in p["capturas"])
        print(f"{p['pagina']:>3} {len(p['capturas']):>4} {p['contenido_hasta_mm']:>6} {p['blanco_mm']:>6}  {det}")
    if con:
        print(f"capturas por pagina (paginas con capturas): {n_caps / len(con):.2f}; "
              f"blanco medio en esas paginas: {sum(p['blanco_mm'] for p in con) / len(con):.1f} mm")
    json.dump({"etiqueta": ETIQUETA, "bytes": len(pdf), "paginas": paginas},
              open(f"{SALIDA}/{ETIQUETA}.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
