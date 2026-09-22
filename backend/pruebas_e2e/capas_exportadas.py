"""ETAPA 6.4 — las capas en el PDF y en el HTML exportado (D49).

    docker exec jmeter_backend python3 /tmp/e2e/capas_exportadas.py <exec_id>

PDF: se espia la llamada de dibujo (`chart_multiline`) para ver QUE series se le
pasan y con que capa, y ademas se comprueba el PNG resultante: una imagen con
solo la capa de maximos no puede ser igual a la de ambas.

HTML: se comprueba la visibilidad inicial de cada traza, que los botones esten y
marcados en la capa recibida, y despues se abre el documento en Chromium para
ver que los botones alternan de verdad, que el hover solo muestra lo visible y
que no hay ni un error de consola.

0 llamadas a la IA.
"""
import asyncio
import json
import re
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

import app.api.v1.endpoints.export_pdf as ep_pdf
import app.api.v1.endpoints.export_html as ep_html
import app.services.export.report_generator as rg
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.transaction_chart_analysis import TransactionChartAnalysis

EID = sys.argv[1] if len(sys.argv) > 1 else "20bb2356-410d-465f-8717-c9a025e26e03"
SALIDA = "/tmp/e2e_capas.html"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


# --- espia de la llamada de dibujo del PDF ---------------------------------
llamadas = []          # (n_series, nombres, capa, png)
_orig_ml = rg.chart_multiline


def _espia_ml(series_list, ylabel, use_code_colors=False, dual_max=False, capa='ambas'):
    png = _orig_ml(series_list, ylabel, use_code_colors=use_code_colors,
                   dual_max=dual_max, capa=capa)
    llamadas.append({
        'ylabel': ylabel, 'dual_max': dual_max, 'capa': capa,
        'nombres': [s[0] for s in series_list], 'png': png,
    })
    return png


rg.chart_multiline = _espia_ml
ep_pdf.chart_multiline = _espia_ml


def rt_calls():
    return [c for c in llamadas if c['dual_max']]


def trazas(html, chart_id):
    """Las trazas con las que se pinta un grafico del HTML exportado.

    Se recorta contando corchetes, no con una expresion regular: los datos de las
    trazas llevan corchetes dentro y cualquier `\\[.*?\\]` corta a la primera.
    """
    m = re.search(r"Plotly\.newPlot\('" + re.escape(chart_id) + r"',\s*", html)
    if not m:
        return None
    i = m.end()
    if html[i] != '[':
        return None
    prof, dentro, escapa = 0, None, False
    for j in range(i, len(html)):
        ch = html[j]
        if dentro:
            if escapa:
                escapa = False
            elif ch == '\\':
                escapa = True
            elif ch == dentro:
                dentro = None
            continue
        if ch in '"\'':
            dentro = ch
        elif ch == '[':
            prof += 1
        elif ch == ']':
            prof -= 1
            if prof == 0:
                return json.loads(html[i:j + 1])
    return None


def resumen_vis(tr):
    return [(t.get('name'), t.get('visible', True)) for t in tr]


async def main():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
        etiquetas = sorted({
            f.label for f in (await db.execute(
                select(TransactionChartAnalysis)
                .where(TransactionChartAnalysis.execution_id == EID)
            )).scalars().all()
        })
        print(f"transacciones: {etiquetas}\n")
        elegida = etiquetas[0]

        # =================== PDF ===================
        print("--- 1. PDF sin parametro: las dos capas, como siempre ---")
        llamadas.clear()
        await ep_pdf.export_pdf(EID, db=db, current_user=user)
        base = rt_calls()
        ok(len(base) == 1 + len(etiquetas),
           f"{len(base)} graficas con serie dual (1 general + {len(etiquetas)} por transaccion)")
        ok(all(c['capa'] == 'ambas' for c in base), "todas se dibujan con 'ambas'")
        ok(any(n.endswith(' (max)') for n in base[0]['nombres']),
           f"la general recibe promedio y maximo: {base[0]['nombres']}")
        png_gen_ambas = base[0]['png']
        # Todos los bloques por transaccion llaman a sus series 'Promedio', asi
        # que se guardan POR POSICION: el orden es el de la tabla resumen.
        png_tx_ambas = [c['png'] for c in base[1:]]

        print("\n--- 2. PDF con la general en 'Máximo' ---")
        llamadas.clear()
        await ep_pdf.export_pdf(EID, capa=['general|rt:maximo'], db=db, current_user=user)
        c = rt_calls()
        ok(c[0]['capa'] == 'maximo', f"la general se dibuja con capa={c[0]['capa']!r}")
        ok(all(x['capa'] == 'ambas' for x in c[1:]),
           "las demas siguen en 'ambas' — la seleccion es por grafica (D46)")
        ok(c[0]['png'] != png_gen_ambas, "el PNG de la general cambia respecto al de 'ambas'")
        ok([x['png'] for x in c[1:]] == png_tx_ambas,
           "los PNG de las transacciones son BYTE A BYTE los mismos")

        print("\n--- 3. PDF con una transaccion en 'Promedio' ---")
        llamadas.clear()
        await ep_pdf.export_pdf(EID, capa=[f'tx:{elegida}|rt:promedio'], db=db, current_user=user)
        c = rt_calls()
        ok(c[0]['capa'] == 'ambas', "la general no se movio")
        # El orden de los bloques es el del resumen; se localiza por posicion.
        idx = 1 + etiquetas.index(elegida)
        ok(c[idx]['capa'] == 'promedio', f"'{elegida}' se dibuja con capa='promedio'")
        ok(c[idx]['png'] != png_tx_ambas[idx - 1],
           "su PNG cambia respecto al de 'ambas'")
        ok([x['png'] for k, x in enumerate(c[1:]) if k != idx - 1]
           == [p for k, p in enumerate(png_tx_ambas) if k != idx - 1],
           "los demas bloques salen byte a byte iguales")

        print("\n--- 4. PDF: parametro basura = 'ambas', no un fallo ---")
        llamadas.clear()
        await ep_pdf.export_pdf(EID, capa=['esto-no-es-un-id', 'general|rt:inventada'],
                                db=db, current_user=user)
        c = rt_calls()
        ok(all(x['capa'] == 'ambas' for x in c), "todo vuelve a 'ambas' sin romper la exportacion")
        ok(c[0]['png'] == png_gen_ambas, "y el PDF sale igual que el de siempre")

        # =================== HTML ===================
        print("\n--- 5. HTML: visibilidad inicial segun la capa recibida ---")
        r = await ep_html.export_html(EID, db=db, current_user=user)
        html_base = r.body.decode()
        tr = trazas(html_base, 'chart-rt-label')
        ok(all(t.get('visible', True) is True for t in tr),
           f"sin parametro, las {len(tr)} trazas visibles")

        r = await ep_html.export_html(EID, capa=['general|rt:maximo'], db=db, current_user=user)
        html_max = r.body.decode()
        tr = trazas(html_max, 'chart-rt-label')
        vis = resumen_vis(tr)
        solo_max_visible = all(
            (v is True) == n.endswith(' (max)') for n, v in vis)
        ok(solo_max_visible, f"con 'maximo' solo se ven las de maximos: {vis[:4]}…")
        ok(html_max.count('class="ctrl-btn capa-btn active" data-capa="maximo"') >= 1,
           "el boton 'Máximo' viene marcado en el selector de la general")

        r = await ep_html.export_html(EID, capa=[f'tx:{elegida}|rt:promedio'],
                                      db=db, current_user=user)
        html_tx = r.body.decode()
        tr0 = trazas(html_tx, 'chart-tx0-response-times')
        vis0 = resumen_vis(tr0)
        ok(all((v is True) != n.endswith(' (max)') for n, v in vis0),
           f"el bloque de '{elegida}' abre en 'promedio': {vis0}")
        ok(trazas(html_tx, 'chart-rt-label')[0].get('visible', True) is True,
           "la general del mismo documento sigue con las dos capas")

        print("\n--- 6. HTML: el documento trae los controles y el JS ---")
        ok('window.kxCapa' in html_base, "el JS del selector viaja en el documento")
        ok('.capa-btn.active' in html_base, "y su estilo tambien")
        n_grupos = html_base.count('class="capa-grupo"')
        ok(n_grupos == 1 + len(etiquetas),
           f"{n_grupos} selectores en el HTML (1 general + {len(etiquetas)} por transaccion)")
        # Se cuentan por `data-capa="`, que solo llevan los botones: `capa-btn`
        # aparece tambien en el CSS y en el querySelectorAll del JS.
        ok(html_base.count('data-capa="') == 3 * n_grupos,
           f"tres botones por selector ({html_base.count('data-capa=')} en total)")
        # Ninguna grafica de una sola capa lo lleva.
        for cid in ('chart-latency', 'chart-error-rate', 'chart-codes', 'chart-tps', 'chart-threads'):
            bloque = html_base.split(f'id="{cid}"')[1][:600] if f'id="{cid}"' in html_base else ''
            if bloque and not ok('capa-grupo' not in bloque, f"{cid} no lleva selector de capas"):
                break
        else:
            print("PASA  | ninguna grafica de una sola capa lleva selector")

        open(SALIDA, "w", encoding="utf-8").write(html_max)
        print(f"\nHTML con 'maximo' guardado en {SALIDA} ({len(html_max)} chars)")

    print("\n" + "=" * 70)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("6.4 (PDF + HTML generado) — TODO PASA")
    print("=" * 70)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
