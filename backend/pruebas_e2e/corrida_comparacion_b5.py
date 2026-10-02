"""BLOQUE 5, cierre — «prueba 6» generada tres veces con IA REAL, sin escribir (reporte 149).

    docker exec jmeter_backend python3 /app/pruebas_e2e/corrida_comparacion_b5.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/corrida_comparacion_b5.py --solo-html
    docker cp jmeter_backend:/tmp/b5_comparacion/. C:\\proyectos\\Kinetix_pruebas\\r2\\

  (a) como hoy: los criterios que guardó Nuevo Reporte para «prueba 6» (b81d713b)
  (b) Analista IA: criterios y relato (los de la conversación real del 147)
  (c) Analista IA: lo mismo y un archivo de errores SINTÉTICO (XML de JMeter con
      datos, fabricado a partir de los fallos del JTL, con secretos falsos que
      tienen que salir tapados)

Cada variante: el informe general (`run_ai_and_verdict`, 10 llamadas) y el de
cada transacción con informe propio (6 llamadas cada una), con el código de
siempre. Mismo arnés que `corrida_r2.py`: conexión de SOLO LECTURA, rollback,
`_upsert` sustituido por un colector, tokens por intento desde la telemetría.
Nada se guarda en ninguna base. Salida: /tmp/b5_comparacion/.
"""
import asyncio
import copy
import html
import inspect
import json
import os
import re
import sys
import time
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, "/app")
from sqlalchemy import select   # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine   # noqa: E402

from app.core.config import settings   # noqa: E402
from app.db.models.test import TestExecution   # noqa: E402
from app.services.ai import gemini as G   # noqa: E402
from app.services.ai import transaction_report as TR   # noqa: E402
from app.services.ai.analysis_pipeline import run_ai_and_verdict   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.services.ai.estilo import detectar_estilo   # noqa: E402
from app.services.ai.resumen_serie import _ok   # noqa: E402
from app.services.jtl.transaction_series import build_transaction_series   # noqa: E402
from app.api.v1.endpoints.upload import METRIC_KEYS, _parse_execution_df   # noqa: E402
from app.services.analista import errores as ER, ficha as FI, prompt as PA   # noqa: E402

EJECUCION = "b81d713b-af2f-445c-ab87-663149f644b4"   # «prueba 6», carga
SALIDA = "/tmp/b5_comparacion"
SECRETOS = ["ZZsecretoBearer8812", "ZZclave-Pr6!", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwcnVlYmE2In0.ZmFsc29fZmlybWE"]

CRITERIOS = [
    {"texto": "el 90 % de las peticiones responda en menos de 1 segundo", "tipo": "tiempo_respuesta",
     "metrica": "p90", "operador": "<", "valor": 1, "unidad": "s"},
    {"texto": "una disponibilidad del 99 %", "tipo": "disponibilidad_o_error", "metrica": "disponibilidad",
     "operador": ">=", "valor": 99, "unidad": "%"},
    {"texto": "ninguna transacción debería pasar del 5 % de errores", "tipo": "disponibilidad_o_error",
     "metrica": "tasa_error", "operador": "<=", "valor": 5, "unidad": "%", "cada_transaccion": True},
]
RELATO = [
    "Era una ronda corta de 5 minutos con 5 usuarios, usada solo para validar el script antes de la prueba larga.",
    "Desarrollo confirmó que los errores de Put_Update_Booking y Delete_Booking_Id se deben a un fallo de "
    "autenticación del servicio de reservas: esas peticiones no envían el token, y ya lo están corrigiendo.",
]

_motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                             connect_args={"server_settings": {"default_transaction_read_only": "on"}})
Lectura = async_sessionmaker(_motor, class_=AsyncSession, expire_on_commit=False, autoflush=False)

V = {}            # variante en curso -> sus llamadas, tokens, textos
ACTUAL = {"v": None, "label": None}
_gen = G.GeminiAnalyzer._generate
if os.environ.get("B5_SECO"):   # en seco: el recorrido entero sin llamar a la IA
    _gen = lambda self, prompt, section_name="unknown", *a, **kw: f"[seco] {section_name}"   # noqa: E731
_tel = G._emit_ai_telemetry
_firma = inspect.signature(_tel)


def _telemetria(*a, **kw):
    try:
        arg = _firma.bind(*a, **kw).arguments
        u = getattr(arg.get("response"), "usage", None)
        ptd = getattr(u, "prompt_tokens_details", None)
        ctd = getattr(u, "completion_tokens_details", None)
        V[ACTUAL["v"]]["tokens"].append({
            "outcome": arg.get("outcome"), "prompt": getattr(u, "prompt_tokens", None) or 0,
            "cached": getattr(ptd, "cached_tokens", None) or 0, "completion": getattr(u, "completion_tokens", None) or 0,
            "reasoning": getattr(ctd, "reasoning_tokens", None) or 0})
    except Exception:
        pass
    return _tel(*a, **kw)


def _contado(self, prompt, section_name="unknown", *a, **kw):
    t0 = time.time()
    texto = _gen(self, prompt, section_name, *a, **kw)
    V[ACTUAL["v"]]["llamadas"].append({"seccion": section_name, "transaccion": ACTUAL["label"],
                                      "segundos": round(time.time() - t0, 1), "ok": bool(texto),
                                      "prompt_chars": len(prompt)})
    print(f"  ({ACTUAL['v']}) {ACTUAL['label'] or 'general'} / {section_name}: {time.time() - t0:.1f} s"
          f"{'' if texto else '  RESPALDO'}", flush=True)
    return texto


async def _colector(db, execution_id, label, section, texto, orden, **kw):
    V[ACTUAL["v"]]["tx"].setdefault(label, {})[section] = texto


def fallo(r) -> str:
    """El failureMessage del JTL; vacío en el CSV llega como NaN de pandas."""
    import pandas as pd
    v = r.get("failureMessage")
    return "Test failed: code expected to contain /200/" if v is None or pd.isna(v) or not str(v).strip() else str(v)


def xml_errores(df):
    """El archivo de errores sintético: lo que guardaría «View Results Tree» con datos."""
    err = df[~_ok(df)]
    partes = ['<?xml version="1.0" encoding="UTF-8"?>', '<testResults version="1.2">']
    cuerpo = {"404": '{"error": "Not Found", "detalle": "booking no existe"}',
              "403": '{"error": "Forbidden", "detalle": "token requerido"}',
              "405": "Method Not Allowed"}
    for i, (_, r) in enumerate(err.iterrows()):
        rc = str(r["responseCode"])
        metodo = {"4. Get_Booking_Id": "GET", "5. Put_Update_Booking": "PUT"}.get(r["label"], "DELETE")
        cab = (f"Content-Type: application/json\nCookie: token={SECRETOS[0]}\n" if r["label"] == "4. Get_Booking_Id"
               else "Content-Type: application/json\n")   # Put y Delete: sin el token (el fallo confirmado)
        sampler = (f"{metodo} https://restful-booker.herokuapp.com/booking/{1000 + i % 50}\n\n"
                   + (f'{metodo} data:\n{{"firstname": "Ana", "password": "{SECRETOS[1]}"}}\n' if metodo == "PUT" else ""))
        resp = cuerpo.get(rc, f"HTTP {rc}") + (f" sesion={SECRETOS[2]}" if i % 97 == 0 else "")
        partes.append(
            f'<httpSample t="{int(r["elapsed"])}" ts="{int(r["timeStamp"])}" s="false" lb={quoteattr(str(r["label"]))} '
            f'rc={quoteattr(rc)} rm={quoteattr(str(r["responseMessage"]))} tn="Usuarios 1-1">'
            f'<requestHeader class="java.lang.String">{escape(cab)}</requestHeader>'
            f'<responseData class="java.lang.String">{escape(resp)}</responseData>'
            f'<samplerData class="java.lang.String">{escape(sampler)}</samplerData>'
            f'<assertionResult><name>Codigo 200</name><failure>true</failure><error>false</error>'
            f'<failureMessage>{escape(fallo(r))}'
            f'</failureMessage></assertionResult></httpSample>')
    partes.append("</testResults>")
    return "\n".join(partes).encode()


async def variante(clave, parser, df, metrics, criterios, labels, db, tipo, unidad):
    V[clave] = {"llamadas": [], "tokens": [], "tx": {}, "criterios": copy.deepcopy(criterios)}
    ACTUAL.update(v=clave, label=None)
    t0 = time.time()
    res = await run_ai_and_verdict(parser, metrics, tipo, criterios, unidad, db)
    V[clave]["segundos_general"] = round(time.time() - t0, 1)
    V[clave]["general"] = {k: v for k, v in res.__dict__.items() if k.startswith("ai_") and k != "ai_status"}
    V[clave]["ai_status"] = res.ai_status
    V[clave]["veredicto"] = criterios.get("verdict")
    contexto, fases = contexto_de_parser(parser, tipo, unidad, criterios, metrics=metrics)
    V[clave]["bloque"] = contexto
    por_label = {str(r["label"]): r for _, r in parser.get_summary_table_data().iterrows()}
    t1 = time.time()
    for label in labels:
        ACTUAL["label"] = label
        await TR.generate_transaction_report(
            db=db, execution_id=EJECUCION, label=label, metrics={k: por_label[label][k] for k in METRIC_KEYS},
            series=build_transaction_series(df, label), test_type=tipo, acceptance_criteria=criterios,
            df_tx=df[df["label"] == label], fases=fases, contexto=contexto)
    V[clave]["segundos_tx"] = round(time.time() - t1, 1)
    V[clave]["labels"] = labels


async def main():
    G.GeminiAnalyzer._generate = _contado
    G._emit_ai_telemetry = _telemetria
    TR._upsert = _colector
    os.makedirs(SALIDA, exist_ok=True)
    async with Lectura() as db:
        ex = (await db.execute(select(TestExecution).where(TestExecution.id == EJECUCION))).scalar_one()
        tipo, unidad, nombre = ex.test_type or "load", ex.metric_unit or "TPS", ex.name
        guardados = copy.deepcopy(ex.acceptance_criteria_json or {})
        parser, df = _parse_execution_df(ex)
        metrics = parser._calculate_metrics(parser.df_main)
        metrics["total_redirects"] = len(parser.df_redirects)
        metrics["redirect_labels"] = sorted(parser.redirect_labels)

        # (a) como hoy
        a = {k: v for k, v in guardados.items() if k not in ("verdict", "verdicts_per_transaction")}
        # (b) y (c): la ficha del Analista IA, como la deja la conversación del 147
        ficha = FI.construir(parser, metrics, cliente=None, cliente_id=None, proyecto=nombre, tipo=tipo,
                             unidad=unidad, jtl=[ex.jtl_filename])
        FI.agregar_criterios(ficha, CRITERIOS, "chat")
        FI.agregar_relato(ficha, RELATO, "chat")
        ficha["contexto"]["ambiente"] = "QA"
        FI.recalcular(ficha, lambda: parser.df_main)
        b = PA.criterios_para_generar(ficha, [], "comparacion-b")
        xml = xml_errores(parser.df_main)
        fallos = {p["label"]: p["fallos"] for p in ficha["fallos"]["por_transaccion"]}
        resumen = ER.resumir(xml, "xml", fallos)
        c = PA.criterios_para_generar(ficha, [resumen], "comparacion-c")
        json.dump({"resumen_errores": resumen, "xml_bytes": len(xml)},
                  open(f"{SALIDA}/errores_sinteticos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        for clave, crit in (("a", a), ("b", b), ("c", c)):
            print(f"== variante {clave}", flush=True)
            labels = sorted(crit.get("critical_transactions") or [])
            await variante(clave, parser, parser.df_main, metrics, crit, labels, db, tipo, unidad)
        await db.rollback()
    json.dump({"ejecucion": nombre, "variantes": V}, open(f"{SALIDA}/comparacion_analista.json", "w",
                                                        encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    open(f"{SALIDA}/comparacion_analista.html", "w", encoding="utf-8").write(pagina(nombre, V))
    print(json.dumps({k: resumen_v(v) for k, v in V.items()}, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ la página

GENERALES = [("ai_analysis_summary", "Tabla resumen"), ("ai_analysis_errors", "Errores"),
             ("ai_analysis_response_times", "Response Times"), ("ai_analysis_latency", "Latency"),
             ("ai_analysis_error_rate", "Error Rate"), ("ai_analysis_codes_per_second", "Response Codes"),
             ("ai_analysis_transactions_per_second", "TPS"), ("ai_analysis_active_threads", "Active Threads"),
             ("ai_conclusions", "Conclusiones"), ("ai_recommendations", "Recomendaciones")]
SECC_TX = [("summary", "Resumen"), ("chart_response_times", "Response Times"), ("chart_latency", "Latency"),
           ("chart_error_rate", "Error Rate"), ("chart_codes", "Response Codes"), ("chart_tps", "TPS")]
NOMBRE = {"a": "(a) Como hoy — Nuevo Reporte", "b": "(b) Analista IA — criterios y relato",
          "c": "(c) Analista IA — criterios, relato y archivo de errores"}
# Qué recoge cada informe, buscado en conclusiones + recomendaciones + errores
MARCAS = [
    ("El criterio nuevo «errores por cada transacción»", r"errores por transacci[oó]n|cada transacci[oó]n"),
    ("La confirmación de desarrollo (el token no se envía)", r"desarrollo|confirm[oó]"),
    ("Que era una ronda corta antes de la prueba larga", r"ronda corta|validaci[oó]n corta|prueba larga|validar el script"),
    ("El ambiente (QA)", r"\bQA\b"),
    ("Los códigos 404/405 (también están en el JTL)", r"\b40[45]\b"),
    ("Ningún secreto del archivo a la vista", None),
]


def tokens(v):
    t = v["tokens"]
    ok = [x for x in t if x["outcome"] == "ok"]
    p = sum(x["prompt"] for x in ok)
    c = sum(x["cached"] for x in ok)
    return {"intentos": len(t), "prompt": p, "cached": c, "pct_cache": round(100 * c / p, 1) if p else 0,
            "completion": sum(x["completion"] for x in ok), "reasoning": sum(x["reasoning"] for x in ok)}


def resumen_v(v):
    return {"llamadas": len(v["llamadas"]), "respaldo": sum(1 for x in v["llamadas"] if not x["ok"]),
            "segundos": round(v["segundos_general"] + v["segundos_tx"], 1), "general_s": v["segundos_general"],
            "transacciones_s": v["segundos_tx"], "veredicto": v["veredicto"], **tokens(v)}


def todo_texto(v):
    return "\n".join([*(v["general"].get(k) or "" for k, _ in GENERALES),
                      *((t.get(s) or "") for t in v["tx"].values() for s, _ in SECC_TX)])


def pagina(nombre, V):
    E = html.escape
    claves = [k for k in ("a", "b", "c") if k in V]
    R = {k: resumen_v(V[k]) for k in claves}
    filas = [("Llamadas (respaldo)", lambda r: f'{r["llamadas"]} ({r["respaldo"]})'),
             ("Tiempo total", lambda r: f'{r["segundos"]} s (general {r["general_s"]} s · transacciones {r["transacciones_s"]} s)'),
             ("Tokens de entrada", lambda r: f'{r["prompt"]:,}'.replace(",", ".")),
             ("…de ellos en caché", lambda r: f'{r["cached"]:,} ({r["pct_cache"]} %)'.replace(",", ".")),
             ("Tokens de salida (razonamiento)", lambda r: f'{r["completion"]:,} ({r["reasoning"]:,})'.replace(",", ".")),
             ("Veredicto del motor", lambda r: r["veredicto"] or "— (sin criterios del motor)")]
    tabla = "".join(f"<tr><th>{E(n)}</th>" + "".join(f"<td>{E(str(f(R[k])))}</td>" for k in claves) + "</tr>"
                    for n, f in filas)
    estilo = {k: sum(len(detectar_estilo(V[k]["general"].get(c) or "", c)) for c, _ in GENERALES) for k in claves}
    tabla += "<tr><th>Avisos del detector de estilo (general)</th>" + "".join(f"<td>{estilo[k]}</td>" for k in claves) + "</tr>"
    marcas = ""
    for nombre_m, rx in MARCAS:
        celdas = ""
        for k in claves:
            t = "\n".join(V[k]["general"].get(c) or "" for c in ("ai_conclusions", "ai_recommendations",
                                                                  "ai_analysis_errors", "ai_analysis_summary"))
            if rx is None:
                si = not any(s in todo_texto(V[k]) or s in V[k]["bloque"] for s in SECRETOS)
            else:
                si = bool(re.search(rx, t, re.I))
            celdas += f'<td class="{"si" if si else "no"}">{"sí" if si else "no"}</td>'
        marcas += f"<tr><th>{E(nombre_m)}</th>{celdas}</tr>"

    def bloque(titulo, textos):
        return (f'<h3>{E(titulo)}</h3><div class="fila">'
                + "".join(f'<div class="col"><div class="t">{E(t or "—").replace(chr(10), "<br>")}</div></div>' for t in textos)
                + "</div>")
    cuerpo = "".join(bloque(n, [V[k]["general"].get(c) for k in claves]) for c, n in GENERALES)
    labels = sorted({l for k in claves for l in V[k]["tx"]})
    for l in labels:
        cuerpo += f"<h2>{E(l)}</h2>" + "".join(bloque(n, [(V[k]["tx"].get(l) or {}).get(s) for k in claves]) for s, n in SECC_TX)
    cab = "".join(f"<th>{E(NOMBRE[k])}</th>" for k in claves)
    sec = "".join(f'<div class="col"><pre>{E(PA_secciones(V[k]["bloque"]))}</pre></div>' for k in claves)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analista IA — comparación</title><style>
body{{font:13px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#111}}
header{{background:#0a1628;color:#fff;padding:14px 24px;position:sticky;top:0;z-index:2}}
main{{padding:16px 24px}} table{{border-collapse:collapse;background:#fff;width:100%}}
th,td{{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;vertical-align:top}} thead th{{background:#eef2ff}}
td.si{{color:#15803d;font-weight:600}} td.no{{color:#b91c1c;font-weight:600}}
h2{{margin:28px 0 6px;color:#0a1628;border-bottom:2px solid #4f46e5}} h3{{margin:16px 0 6px;font-size:13px;color:#4f46e5}}
.fila{{display:grid;grid-template-columns:repeat({len(claves)},minmax(0,1fr));gap:10px}}
.col{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px}} pre{{white-space:pre-wrap;font-size:11px;margin:0}}
.cab{{display:grid;grid-template-columns:repeat({len(claves)},minmax(0,1fr));gap:10px;font-weight:700;margin-top:14px}}
</style></head><body><header><b>«{E(nombre)}»</b> — el mismo informe, tres veces, con IA real (gpt-5.5). Nada se escribió en la base.</header>
<main><table><thead><tr><th></th>{cab}</tr></thead><tbody>{tabla}</tbody></table>
<h2>Qué recoge el informe (resumen, errores, conclusiones y recomendaciones; búsqueda automática, orientativa)</h2><table><thead><tr><th></th>{cab}</tr></thead><tbody>{marcas}</tbody></table>
<h2>Lo que reciben los prompts de nuevo (las secciones del analista)</h2><div class="fila">{sec}</div>
<h2>Informe general</h2><div class="cab">{"".join(f"<div>{E(NOMBRE[k])}</div>" for k in claves)}</div>{cuerpo}</main></body></html>"""


def PA_secciones(bloque):
    """Del bloque de la ejecución, solo lo que cambia entre variantes: criterios, relato y errores."""
    partes = re.split(r"\n\n", bloque)
    utiles = [p for p in partes if p.startswith(("CRITERIOS DE ACEP", "LO QUE CUENTA", "DETALLE DE LOS ERRORES"))]
    return "\n\n".join(utiles) or "(sin secciones nuevas)"


if __name__ == "__main__":
    if "--solo-html" in sys.argv:
        d = json.load(open(f"{SALIDA}/comparacion_analista.json", encoding="utf-8"))
        open(f"{SALIDA}/comparacion_analista.html", "w", encoding="utf-8").write(pagina(d["ejecucion"], d["variantes"]))
    else:
        asyncio.run(main())
