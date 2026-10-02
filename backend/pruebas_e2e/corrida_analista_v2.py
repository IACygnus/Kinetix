"""Reporte 150, puntos 5 y 6 — el informe de Fredy, antes y ahora, con IA REAL y sin escribir.

    docker cp "<descargas>/resultados_log_carga_error_General 30-sept.-2026-162610.csv" jmeter_backend:/tmp/b5_errores_real.xml
    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/corrida_analista_v2.py
    docker exec jmeter_backend rm -f /tmp/b5_errores_real.xml
    docker cp jmeter_backend:/tmp/b5_v2/. C:\\proyectos\\Kinetix_pruebas\\r2\\
    (con --solo-html rehace la página desde el JSON, sin llamar a la IA)

B5_ESFUERZO=medium|low fuerza el razonamiento SOLO dentro de este proceso (no toca
`ai_config`): la configuración de Fredy pasó a «low» a las 17:51 UTC del 2/10,
después de su generación, y para comparar con su informe (hecho en «medium») hay
que usar el mismo. La salida va a analista_v2_<esfuerzo>.json, y
`--combinar` junta la de «medium» (la página) con la de «low» (coste y textos).

La sesión real de Fredy (ea4cdd73, «prueba avianca · proyecto de prueba») y la
ejecución que generó (9b27f1a6) se LEEN con una conexión de solo lectura. Nada
se escribe en ninguna base: la ficha vive en memoria, `_upsert` es un colector y
no se tocan los contadores de uso.

  ANTES  los textos que ya están guardados de la ejecución 9b27f1a6
  AHORA  el mismo JTL con los criterios de su sesión YA CORREGIDOS (abajo) y su
         archivo de errores (copia temporal en /tmp, que se borra al terminar)

Y para el punto 5, en la misma corrida:
  - las 6 gráficas del informe nuevo, otra vez con razonamiento BAJO;
  - los 3 turnos del chat de Fredy, repetidos con razonamiento MEDIO y BAJO.
Cuidado al leer la caché de las repeticiones: el mismo prompt dos veces se cachea.
"""
import asyncio
import copy
import html
import inspect
import json
import os
import sys
import time

sys.path.insert(0, "/app")
from sqlalchemy import text   # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine   # noqa: E402

from app.core.config import settings   # noqa: E402
from app.services.ai import gemini as G, origen   # noqa: E402
from app.services.ai import transaction_report as TR   # noqa: E402
from app.services.ai.analysis_pipeline import run_ai_and_verdict   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.services.jtl.transaction_series import build_transaction_series   # noqa: E402
from app.api.v1.endpoints.upload import METRIC_KEYS, parsear_archivos   # noqa: E402
from app.services.analista import chat as CH, errores as ER, ficha as FI, prompt as PA   # noqa: E402
from app.services.analista import criterios_libres as CL   # noqa: E402

SESION = "ea4cdd73-b5ab-4e5e-8b1b-1aa02cf94eba"
EJECUCION = "9b27f1a6-6e55-4112-9740-1b74c6e2e13b"
ERRORES = "/tmp/b5_errores_real.xml"
SALIDA = "/tmp/b5_v2"
ESFUERZO = os.environ.get("B5_ESFUERZO", "")
A, O, R = "1. SaveFunds_AsegurarFondos", "3. Webhook_Originator", "1. Webhook_Receptor"

# Los criterios de la sesión de Fredy, CORREGIDOS como él los explicó:
#  - «5 segundos el tiempo de espera»: por servicio. La medida no la dijo: se usa
#    el MÁXIMO (su propio modelo de resumen juzga los máximos frente al umbral).
#    Es una interpretación: hay que confirmarla con él.
#  - «64.000 entre asegurar fondos y originador»: él corrigió «es por servicio,
#    no el total». Se toma 32.000 para cada uno (el reparto del total). Con 64.000
#    cada uno el resultado sería el mismo: los dos están por debajo de 11.000.
#  - «8.000 para receptor» y los 30 minutos de la prueba.
#  - «28 usuarios concurrentes» en los dos servicios del grupo Originador.
CRITERIOS = [
    {"texto": "5 segundos el tiempo de espera, en cada servicio (medida: el máximo)", "tipo": "tiempo_respuesta",
     "metrica": "max", "operador": "<=", "valor": 5, "unidad": "s", "cada_transaccion": True},
    {"texto": "64.000 transacciones entre asegurar fondos y originador, por servicio (32.000 cada uno) en 30 minutos",
     "tipo": "volumen", "valor": 32000, "transacciones": [A, O], "ventana_valor": 30, "ventana_unidad": "min"},
    {"texto": "8.000 transacciones para receptor en 30 minutos", "tipo": "volumen", "valor": 8000,
     "transacciones": [R], "ventana_valor": 30, "ventana_unidad": "min"},
    {"texto": "28 usuarios concurrentes en los dos servicios (asegurar fondos y originador)", "tipo": "concurrencia",
     "valor": 28, "transacciones": [A, O]},
]
RELATO = ["Los volúmenes acordados se analizan por servicio, no como un total combinado."]

_motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                             connect_args={"server_settings": {"default_transaction_read_only": "on"}})
Lectura = async_sessionmaker(_motor, class_=AsyncSession, expire_on_commit=False, autoflush=False)

TEL = []          # una fila por intento: grupo, sección, tokens, segundos
ESTADO = {"grupo": "nuevo", "label": None}
PROMPTS = {}      # sección -> prompt (para repetir las gráficas con razonamiento bajo)
TX = {}
_gen = G.GeminiAnalyzer._generate
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
                    "esfuerzo": arg.get("reasoning_effort"),
                    "outcome": arg.get("outcome"), "entrada": getattr(u, "prompt_tokens", None) or 0,
                    "cache": getattr(ptd, "cached_tokens", None) or 0, "salida": getattr(u, "completion_tokens", None) or 0,
                    "razonamiento": getattr(ctd, "reasoning_tokens", None) or 0,
                    "segundos": round((datetime.now(timezone.utc) - t0).total_seconds(), 1) if t0 else 0})
    except Exception as e:
        print("telemetria:", e)
    return _tel(*a, **kw)


def _generate(self, prompt, section_name="unknown", *a, **kw):
    if ESTADO["grupo"] == "nuevo" and ESTADO["label"] is None:
        PROMPTS[section_name] = (prompt, kw.get("permite_veredicto", False))
    return _gen(self, prompt, section_name, *a, **kw)


async def _colector(db, execution_id, label, section, texto, orden, **kw):
    TX.setdefault(label, {})[section] = texto


async def main():
    G._emit_ai_telemetry = _telemetria
    G.GeminiAnalyzer._generate = _generate
    TR._upsert = _colector
    os.makedirs(SALIDA, exist_ok=True)
    async with Lectura() as db:
        s = (await db.execute(text("select ficha::text, mensajes::text, jtl::text, test_type, metric_unit "
                                   "from analysis_sessions where id=:i"), {"i": SESION})).one()
        e = (await db.execute(text("select acceptance_criteria_json::text, ai_analysis_summary, ai_analysis_errors, "
                                   "ai_analysis_response_times, ai_analysis_latency, ai_analysis_error_rate, "
                                   "ai_analysis_codes_per_second, ai_analysis_transactions_per_second, "
                                   "ai_analysis_active_threads, ai_conclusions, ai_recommendations "
                                   "from test_executions where id=:i"), {"i": EJECUCION})).one()
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
        if ESFUERZO:
            conf["reasoning_effort"] = ESFUERZO
            import app.services.ai.analysis_pipeline as AP

            async def _conf(_db):
                return dict(conf)
            AP.load_ai_config_from_db = _conf
            TR.load_ai_config_from_db = _conf
        jtl = json.loads(s[2])
        tipo, unidad = s[3], s[4]
        _df, metrics, parser = parsear_archivos([j["ruta"] for j in jtl], [j["nombre"] for j in jtl])

        ficha = FI.construir(parser, metrics, cliente="prueba avianca", cliente_id=None, proyecto="proyecto de prueba",
                             tipo=tipo, unidad=unidad, jtl=[j["nombre"] for j in jtl])
        FI.agregar_criterios(ficha, CRITERIOS, "chat")
        FI.agregar_relato(ficha, RELATO, "chat")
        resumenes = []
        if os.path.exists(ERRORES):
            fallos = {p["label"]: p["fallos"] for p in ficha["fallos"]["por_transaccion"]}
            r = ER.resumir(open(ERRORES, "rb").read(), ER.detectar_formato(open(ERRORES, "rb").read()), fallos)
            resumenes.append(r)
            ficha["errores_detalle"]["adjuntos"].append(ER.resumen_corto("real", "errores de JMeter", r))
        FI.recalcular(ficha, lambda: parser.df_main)
        crit = PA.criterios_para_generar(ficha, resumenes, SESION)

        an = G.get_gemini_analyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                                   reasoning_effort=conf.get("reasoning_effort") or "")
        # --- AHORA: el informe nuevo (10 generales + 6 por cada transacción con informe propio)
        ESTADO.update(grupo="nuevo", label=None)
        t0 = time.time()
        res = await run_ai_and_verdict(parser, metrics, tipo, crit, unidad, db)
        seg_general = round(time.time() - t0, 1)
        contexto, fases = contexto_de_parser(parser, tipo, unidad, crit, metrics=metrics)
        filas = {str(r["label"]): r for _, r in parser.get_summary_table_data().iterrows()}
        labels = FI.criticas_para_generar(ficha)
        t1 = time.time()
        for label in labels:
            ESTADO["label"] = label
            await TR.generate_transaction_report(
                db=db, execution_id=EJECUCION, label=label, metrics={k: filas[label][k] for k in METRIC_KEYS},
                series=build_transaction_series(parser.df_main, label), test_type=tipo, acceptance_criteria=crit,
                df_tx=parser.df_main[parser.df_main["label"] == label], fases=fases, contexto=contexto)
        ESTADO["label"] = None
        seg_tx = round(time.time() - t1, 1)

        # --- Punto 5: las 6 gráficas con razonamiento BAJO (mismo prompt)
        bajo = G.GeminiAnalyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                                reasoning_effort="low")
        ESTADO["grupo"] = "graficas_bajo"
        bajo_txt = {}
        for sec in [k for k in PROMPTS if k.startswith("chart_")]:
            p, perm = PROMPTS[sec]
            bajo_txt[sec], _ = await origen.llamar(bajo._generate, p, section_name=sec, permite_veredicto=perm)

        # --- Punto 5: los 3 turnos del chat de Fredy, con razonamiento MEDIO y BAJO
        mensajes = json.loads(s[1])
        bloque = contexto_de_parser(parser, tipo, unidad, {"analista": {"estado_criterios": "sin_declarar"}},
                                    metrics)[0]
        f0 = FI.construir(parser, metrics, cliente="prueba avianca", cliente_id=None, proyecto="proyecto de prueba",
                          tipo=tipo, unidad=unidad, jtl=[j["nombre"] for j in jtl])
        FI.recalcular(f0)
        chat = {}
        for esfuerzo, analizador in (("medio", an), ("bajo", bajo)):
            ESTADO["grupo"] = f"chat_{esfuerzo}"
            chat[esfuerzo] = []
            # el primer mensaje y los dos turnos del analista
            p1 = CH.prompt_primer_mensaje(bloque)
            raw, _ = await origen.llamar(analizador._generate, p1, section_name="analista_chat",
                                         sistema=CH.SISTEMA, sanear=False, max_retries=2)
            chat[esfuerzo].append({"turno": "primer mensaje", "valido": _valido(raw), "texto": (raw or "")[:400]})
            previos = [mensajes[0]]
            for m in [x for x in mensajes if x["rol"] == "analista"]:
                p = CH.prompt_turno(bloque, f0, previos, m["texto"])
                raw, _ = await origen.llamar(analizador._generate, p, section_name="analista_chat",
                                             sistema=CH.SISTEMA, sanear=False, max_retries=2)
                chat[esfuerzo].append({"turno": m["texto"][:80], "valido": _valido(raw), "texto": (raw or "")[:900]})
                previos = previos + [m]

    antes = {k: v for k, v in zip(["acceptance", "ai_analysis_summary", "ai_analysis_errors", "ai_analysis_response_times",
                                    "ai_analysis_latency", "ai_analysis_error_rate", "ai_analysis_codes_per_second",
                                    "ai_analysis_transactions_per_second", "ai_analysis_active_threads",
                                    "ai_conclusions", "ai_recommendations"], e)}
    antes_crit = json.loads(antes.pop("acceptance"))
    datos = {
        "antes": {"textos": antes, "veredicto": antes_crit.get("verdict"),
                  "veredictos_tx": antes_crit.get("verdicts_per_transaction"),
                  "criterios": (antes_crit.get("analista") or {}).get("criterios") or []},
        "ahora": {"textos": {k: v for k, v in res.__dict__.items() if k.startswith("ai_") and k != "ai_status"},
                  "ai_status": res.ai_status, "veredicto": crit.get("verdict"),
                  "veredictos_tx": crit.get("verdicts_per_transaction"), "transacciones": TX,
                  "criterios": ficha["criterios"]["lista"], "grupos": ficha["criterios"]["grupos"],
                  "segundos_general": seg_general, "segundos_tx": seg_tx},
        "graficas_bajo": bajo_txt, "chat": chat, "telemetria": TEL,
        "errores_adjunto": bool(resumenes),
    }
    datos["esfuerzo"] = conf.get("reasoning_effort")
    json.dump(datos, open(f"{SALIDA}/analista_v2_{datos['esfuerzo']}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(resumen_coste(TEL), ensure_ascii=False, indent=1))


def _valido(raw):
    try:
        d = CH.leer_json(raw)
        return {"ok": True, "criterios": len(d["criterios"])}
    except Exception as e:
        return {"ok": False, "motivo": str(e)[:80]}


def resumen_coste(tel):
    out = {}
    for t in tel:
        if t["outcome"] != "ok":
            continue
        g = out.setdefault(t["grupo"], {"llamadas": 0, "entrada": 0, "cache": 0, "salida": 0, "razonamiento": 0,
                                         "segundos": 0.0})
        g["llamadas"] += 1
        for k in ("entrada", "cache", "salida", "razonamiento"):
            g[k] += t[k]
        g["segundos"] = round(g["segundos"] + t["segundos"], 1)
    return out


# ------------------------------------------------------------------ la página

E = html.escape
SECC = [("ai_analysis_summary", "Resumen"), ("ai_conclusions", "Conclusiones"), ("ai_recommendations", "Recomendaciones"),
        ("ai_analysis_errors", "Errores"), ("ai_analysis_response_times", "Response Times"),
        ("ai_analysis_latency", "Latency"), ("ai_analysis_error_rate", "Error Rate"),
        ("ai_analysis_codes_per_second", "Response Codes"), ("ai_analysis_transactions_per_second", "TPS"),
        ("ai_analysis_active_threads", "Active Threads")]
TXS = [("summary", "Resumen"), ("chart_response_times", "Response Times"), ("chart_latency", "Latency"),
       ("chart_error_rate", "Error Rate"), ("chart_codes", "Response Codes"), ("chart_tps", "TPS")]
COLOR = {"cumple": "#15803d", "no_cumple": "#b91c1c", "no_evaluado": "#6b7280", "lo_confirma_el_analista": "#b45309"}


def _t(x):
    return E(x or "—").replace("\n", "<br>")


def pagina(d):
    an, ah = d["antes"], d["ahora"]
    filas_c = "".join(
        f'<tr><td>{E(c["texto"])}</td><td>{E(CL.describir(c))}</td><td>{E(CL.alcance_txt(c))}</td>'
        f'<td><b style="color:{COLOR.get(c["resultado"]["estado"], "#000")}">{E(c["resultado"]["estado"].replace("_", " "))}</b>'
        f'<br><small>{E(c["resultado"].get("texto") or c["resultado"].get("motivo") or "")}</small></td></tr>'
        for c in ah["criterios"])
    filas_a = "".join(
        f'<tr><td>{E(c.get("texto"))}</td><td>{E((c.get("alcance") or {}).get("tipo", ""))}</td>'
        f'<td>{E((c.get("resultado") or {}).get("estado", ""))}'
        f'{" (confirmado: " + E(c["confirmacion"]) + ")" if c.get("confirmacion") else ""}<br>'
        f'<small>{E((c.get("resultado") or {}).get("texto", ""))}</small></td></tr>' for c in an["criterios"])
    secciones = "".join(f'<h3>{E(n)}</h3><div class="fila"><div class="col">{_t(an["textos"].get(k))}</div>'
                        f'<div class="col">{_t(ah["textos"].get(k))}</div></div>' for k, n in SECC)
    tx = ""
    for label, secs in ah["transacciones"].items():
        tx += f"<h2>{E(label)} (solo en el informe nuevo)</h2>" + "".join(
            f'<h3>{E(n)}</h3><div class="col">{_t(secs.get(k))}</div>' for k, n in TXS)
    coste = resumen_coste(d["telemetria"])
    nombres = {"nuevo": "Informe nuevo (medio)", "graficas_bajo": "Las 6 gráficas, con razonamiento BAJO",
               "chat_medio": "Chat de Fredy repetido, MEDIO", "chat_bajo": "Chat de Fredy repetido, BAJO"}
    n = lambda x: f"{x:,}".replace(",", ".")
    filas_coste = "".join(
        f"<tr><td>{E(nombres.get(g, g))}</td><td>{v['llamadas']}</td><td>{n(v['entrada'])}</td><td>{n(v['cache'])}</td>"
        f"<td>{n(v['salida'])}</td><td>{n(v['razonamiento'])}</td><td>{v['segundos']}</td></tr>"
        for g, v in coste.items())
    if d.get("bajo"):
        cb = resumen_coste(d["bajo"]["telemetria"]).get("nuevo", {})
        filas_coste += (f"<tr><td>Informe nuevo, todo en BAJO (la configuración actual de Fredy)</td><td>{cb.get('llamadas')}</td>"
                        f"<td>{n(cb.get('entrada', 0))}</td><td>{n(cb.get('cache', 0))}</td><td>{n(cb.get('salida', 0))}</td>"
                        f"<td>{n(cb.get('razonamiento', 0))}</td><td>{cb.get('segundos')}</td></tr>")
    chat = "".join(f"<h3>Chat · {E(k)}</h3><ul>" + "".join(
        f"<li>{E(x['turno'])} → JSON {'válido' if x['valido']['ok'] else 'NO válido'}"
        f"{' · ' + str(x['valido'].get('criterios')) + ' criterios' if x['valido']['ok'] else ''}</li>" for x in v)
        + "</ul>" for k, v in d["chat"].items())
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analista IA — antes y ahora</title><style>
body{{font:13px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#111}}
header{{background:#0a1628;color:#fff;padding:14px 24px}} main{{padding:16px 24px}}
table{{border-collapse:collapse;background:#fff;width:100%;margin-bottom:8px}} th,td{{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#eef2ff}} h2{{margin:26px 0 6px;border-bottom:2px solid #4f46e5}} h3{{margin:14px 0 6px;color:#4f46e5;font-size:13px}}
.fila{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} .col{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:10px}}
.cab{{display:grid;grid-template-columns:1fr 1fr;gap:10px;font-weight:700}} .v{{font-size:18px;font-weight:700}}
</style></head><body><header><b>«prueba avianca · proyecto de prueba»</b> — el informe que generó Fredy y el de ahora, con IA real (gpt-5.5). Nada se escribió en la base.</header><main>
<h2>Criterios de aceptación y su resultado (ahora, corregidos)</h2>
<p>Interpretaciones a confirmar con Fredy: el tiempo de 5 s se mide sobre el <b>máximo</b> de cada servicio; los 64.000 «por servicio» se toman como 32.000 cada uno; <b>la IA real, con su misma frase, entendió 64.000 cada uno</b> (ver el chat de abajo). El resultado es el mismo: los dos servicios rondan las 9.500 peticiones correctas en 30 minutos.</p>
<table><tr><th>Lo que dijo</th><th>Cómo lo entiende Kinetix</th><th>Sobre</th><th>Resultado</th></tr>{filas_c}</table>
<p class="v">Veredicto — antes: {E(str(an['veredicto']))} (y las conclusiones decían «apto para avanzar») · ahora: {E(str(ah['veredicto']))}</p>
<p>Por transacción — antes: {E(json.dumps(an['veredictos_tx'], ensure_ascii=False))}<br>ahora: {E(json.dumps(ah['veredictos_tx'], ensure_ascii=False))}</p>
<h3>Los criterios tal como llegaron al informe de antes</h3><table><tr><th>Texto</th><th>Alcance</th><th>Resultado</th></tr>{filas_a}</table>
<h2>Coste de esta corrida</h2><table><tr><th>Grupo</th><th>Llamadas</th><th>Entrada</th><th>…en caché</th><th>Salida</th><th>…razonamiento</th><th>Segundos</th></tr>{filas_coste}</table>
{chat}
<h2>Informe general: antes (izquierda) y ahora (derecha), los dos con razonamiento medio</h2><div class="cab"><div>Antes (9b27f1a6, lo que generó Fredy)</div><div>Ahora (criterios corregidos)</div></div>{secciones}
{tx}
{_bajo(d)}
</main></body></html>"""


def _bajo(d):
    b = d.get("bajo")
    if not b:
        return ""
    return ("<h2>El informe nuevo con razonamiento BAJO (la configuración actual)</h2><details><summary>Ver los textos</summary>"
            + "".join(f'<h3>{E(n)}</h3><div class="col">{_t(b["ahora"]["textos"].get(k))}</div>' for k, n in SECC)
            + "</details>")


if __name__ == "__main__":
    if "--combinar" in sys.argv or "--solo-html" in sys.argv:
        d = json.load(open(f"{SALIDA}/analista_v2_medium.json", encoding="utf-8"))
        bajo = f"{SALIDA}/analista_v2_low.json"
        d["bajo"] = json.load(open(bajo, encoding="utf-8")) if os.path.exists(bajo) else None
        open(f"{SALIDA}/analista_v2.html", "w", encoding="utf-8").write(pagina(d))
    else:
        asyncio.run(main())
