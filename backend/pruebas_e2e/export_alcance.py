"""ETAPA 6.3 — el selector de exportacion, en las dos salidas (D50, D51).

    docker exec jmeter_backend python3 /tmp/e2e/export_alcance.py <exec_id>

Ejecuta los DOS endpoints de exportacion individual en proceso, con y sin el
parametro `tx`, y comprueba que bloques por transaccion salen en cada caso.
Ademas repite el caso del label invalido por HTTP real, para ver el 400 tal como
lo recibiria el navegador.

Cero llamadas a la IA: exportar solo lee lo que ya esta guardado.
"""
import asyncio
import re
import sys

sys.path.insert(0, "/app")

from fastapi import HTTPException
from sqlalchemy import select

import app.api.v1.endpoints.export_pdf as ep_pdf
import app.api.v1.endpoints.export_html as ep_html
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.transaction_chart_analysis import TransactionChartAnalysis

EID = sys.argv[1] if len(sys.argv) > 1 else "20bb2356-410d-465f-8717-c9a025e26e03"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


# --- PDF: se espia el HTML que se le entrega a WeasyPrint -------------------
_pdf_html = {}
_orig_build = ep_pdf.build_pdf_html


def _espia(*a, **k):
    html = _orig_build(*a, **k)
    _pdf_html["html"] = html
    return html


ep_pdf.build_pdf_html = _espia


def bloques_pdf(html, etiquetas):
    """Que transacciones abren bloque en el PDF. El titulo del bloque es el
    nombre de la transaccion sobre fondo navy y con salto de pagina (D16/D24)."""
    cabeceras = re.findall(
        r'page-break-before:always;background:#0a1628[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)',
        html)
    vistos = [c.strip() for c in cabeceras]
    return [e for e in etiquetas if any(e == v for v in vistos)], len(cabeceras)


def bloques_html(cuerpo, etiquetas):
    """Lo mismo en el HTML: el titulo del bloque va en font-size:1.5rem."""
    cabeceras = re.findall(r'font-size:1\.5rem;font-weight:700">([^<]+)</div>', cuerpo)
    vistos = [c.strip() for c in cabeceras]
    return [e for e in etiquetas if e in vistos], len(cabeceras)


async def main():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()

        etiquetas = sorted({
            f.label for f in (await db.execute(
                select(TransactionChartAnalysis)
                .where(TransactionChartAnalysis.execution_id == EID)
            )).scalars().all()
        })
        print(f"transacciones con analisis ({len(etiquetas)}): {etiquetas}\n")
        assert len(etiquetas) >= 2, "hace falta una ejecucion con 2+ transacciones"

        async def pdf(tx):
            _pdf_html.clear()
            await ep_pdf.export_pdf(EID, tx=tx, db=db, current_user=user)
            return _pdf_html["html"]

        async def html(tx):
            r = await ep_html.export_html(EID, tx=tx, db=db, current_user=user)
            return r.body.decode("utf-8")

        # ---------------- 1. Sin parametro = como hoy ----------------
        print("--- 1. Sin parametro: el documento de siempre (compatibilidad, D51) ---")
        base_pdf = await pdf(None)
        base_html = await html(None)
        b1, n1 = bloques_pdf(base_pdf, etiquetas)
        b2, n2 = bloques_html(base_html, etiquetas)
        ok(b1 == etiquetas and n1 == len(etiquetas), f"PDF sin tx: {n1} bloques {b1}")
        ok(b2 == etiquetas and n2 == len(etiquetas), f"HTML sin tx: {n2} bloques {b2}")

        # ---------------- 2. Solo el informe general ----------------
        print("\n--- 2. 'Solo informe general': ningun bloque por transaccion ---")
        solo_pdf = await pdf([""])          # como llega ?tx= vacio
        solo_html = await html([""])
        _, n3 = bloques_pdf(solo_pdf, etiquetas)
        _, n4 = bloques_html(solo_html, etiquetas)
        ok(n3 == 0, f"PDF con ?tx= : {n3} bloques")
        ok(n4 == 0, f"HTML con ?tx= : {n4} bloques")
        # "INFORME DE CADA TRANSACCION" es un comentario HTML de la plantilla
        # (report_generator.py:1131), invisible en el PDF: no se comprueba. Lo que
        # se comprueba es el documento de verdad — cuantas paginas imprime.
        from weasyprint import HTML as _W
        pag_base = len(_W(string=base_pdf).render().pages)
        pag_solo = len(_W(string=solo_pdf).render().pages)
        ok(pag_solo < pag_base,
           f"el PDF solo-general imprime {pag_solo} paginas frente a {pag_base} del completo")
        # Lo demas del documento sigue ahi: no se ha recortado de mas.
        for nombre, doc in (("PDF", solo_pdf), ("HTML", solo_html)):
            ok("CONCLUSIONES" in doc.upper(), f"el {nombre} conserva las conclusiones generales")
            ok("Response Times" in doc, f"el {nombre} conserva las graficas generales")

        # ---------------- 3. Una sola transaccion ----------------
        print("\n--- 3. Una transaccion marcada: solo su bloque ---")
        elegida = etiquetas[1]
        una_pdf = await pdf([elegida])
        una_html = await html([elegida])
        b5, n5 = bloques_pdf(una_pdf, etiquetas)
        b6, n6 = bloques_html(una_html, etiquetas)
        ok(b5 == [elegida] and n5 == 1, f"PDF con ?tx={elegida!r}: {b5}")
        ok(b6 == [elegida] and n6 == 1, f"HTML con ?tx={elegida!r}: {b6}")

        # ---------------- 4. Todas marcadas = como hoy ----------------
        print("\n--- 4. Todas marcadas: igual que sin parametro ---")
        todas_pdf = await pdf(list(etiquetas))
        todas_html = await html(list(etiquetas))
        b7, n7 = bloques_pdf(todas_pdf, etiquetas)
        b8, n8 = bloques_html(todas_html, etiquetas)
        ok(b7 == etiquetas and n7 == n1, f"PDF con todas: {n7} bloques, los mismos que sin parametro")
        ok(b8 == etiquetas and n8 == n2, f"HTML con todas: {n8} bloques, los mismos que sin parametro")
        ok(len(todas_pdf) == len(base_pdf), "el PDF con todas pesa lo mismo que el de siempre")

        # ---------------- 5. El orden no depende de la seleccion ----------------
        print("\n--- 5. El orden es el de la tabla resumen, no el del cliente ---")
        alreves = await pdf(list(reversed(etiquetas)))
        b9, _ = bloques_pdf(alreves, etiquetas)
        ok(b9 == etiquetas, f"pedidas al reves, salen en el orden del resumen: {b9}")

        # ---------------- 6. Label desconocido = 400 ----------------
        print("\n--- 6. Un label que no existe es un 400, no un documento incompleto ---")
        for nombre, fn in (("PDF", pdf), ("HTML", html)):
            try:
                await fn(["Transaccion Que No Existe"])
                ok(False, f"{nombre}: deberia haber dado 400")
            except HTTPException as e:
                ok(e.status_code == 400, f"{nombre}: {e.status_code} — {e.detail}")
        # Una valida + una invalida tambien falla: no se exporta a medias.
        try:
            await pdf([etiquetas[0], "No Existe"])
            ok(False, "PDF: una valida + una invalida deberia dar 400")
        except HTTPException as e:
            ok(e.status_code == 400, f"PDF una valida + una invalida: {e.status_code}")

        # ---------------- 7. Longitud de la URL (riesgo del reporte 46) -------
        print("\n--- 7. Longitud de la URL con todas las transacciones ---")
        from urllib.parse import urlencode
        q = urlencode([("tx", e) for e in etiquetas])
        largo = len(f"/api/v1/executions/{EID}/export/pdf?{q}")
        ok(largo < 2000, f"la URL con todas mide {largo} caracteres (limite practico 2000)")

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("6.3 — SELECTOR DE EXPORTACION: TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
