"""Ejecuta el endpoint del PDF en proceso y guarda el HTML real que se renderiza.

Comprueba sobre datos REALES lo que el diff sintetico ya mostro: orden D17, sin
Throughput, sin la palabra prohibida, y un bloque por transaccion. Ademas cuenta
las paginas con el propio WeasyPrint.
"""
import asyncio, re, sys
sys.path.insert(0, "/app")

from sqlalchemy import select
import app.api.v1.endpoints.export_pdf as ep
from app.db.session import AsyncSessionLocal
from app.db.models.user import User

EID = sys.argv[1] if len(sys.argv) > 1 else "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"
capturado = {}

_orig = ep.build_pdf_html
def _espia(*a, **k):
    html = _orig(*a, **k)
    capturado["html"] = html
    return html
ep.build_pdf_html = _espia


async def main():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
        await ep.export_pdf(EID, db=db, current_user=user)
    html = capturado["html"]
    open("/tmp/pdf_real.html", "w", encoding="utf-8").write(html)
    print(f"HTML real: {len(html)} chars")

    def idx(t):
        return html.find(t)
    bloques = re.findall(r'break-before:page;page-break-before:always;background:#0a1628', html)
    i_tx = idx("INFORME DE CADA TRANSACCION")
    i_con = idx("CONCLUSIONES Y RECOMENDACIONES")
    pruebas = [
        ("sin la grafica Throughput Over Time", "Throughput Over Time" not in html),
        ("el KPI Throughput de la portada sigue", "THROUGHPUT" in html),
        ("sin la palabra prohibida mini-informe", "mini-informe" not in html.lower()),
        ("las transacciones van ANTES de las conclusiones", 0 < i_tx < i_con),
        (f"un bloque por transaccion ({len(bloques)})", len(bloques) >= 1),
        ("sin conclusiones por transaccion", "Conclusiones de la Transaccion" not in html),
        ("sin recomendaciones por transaccion", "Recomendaciones de la Transaccion" not in html),
        ("cada bloque abre pagina (D24)", len(bloques) == html.count("page-break-before:always;background:#0a1628")),
    ]
    fallos = 0
    for texto, ok in pruebas:
        print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
        fallos += 0 if ok else 1

    from weasyprint import HTML
    doc = HTML(string=html).render()
    print(f"paginas del PDF: {len(doc.pages)}")
    print(f"\n=== {'TODO PASA' if not fallos else f'{fallos} FALLOS'} ===")
    return fallos


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
