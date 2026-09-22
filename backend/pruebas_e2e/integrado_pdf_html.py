"""Ejecuta el export del PDF integrado en proceso y espia el HTML que se renderiza.

Uso:
    python3 /tmp/e2e/integrado_pdf_html.py                 # informe real guardado
    python3 /tmp/e2e/integrado_pdf_html.py <execution_id>  # una seccion con esa ejecucion

La segunda forma existe porque los informes integrados guardados pueden no tener
ninguna ejecucion CON informe por transaccion, y entonces no probarian lo que
hay que probar: que los bloques por transaccion sobreviven al recorte de las
conclusiones individuales (regla 18, orden de los dos _strip).
"""
import asyncio
import re
import sys

sys.path.insert(0, "/app")
from sqlalchemy import select                                   # noqa: E402
import weasyprint                                               # noqa: E402
import app.api.v1.endpoints.integrated_report as ir             # noqa: E402
from app.db.models.integrated_report import IntegratedReport    # noqa: E402
from app.db.models.user import User                             # noqa: E402
from app.db.session import AsyncSessionLocal                    # noqa: E402

ARG = sys.argv[1] if len(sys.argv) > 1 else None
RID_POR_DEFECTO = "fa724249-aee1-4b08-b1af-a3aaf58a4eca"

cap = {}
_orig = weasyprint.HTML


class _Espia(_orig):
    def __init__(self, *a, **k):
        if "string" in k:
            cap["html"] = k["string"]
        super().__init__(*a, **k)


weasyprint.HTML = _Espia


async def main():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
        if ARG:
            secciones = [ir.SectionInput(order=0, type="load_test", source_id=ARG,
                                         source_name="prueba")]
            req = ir.IntegratedReportRequest(sections=secciones, name="Integrado de prueba")
            print(f"seccion unica con la ejecucion {ARG}")
        else:
            fila = (await db.execute(select(IntegratedReport)
                                     .where(IntegratedReport.id == RID_POR_DEFECTO))).scalars().first()
            secciones = [ir.SectionInput(order=s["order"], type=s["type"],
                                         source_id=s["source_id"],
                                         source_name=s.get("source_name") or "")
                         for s in (fila.sections or [])]
            req = ir.IntegratedReportRequest(sections=secciones, report_id=RID_POR_DEFECTO,
                                             name=fila.name)
            print(f"informe guardado '{fila.name}' con {len(secciones)} secciones")
        await ir.export_integrated_pdf(req, db=db, current_user=user)

    h = cap["html"]
    open("/tmp/integrado_pdf.html", "w", encoding="utf-8").write(h)
    print(f"HTML del PDF integrado: {len(h)} chars")
    bloques = len(re.findall(r"break-before:page;page-break-before:always;background:#0a1628", h))
    consolidadas = h.count('class="conclusions-block"')
    # Que se puede exigir depende de la entrada:
    #  - con una ejecucion CON informe por transaccion, tiene que haber bloques;
    #  - con el informe guardado, tiene que haber UN bloque de conclusiones, el
    #    consolidado (las individuales se recortan). La peticion ad-hoc no trae
    #    consolidado, asi que ahi lo correcto es que no haya ninguno.
    pruebas = [
        (f"los bloques por transaccion sobreviven al recorte ({bloques})",
         bloques >= 1 if ARG else True),
        (f"conclusiones individuales recortadas, queda solo el consolidado ({consolidadas})",
         consolidadas == (0 if ARG else 1)),
        ("sin la grafica Throughput", "Throughput Over Time" not in h),
        ("sin la palabra prohibida", "mini-informe" not in h.lower()),
        ("sin conclusiones por transaccion", "Conclusiones de la Transaccion" not in h),
    ]
    fallos = 0
    for t, ok in pruebas:
        print(f"{'PASA ' if ok else 'FALLA'} | {t}")
        fallos += 0 if ok else 1
    print(f"\n=== {'TODO PASA' if not fallos else f'{fallos} FALLOS'} ===")
    return fallos


sys.exit(1 if asyncio.run(main()) else 0)
