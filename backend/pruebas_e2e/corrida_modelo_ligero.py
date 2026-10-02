"""Reporte 151, parte 4 — el modelo ligero, con IA REAL y sin escribir en ninguna base.

    docker cp "<descargas>/resultados_log_carga_error_General 30-sept.-2026-162610.csv" jmeter_backend:/tmp/b5_errores_real.xml
    docker exec -w /app -e B5_VERSION=a jmeter_backend python3 /app/pruebas_e2e/corrida_modelo_ligero.py
    docker exec -w /app -e B5_VERSION=b -e B5_LIGERO=gpt-5.4-mini jmeter_backend python3 /app/pruebas_e2e/corrida_modelo_ligero.py
    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/corrida_modelo_ligero.py --combinar
    docker exec jmeter_backend rm -f /tmp/b5_errores_real.xml
    docker cp jmeter_backend:/tmp/b5_ligero/modelo_ligero.html C:\\proyectos\\Kinetix_pruebas\\r2\\

Las dos versiones del informe de Fredy (JTL y criterios de su sesión ea4cdd73,
los mismos de `corrida_analista_v2.py`):
  (a) todo con gpt-5.5 y el reparto de la parte 1 (medio en resumen,
      conclusiones y recomendaciones; bajo en el resto);
  (b) lo mismo, pero el chat y las gráficas con el modelo ligero
      (`AI_MODELO_LIGERO`, solo dentro de este proceso).
En cada versión: el informe general, los de transacción y los tres turnos del
chat de Fredy. La base se lee con una conexión de solo lectura; `_upsert` es un
colector; los contadores de uso no se tocan; `ai_config` no se toca.
"""
import asyncio
import html
import inspect
import json
import os
import re
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")
VERSION = os.environ.get("B5_VERSION", "a")
LIGERO = os.environ.get("B5_LIGERO", "")
if LIGERO:
    os.environ["AI_MODELO_LIGERO"] = LIGERO   # antes de importar gemini: así lo lee el analizador

from sqlalchemy import text   # noqa: E402

from app.services.ai import gemini as G, origen   # noqa: E402
from app.services.ai import transaction_report as TR   # noqa: E402
import app.services.ai.analysis_pipeline as AP   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.services.ai.estilo import detectar_estilo   # noqa: E402
from app.services.jtl.transaction_series import build_transaction_series   # noqa: E402
from app.api.v1.endpoints.upload import METRIC_KEYS, parsear_archivos   # noqa: E402
from app.services.analista import chat as CH, errores as ER, ficha as FI, prompt as PA   # noqa: E402
import corrida_analista_v2 as V2   # noqa: E402  (sesión, criterios corregidos y conexión de solo lectura)

SALIDA = "/tmp/b5_ligero"
TEL, TX = [], {}
ESTADO = {"grupo": "informe", "label": None}
_tel = G._emit_ai_telemetry
_firma = inspect.signature(_tel)


def _telemetria(*a, **kw):
    try:
        arg = _firma.bind(*a, **kw).arguments
        u = getattr(arg.get("response"), "usage", None)
        ptd = getattr(u, "prompt_tokens_details", None)
        ctd = getattr(u, "completion_tokens_details", None)
        from datetime import datetime, timezone
        t0 = arg.get("t0")
        TEL.append({"grupo": ESTADO["grupo"], "seccion": arg.get("section"), "transaccion": ESTADO["label"],
                    "modelo": arg.get("model"), "esfuerzo": arg.get("reasoning_effort"), "outcome": arg.get("outcome"),
                    "entrada": getattr(u, "prompt_tokens", None) or 0, "cache": getattr(ptd, "cached_tokens", None) or 0,
                    "salida": getattr(u, "completion_tokens", None) or 0,
                    "razonamiento": getattr(ctd, "reasoning_tokens", None) or 0,
                    "segundos": round((datetime.now(timezone.utc) - t0).total_seconds(), 1) if t0 else 0})
    except Exception as e:
        print("telemetria:", e)
    return _tel(*a, **kw)


async def _colector(db, execution_id, label, section, texto, orden, **kw):
    TX.setdefault(label, {})[section] = texto


async def main():
    G._emit_ai_telemetry = _telemetria
    TR._upsert = _colector
    os.makedirs(SALIDA, exist_ok=True)
    async with V2.Lectura() as db:
        s = (await db.execute(text("select ficha::text, mensajes::text, jtl::text, test_type, metric_unit "
                                   "from analysis_sessions where id=:i"), {"i": V2.SESION})).one()
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
        conf["reasoning_effort"] = "medium"   # el de la configuración de Fredy desde la parte 1

        async def _conf(_db):
            return dict(conf)
        AP.load_ai_config_from_db = _conf
        TR.load_ai_config_from_db = _conf
        jtl = json.loads(s[2])
        tipo, unidad = s[3], s[4]
        _df, metrics, parser = parsear_archivos([j["ruta"] for j in jtl], [j["nombre"] for j in jtl])
        ficha = FI.construir(parser, metrics, cliente="prueba avianca", cliente_id=None, proyecto="proyecto de prueba",
                             tipo=tipo, unidad=unidad, jtl=[j["nombre"] for j in jtl])
        FI.agregar_criterios(ficha, V2.CRITERIOS, "chat")
        FI.agregar_relato(ficha, V2.RELATO, "chat")
        resumenes = []
        if os.path.exists(V2.ERRORES):
            crudo = open(V2.ERRORES, "rb").read()
            fallos = {p["label"]: p["fallos"] for p in ficha["fallos"]["por_transaccion"]}
            r = ER.resumir(crudo, ER.detectar_formato(crudo), fallos)
            resumenes.append(r)
            ficha["errores_detalle"]["adjuntos"].append(ER.resumen_corto("real", "errores de JMeter", r))
        FI.recalcular(ficha, lambda: parser.df_main)
        crit = PA.criterios_para_generar(ficha, resumenes, V2.SESION)

        an = G.get_gemini_analyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                                   reasoning_effort="medium")
        print("modelo principal:", an.model_name, "· ligero:", an.modelo_ligero)

        t0 = time.time()
        res = await AP.run_ai_and_verdict(parser, metrics, tipo, crit, unidad, db)
        seg_general = round(time.time() - t0, 1)
        contexto, fases = contexto_de_parser(parser, tipo, unidad, crit, metrics=metrics)
        filas = {str(r["label"]): r for _, r in parser.get_summary_table_data().iterrows()}
        t1 = time.time()
        for label in FI.criticas_para_generar(ficha):
            ESTADO["label"] = label
            await TR.generate_transaction_report(
                db=db, execution_id=V2.EJECUCION, label=label, metrics={k: filas[label][k] for k in METRIC_KEYS},
                series=build_transaction_series(parser.df_main, label), test_type=tipo, acceptance_criteria=crit,
                df_tx=parser.df_main[parser.df_main["label"] == label], fases=fases, contexto=contexto)
        ESTADO["label"] = None
        seg_tx = round(time.time() - t1, 1)

        # los tres turnos del chat de Fredy (primer mensaje + sus dos mensajes)
        ESTADO["grupo"] = "chat"
        mensajes = json.loads(s[1])
        bloque = contexto_de_parser(parser, tipo, unidad, {"analista": {"estado_criterios": "sin_declarar"}}, metrics)[0]
        f0 = FI.construir(parser, metrics, cliente="prueba avianca", cliente_id=None, proyecto="proyecto de prueba",
                          tipo=tipo, unidad=unidad, jtl=[j["nombre"] for j in jtl])
        FI.recalcular(f0)
        chat = []
        raw, _ = await origen.llamar(an._generate, CH.prompt_primer_mensaje(bloque), section_name="analista_chat",
                                     sistema=CH.SISTEMA, sanear=False, max_retries=2)
        chat.append({"turno": "primer mensaje", "valido": V2._valido(raw), "texto": (raw or "")[:900]})
        previos = [mensajes[0]]
        for m in [x for x in mensajes if x["rol"] == "analista"]:
            raw, _ = await origen.llamar(an._generate, CH.prompt_turno(bloque, f0, previos, m["texto"]),
                                         section_name="analista_chat", sistema=CH.SISTEMA, sanear=False, max_retries=2)
            chat.append({"turno": m["texto"][:80], "valido": V2._valido(raw), "texto": (raw or "")[:900]})
            previos = previos + [m]

    datos = {"version": VERSION, "principal": conf["model_name"], "ligero": LIGERO or None,
             "general": {k: v for k, v in res.__dict__.items() if k.startswith("ai_") and k != "ai_status"},
             "ai_status": res.ai_status, "transacciones": TX, "chat": chat, "telemetria": TEL,
             "segundos_general": seg_general, "segundos_tx": seg_tx}
    json.dump(datos, open(f"{SALIDA}/version_{VERSION}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(totales(TEL), ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ medir

def _clase(t):
    s = t["seccion"] or ""
    if s == "analista_chat":
        return "chat"
    if s.startswith("chart_") or s.startswith("txreport_chart_"):
        return "graficas"
    if s in ("summary_table", "conclusions", "recommendations"):
        return "resumen_conc_reco"
    return "resto"   # errores, redirecciones y resumen de cada transacción


def totales(tel):
    out = {}
    for t in tel:
        if t["outcome"] != "ok":
            continue
        for clave in (_clase(t), "total"):
            g = out.setdefault(clave, {"llamadas": 0, "entrada": 0, "cache": 0, "salida": 0, "razonamiento": 0,
                                       "segundos": 0.0, "modelos": set()})
            g["llamadas"] += 1
            for k in ("entrada", "cache", "salida", "razonamiento"):
                g[k] += t[k]
            g["segundos"] = round(g["segundos"] + t["segundos"], 1)
            g["modelos"].add(f'{t["modelo"]}/{t["esfuerzo"]}')
    for g in out.values():
        g["modelos"] = sorted(g["modelos"])
    return out


_CIFRA = re.compile(r"\d[\d.,]*")
_RAMPA = re.compile(r"\brampa|\bescal[oó]n|\bmeseta|\bfase de (?:subida|bajada|sostenimiento)", re.I)


def estilo(texto):
    t = (texto or "").strip()
    return {"parrafos": len([p for p in re.split(r"\n\s*\n", t) if p.strip()]),
            "cifras": len(_CIFRA.findall(t)), "palabras": len(t.split()),
            "rampas": sorted({m.group(0).lower() for m in _RAMPA.finditer(t)}),
            "avisos": [a["termino"] for a in detectar_estilo(t, "chart")]}


# ------------------------------------------------------------------ la página

E = html.escape
GRAFICAS = [("ai_analysis_response_times", "Response Times"), ("ai_analysis_latency", "Latency"),
            ("ai_analysis_error_rate", "Error Rate"), ("ai_analysis_codes_per_second", "Response Codes"),
            ("ai_analysis_transactions_per_second", "TPS"), ("ai_analysis_active_threads", "Active Threads")]
GRAFICAS_TX = [("chart_response_times", "Response Times"), ("chart_latency", "Latency"),
               ("chart_error_rate", "Error Rate"), ("chart_codes", "Response Codes"), ("chart_tps", "TPS")]


def _n(x):
    return f"{x:,.0f}".replace(",", ".") if isinstance(x, int) else f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fila_estilo(e):
    r = f'{e["parrafos"]} párr. · {e["cifras"]} cifras · {e["palabras"]} palabras'
    if e["rampas"]:
        r += f' · <b class="mal">cita: {E(", ".join(e["rampas"]))}</b>'
    if e["avisos"]:
        r += f' · <b class="mal">aviso: {E(", ".join(e["avisos"]))}</b>'
    return r


def _par(nombre, ta, tb):
    ea, eb = estilo(ta), estilo(tb)
    return (f'<h3>{E(nombre)}</h3><div class="par"><div class="col"><p class="m">{_fila_estilo(ea)}</p>'
            f'{E(ta or "(vacío)").replace(chr(10), "<br>")}</div><div class="col"><p class="m">{_fila_estilo(eb)}</p>'
            f'{E(tb or "(vacío)").replace(chr(10), "<br>")}</div></div>'), ea, eb


def pagina(a, b):
    ta, tb = totales(a["telemetria"]), totales(b["telemetria"])
    filas = ""
    for clave, nombre in (("chat", "Chat (3 turnos)"), ("graficas", "Gráficas (generales y por transacción)"),
                          ("resumen_conc_reco", "Resumen, conclusiones y recomendaciones"),
                          ("resto", "Errores, redirecciones y resumen de cada transacción"), ("total", "TOTAL")):
        for v, t in (("a", ta), ("b", tb)):
            g = t.get(clave, {})
            if not g:
                continue
            cache_pct = f' ({100 * g["cache"] / g["entrada"]:.0f} %)'.replace(".", ",") if g["entrada"] else ""
            filas += (f'<tr class="{"tot" if clave == "total" else ""}"><td>{E(nombre)}</td><td>({v})</td><td>{E(", ".join(g["modelos"]))}</td>'
                      f'<td>{g["llamadas"]}</td><td>{_n(g["entrada"])}</td><td>{_n(g["cache"])}{cache_pct}</td>'
                      f'<td>{_n(g["salida"])}</td><td>{_n(g["razonamiento"])}</td><td>{_n(g["segundos"])}</td></tr>')
    cuerpo, resumen_estilo = "", {"a": [], "b": []}
    cuerpo += "<h2>Informe general</h2>"
    for k, n in GRAFICAS:
        h, ea, eb = _par(n, a["general"].get(k), b["general"].get(k))
        cuerpo += h
        resumen_estilo["a"].append(ea)
        resumen_estilo["b"].append(eb)
    for label in a["transacciones"]:
        cuerpo += f"<h2>{E(label)}</h2>"
        for k, n in GRAFICAS_TX:
            h, ea, eb = _par(n, a["transacciones"][label].get(k), (b["transacciones"].get(label) or {}).get(k))
            cuerpo += h
            resumen_estilo["a"].append(ea)
            resumen_estilo["b"].append(eb)

    def _res(lista):
        un = sum(1 for e in lista if e["parrafos"] == 1)
        rampas = sum(1 for e in lista if e["rampas"])
        avisos = sum(1 for e in lista if e["avisos"])
        cifras = sum(e["cifras"] for e in lista) / max(1, len(lista))
        palabras = sum(e["palabras"] for e in lista) / max(1, len(lista))
        return (f"{un} de {len(lista)} en un solo párrafo · {cifras:.1f} cifras y {palabras:.0f} palabras de media · "
                f"{rampas} citan rampas/escalones · {avisos} con aviso del detector").replace(".", ",", 2)

    def _chat(v):
        return "".join(f'<li>{E(c["turno"])}: <b class="{"ok" if c["valido"].get("ok") else "mal"}">'
                       f'{"JSON válido" if c["valido"].get("ok") else "JSON NO válido: " + E(c["valido"].get("motivo", ""))}</b>'
                       f'{(" · " + str(c["valido"].get("criterios")) + " criterios") if c["valido"].get("ok") else ""}</li>'
                       for c in v["chat"])
    chat_txt = "".join(f'<h3>{E(ca["turno"])}</h3><div class="par"><div class="col"><pre>{E(ca["texto"])}</pre></div>'
                       f'<div class="col"><pre>{E(cb["texto"])}</pre></div></div>' for ca, cb in zip(a["chat"], b["chat"]))
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modelo ligero</title><style>
:root{{--bg:#fff;--fg:#1f2937;--mu:#6b7280;--li:#e5e7eb;--ca:#f9fafb;--ok:#047857;--mal:#b91c1c;--ac:#4f46e5}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#0f172a;--fg:#e5e7eb;--mu:#9ca3af;--li:#334155;--ca:#1e293b;--ok:#34d399;--mal:#f87171;--ac:#818cf8}}}}
:root[data-theme="dark"]{{--bg:#0f172a;--fg:#e5e7eb;--mu:#9ca3af;--li:#334155;--ca:#1e293b;--ok:#34d399;--mal:#f87171;--ac:#818cf8}}
body{{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif;margin:0}}main{{max-width:1300px;margin:0 auto;padding:16px}}
h1{{font-size:1.5rem}}h2{{border-bottom:2px solid var(--ac);padding-bottom:4px;margin-top:2rem}}h3{{font-size:1rem;margin:1.2rem 0 .4rem}}
.tabla{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}td,th{{border:1px solid var(--li);padding:4px 8px;text-align:right}}
td:first-child,td:nth-child(2),td:nth-child(3),th{{text-align:left}}tr.tot td{{font-weight:700}}
.par{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}@media (max-width:760px){{.par{{grid-template-columns:1fr}}}}
.col{{background:var(--ca);border:1px solid var(--li);border-radius:8px;padding:10px}}.m{{color:var(--mu);font-size:.8rem;margin:0 0 6px}}
.ok{{color:var(--ok)}}.mal{{color:var(--mal)}}pre{{white-space:pre-wrap;font-size:.8rem;margin:0}}code{{background:var(--ca);padding:0 4px}}
.cab{{display:grid;grid-template-columns:1fr 1fr;gap:12px;font-weight:700}}
</style></head><body><main>
<h1>Modelo ligero en el chat y las gráficas — reporte 151</h1>
<p>El informe de Fredy (JTL «resultados_general_carga 30-sept.-2026-162610», criterios de su sesión), generado dos veces con IA real y <b>sin escribir en ninguna base</b>.
<b>(a)</b> todo con <code>{E(a["principal"])}</code> y el reparto de la parte 1. <b>(b)</b> chat y gráficas con <code>{E(b["ligero"] or "")}</code>; resumen, conclusiones, recomendaciones y el resto con <code>{E(b["principal"])}</code>.
La configuración no cambió: el modelo ligero existió solo dentro del proceso de la prueba.</p>
<h2>Tokens y tiempo</h2><div class="tabla"><table><tr><th>Llamadas</th><th>Versión</th><th>Modelo / esfuerzo</th><th>N.º</th><th>Entrada</th><th>Caché</th><th>Salida</th><th>Razonamiento</th><th>Segundos (suma)</th></tr>{filas}</table></div>
<p>Tiempo de pared: (a) general {_n(a["segundos_general"])} s + transacciones {_n(a["segundos_tx"])} s · (b) general {_n(b["segundos_general"])} s + transacciones {_n(b["segundos_tx"])} s.</p>
<p><b>Coste</b>, por modelo: <code>coste = (entrada − caché) × P<sub>entrada</sub> + caché × P<sub>caché</sub> + salida × P<sub>salida</sub></code>, con los precios por token de cada modelo en la tarifa vigente de OpenAI. La salida ya incluye el razonamiento. En (b) se suman dos términos: uno con las filas de <code>{E(b["principal"])}</code> y sus precios, otro con las de <code>{E(b["ligero"] or "")}</code> y los suyos.</p>
<p class="m">La caché de (b) no es del todo comparable: (b) corrió después de (a) y las llamadas de <code>{E(b["principal"])}</code> encontraron en caché el prefijo que dejó (a). La caché es de cada modelo: el ligero empieza en frío.</p>
<h2>¿Respetó el estilo?</h2>
<p>(a) {_res(resumen_estilo["a"])}<br>(b) {_res(resumen_estilo["b"])}</p>
<h2>¿Salió válido el JSON del chat?</h2><div class="par"><div class="col"><b>(a)</b><ul>{_chat(a)}</ul></div><div class="col"><b>(b)</b><ul>{_chat(b)}</ul></div></div>
<div class="cab"><div>(a) {E(a["principal"])}</div><div>(b) {E(b["ligero"] or "")}</div></div>
{cuerpo}
<h2>El chat, turno a turno</h2>{chat_txt}
</main></body></html>"""


if __name__ == "__main__":
    if "--combinar" in sys.argv:
        a = json.load(open(f"{SALIDA}/version_a.json", encoding="utf-8"))
        b = json.load(open(f"{SALIDA}/version_b.json", encoding="utf-8"))
        open(f"{SALIDA}/modelo_ligero.html", "w", encoding="utf-8").write(pagina(a, b))
        for v, d in (("a", a), ("b", b)):
            print(v, json.dumps(totales(d["telemetria"]), ensure_ascii=False, default=list))
    else:
        asyncio.run(main())
