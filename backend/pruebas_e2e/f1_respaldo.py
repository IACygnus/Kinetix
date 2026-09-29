"""F1 (aviso de respaldo) — backend. Sin IA real y sin la base de Fredy.

    docker exec -e KX_API=http://localhost:8002/api/v1 -e KX_DB=jmeter_analyzer_test \
        -e KX_SESION=/tmp/e2e_sesion_test.json jmeter_backend python3 /app/pruebas_e2e/f1_respaldo.py

A. En proceso, con un cliente de OpenAI FALSO (ninguna peticion sale a la IA):
   1. el buzon de `_generate` recoge el tipo y el literal: 401 -> clave,
      insufficient_quota -> cupo, y dos llamadas en paralelo no se pisan;
   2. `run_ai_and_verdict` con la clave rechazada: las 10 secciones «respaldo»,
      motivo «clave», y `success` en falso aunque la primera tambien fallara;
      con la IA respondiendo: las 10 «ia» y `success` en verdad;
      con el limite de Kinetix: todas «sin_texto», motivo «limite_kinetix»;
   3. los informes viejos: el texto de `FallbackAnalyzer` se reconoce, uno de IA no;
   4. la marca dice cuantas, cuando y por que.
B. `estado_ia.comprobar`: sin configuracion, limite de Kinetix y una clave
   inventada contra OpenAI (models.retrieve: no genera, no cuesta).
C. Contra el backend de PRUEBAS (8002, base jmeter_analyzer_test, sin clave):
   una subida `ZZTEST-F1` sale con todas las secciones «sin_texto», lo dicen
   `ai_status`, el historial, `/origen-ia` y la tabla; editar una seccion la
   marca como corregida; el integrado exportado lleva la marca en el HTML y en
   los metadatos del PDF. Al final se borra SOLO lo `ZZTEST-F1` (por la API).
"""
import asyncio
import io
import json
import os
import sys
import types

sys.path.insert(0, "/app")

import httpx
import openai

from app.services.ai import analysis_pipeline as AP
from app.services.ai import estado_ia, origen
from app.services.ai.gemini import FallbackAnalyzer, GeminiAnalyzer
from app.services.jtl.jtl_parser import JTLParser

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
BASE = os.environ.get("KX_DB", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
JTL = "/app/uploads/20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl"
MARCA = "ZZTEST-F1"

fallos = []


def ok(c, msg):
    print(("PASA  | " if c else "FALLA | ") + msg)
    if not c:
        fallos.append(msg)
    return c


# ---------------- un OpenAI falso ----------------
def _resp(code):
    return httpx.Response(code, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))


class _Completions:
    def __init__(self, modo):
        self.modo = modo

    def create(self, **kw):
        if self.modo == "clave":
            raise openai.AuthenticationError("Your API key has been invalidated.", response=_resp(401),
                                             body={"code": "token_invalidated", "message": "Your API key has been invalidated."})
        if self.modo == "cupo":
            raise openai.RateLimitError("You exceeded your current quota", response=_resp(429),
                                        body={"code": "insufficient_quota"})
        msg = types.SimpleNamespace(content="Texto de la IA de prueba: 8.600 muestras en el min 1:00.")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg, finish_reason="stop")], usage=None)


def analizador(modo):
    a = GeminiAnalyzer.__new__(GeminiAnalyzer)
    a.provider, a.model_name, a.reasoning_effort = "openai", "gpt-5.5", "low"
    a._openai_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions(modo)))
    GeminiAnalyzer._cerrar_circuito()
    GeminiAnalyzer._circuit_open = False
    return a


class _SinBase:
    async def execute(self, *a, **kw):
        raise RuntimeError("sin base")


async def parte_a():
    print("\n=== A1. El buzon de cada llamada ===")
    _, f = await origen.llamar(analizador("clave")._generate, "hola", section_name="prueba")
    ok(f.get("tipo") == "clave", f"401 -> clave ({f.get('tipo')})")
    ok("token_invalidated" in f.get("detalle", "") or "invalidated" in f.get("detalle", ""),
       "el literal del proveedor viaja con el fallo")
    _, f = await origen.llamar(analizador("cupo")._generate, "hola", section_name="prueba")
    ok(f.get("tipo") == "cupo", f"insufficient_quota -> cupo ({f.get('tipo')})")
    t, f = await origen.llamar(analizador("ia")._generate, "hola", section_name="prueba")
    ok(bool(t) and not f, "con respuesta, el buzon queda vacio")
    a_bien, a_mal = analizador("ia"), analizador("clave")
    (t1, f1), (t2, f2) = await asyncio.gather(
        origen.llamar(a_bien._generate, "x", section_name="bien"),
        origen.llamar(a_mal._generate, "x", section_name="mal"))
    ok(bool(t1) and not f1 and f2.get("tipo") == "clave", "dos llamadas en paralelo no se pisan el motivo")

    print("\n=== A2. El informe general entero ===")
    p = JTLParser(JTL)
    _, metrics = p.parse()
    crit = {"concurrency": 30, "response_time": 2000, "availability": 99.5}

    async def correr(modo, conf):
        async def _conf(db):
            return conf
        AP.load_ai_config_from_db = _conf
        AP.get_gemini_analyzer = lambda **kw: analizador(modo)
        return await AP.run_ai_and_verdict(p, metrics, "load", dict(crit), "TPS", _SinBase())

    conf = {"provider": "openai", "model_name": "gpt-5.5", "api_key": "x"}
    r = await correr("clave", conf)
    tipos = {v["origen"] for v in r.origenes.values()}
    ok(len(r.origenes) == 10 and tipos == {"respaldo"}, f"clave rechazada: 10 secciones de respaldo ({len(r.origenes)}, {tipos})")
    ok(all(v["motivo_tipo"] == "clave" for v in r.origenes.values()), "todas con motivo «clave»")
    ok(r.ai_status["success"] is False and r.ai_status["respaldo"] == 10, f"ai_status: success={r.ai_status['success']}, respaldo={r.ai_status.get('respaldo')}")
    ok("no las escribió la IA" in (r.ai_status.get("error") or ""), f"ai_status.error lo dice: «{(r.ai_status.get('error') or '')[:90]}…»")
    ok(r.ai_analysis_summary.startswith("La prueba proceso"), "y el texto guardado es el del respaldo")

    r = await correr("ia", conf)
    ok({v["origen"] for v in r.origenes.values()} == {"ia"} and r.ai_status["success"] is True,
       f"IA respondiendo: 10 «ia» y success=True ({r.ai_status['success']})")

    r = await correr("ia", {"limit_reached": "daily", "provider": "openai"})
    ok({v["origen"] for v in r.origenes.values()} == {"sin_texto"}
       and {v["motivo_tipo"] for v in r.origenes.values()} == {"limite_kinetix"},
       "limite de Kinetix: todas «sin_texto», motivo «limite_kinetix»")

    print("\n=== A3. Los informes de antes del registro ===")
    fb = FallbackAnalyzer()
    stats = {"avg_rt": 120, "min_rt": 10, "max_rt": 900, "p95": 400, "p99": 800, "throughput": 12.5,
             "total_requests": 1000, "total_errors": 20, "error_rate": 2.0, "duration": 600,
             "avg_latency": 100, "kb_received": 10, "kb_sent": 2, "num_transactions": 3}
    viejo = types.SimpleNamespace(
        ai_analysis_summary=fb.analyze_summary_table(p.get_summary_table_data(), None),
        ai_analysis_errors=fb.analyze_errors([{"label": "a", "count": 20, "code": "500"}], 1000),
        **{f"ai_analysis_{k}": fb.analyze_chart(k, stats) for k in
           ("response_times", "latency", "error_rate", "codes_per_second", "transactions_per_second", "active_threads")},
        ai_conclusions=fb.generate_conclusions(stats, acceptance_criteria=crit),
        ai_recommendations=fb.generate_recommendations(stats, acceptance_criteria=crit),
        created_at=None)
    det = origen.detectar_por_texto(viejo)
    ok(len(det) == 10 and all(det.values()), f"las 10 plantillas del respaldo se reconocen ({sum(det.values())}/{len(det)})")
    nuevo = types.SimpleNamespace(ai_analysis_summary="15.786 transacciones se ejecutaron durante 1.800 segundos.",
                                  ai_analysis_errors="Se registraron 1.307 fallos, casi todos en la consulta.")
    ok(not any(origen.detectar_por_texto(nuevo).values()), "un texto de la IA no se confunde con plantilla")

    print("\n=== A4. La marca ===")
    res = origen.resumen_de(types.SimpleNamespace(created_at=None), [
        types.SimpleNamespace(section=c, label="", origen="respaldo", provider="openai", model="gpt-5.5",
                              motivo_tipo="clave", motivo="gpt-5.5: Error code: 401 - token_invalidated",
                              generated_at=__import__("datetime").datetime(2026, 9, 26, 17, 22), edited_at=None)
        for c in origen.SECCIONES_GENERALES if c != "ai_analysis_redirects"])
    m = origen.marca(res)
    print(f"      {m}")
    ok("10 de 10 secciones NO las escribió la IA" in m, "dice cuantas")
    ok("2026-09-26 17:22" in m, "dice cuando")
    ok("la clave de la IA no sirve" in m and "token_invalidated" in m, "dice por que, con el literal")


def parte_b():
    print("\n=== B. /ai-config/estado, sin generar ===")
    r = estado_ia.comprobar({})
    ok(r["ok"] is False and r["motivo_tipo"] == "sin_configuracion", "sin configuracion -> lo dice")
    r = estado_ia.comprobar({"limit_reached": "daily", "provider": "openai", "model_name": "gpt-5.5"})
    ok(r["ok"] is False and r["motivo_tipo"] == "limite_kinetix", "limite de Kinetix -> lo dice")
    r = estado_ia.comprobar({"provider": "openai", "model_name": "gpt-5.5", "api_key": "sk-proj-ZZTEST-clave-inventada"}, forzar=True)
    ok(r["ok"] is False and r["motivo_tipo"] == "clave", f"clave inventada contra OpenAI -> «clave» ({r['motivo_tipo']}: {(r['detalle'] or '')[:70]})")
    r2 = estado_ia.comprobar({"provider": "openai", "model_name": "gpt-5.5", "api_key": "sk-proj-ZZTEST-clave-inventada"})
    ok(r2.get("cache") is True, "la segunda consulta sale de la cache (no vuelve a llamar)")
    ok("cupo agotado solo se ve al generar" in r["limite"], "y dice lo que no puede ver")


def parte_c():
    print("\n=== C. Contra el backend de pruebas ===")
    if "test" not in BASE:
        ok(False, f"KX_DB='{BASE}' no es la base de pruebas: parte C NO se corre")
        return
    ck = {c["name"]: c["value"] for c in json.load(open(SESION))["cookies"]}
    cli = httpx.Client(cookies=ck, headers={"X-CSRF-Token": ck.get("csrf_token", "")}, timeout=600)

    est = cli.get(f"{API}/ai-config/estado")
    ok(est.status_code == 200 and est.json()["ok"] is False, f"GET /ai-config/estado -> {est.status_code}, {est.json().get('motivo_tipo')}")

    with open(JTL, "rb") as fh:
        r = cli.post(f"{API}/upload", params={"name": MARCA, "test_type": "load", "metric_unit": "TPS",
                                             "description": "F1: prueba del aviso de respaldo"},
                     files={"files": (os.path.basename(JTL), fh, "text/csv")})
    if not ok(r.status_code == 200, f"POST /upload -> {r.status_code}"):
        print(r.text[:500])
        return
    d = r.json()
    eid, st = d["id"], d["ai_status"]
    ok(st["success"] is False and st.get("respaldo") == st.get("secciones") and st.get("secciones"),
       f"ai_status: success={st['success']}, {st.get('respaldo')} de {st.get('secciones')} sin IA, motivo={st.get('motivo_tipo')}")

    o = cli.get(f"{API}/executions/{eid}/origen-ia").json()
    ok(o["fuente"] == "registro" and o["afectadas"] == o["total"] > 0, f"/origen-ia: {o['afectadas']} de {o['total']}, fuente={o['fuente']}")
    ok(o["motivo_tipo"] == "sin_configuracion", f"motivo: {o['motivo_tipo']} — «{o['motivo_frase']}»")
    ok(o["marca"].startswith("Kinetix · origen del texto:"), f"marca: {o['marca'][:100]}…")

    lista = cli.get(f"{API}/executions").json()
    fila = next((x for x in lista if x["id"] == eid), None)
    ok(fila is not None and fila["ai_origen"]["afectadas"] == o["total"], f"el historial lo trae: {fila and fila['ai_origen']}")

    r = cli.put(f"{API}/executions/{eid}/analysis", json={"ai_analysis_summary": "ZZTEST-F1 corregido a mano."})
    o2 = cli.get(f"{API}/executions/{eid}/origen-ia").json()
    ok(r.status_code == 200 and o2["afectadas_sin_editar"] == o["afectadas_sin_editar"] - 1,
       f"editar una seccion la marca como corregida ({o['afectadas_sin_editar']} -> {o2['afectadas_sin_editar']})")
    r = cli.put(f"{API}/executions/{eid}/analysis", json={"ai_analysis_summary": "ZZTEST-F1 corregido a mano."})
    o3 = cli.get(f"{API}/executions/{eid}/origen-ia").json()
    ok(o3["afectadas_sin_editar"] == o2["afectadas_sin_editar"], "reenviar el mismo texto no cuenta como edicion")

    # El informe de una transaccion: sin IA no hay respaldo, la seccion queda
    # vacia, y cada una dice por que.
    label = cli.get(f"{API}/executions/{eid}/transaction-analyses").json()
    label = (label.get("transactions") or label.get("items") or [{}])[0].get("label") if isinstance(label, dict) else None
    label = label or JTLParser(JTL).parse()[0]["label"].iloc[0]
    g = cli.post(f"{API}/executions/{eid}/transaction-report", params={"label": label})
    tx = cli.get(f"{API}/executions/{eid}/transaction-report", params={"label": label}).json()
    orig = [s.get("origen") for s in tx.get("sections", [])]
    ok(g.status_code == 200 and len(orig) == 6 and all(o and o["origen"] == "sin_texto" for o in orig),
       f"transaccion «{label}»: las 6 secciones con su origen «sin_texto» ({g.status_code})")
    ok(all(o["motivo_tipo"] == "sin_configuracion" for o in orig if o), "y su motivo")
    o4 = cli.get(f"{API}/executions/{eid}/origen-ia").json()
    ok(o4["transacciones"].get(label, {}).get("afectadas") == 6, f"/origen-ia cuenta la transaccion: {o4['transacciones']}")

    # Los exportados INDIVIDUALES (las dos lineas autorizadas en los protegidos).
    import pypdfium2 as pdfium
    hi = cli.get(f"{API}/executions/{eid}/export/html")
    ok(hi.status_code == 200 and 'name="kinetix:origen"' in hi.text and "NO las escribió la IA" in hi.text,
       f"HTML individual: meta kinetix:origen ({hi.status_code})")
    ok("kinetix:origen" not in hi.text.split("</head>", 1)[-1], "y no se pinta en la pagina")
    pi = cli.get(f"{API}/executions/{eid}/export/pdf")
    mi = pdfium.PdfDocument(io.BytesIO(pi.content)).get_metadata_dict() if pi.status_code == 200 else {}
    ok("NO las escribió la IA" in (mi.get("Keywords", "") + mi.get("Subject", "")),
       f"PDF individual: en sus metadatos ({pi.status_code}; {(mi.get('Subject') or '')[:70]}…)")

    # El integrado exportado lleva la marca (HTML y metadatos del PDF).
    cuerpo = {"sections": [{"order": 0, "type": "load_test", "source_id": eid, "source_name": MARCA}],
              "unified_conclusions": ""}
    h = cli.post(f"{API}/reports/integrated/export-html", json=cuerpo)
    ok(h.status_code == 200 and 'name="kinetix:origen"' in h.text and "NO las escribió la IA" in h.text,
       f"HTML del integrado: meta kinetix:origen ({h.status_code})")
    ok("kinetix:origen" not in h.text.split("</head>", 1)[-1], "y no se pinta en la pagina (solo en <head>)")
    pdf = cli.post(f"{API}/reports/integrated/export-pdf", json=cuerpo)
    meta = {}
    if pdf.status_code == 200:
        import pypdfium2 as pdfium
        meta = pdfium.PdfDocument(io.BytesIO(pdf.content)).get_metadata_dict()
    ok("NO las escribió la IA" in (meta.get("Keywords", "") + meta.get("Subject", "")),
       f"PDF del integrado: en sus metadatos ({(meta.get('Subject') or '')[:80]}…)")

    # Limpieza: solo lo ZZTEST-F1, por la API (reglas 29 y 30).
    for x in cli.get(f"{API}/executions").json():
        if x["name"].startswith(MARCA):
            cli.delete(f"{API}/executions/{x['id']}")
    quedan = [x for x in cli.get(f"{API}/executions").json() if x["name"].startswith(MARCA)]
    ok(not quedan, "limpieza: no queda nada ZZTEST-F1")


async def main():
    await parte_a()
    parte_b()
    parte_c()
    print("\nF1 RESPALDO: TODO PASA" if not fallos else f"\nF1 RESPALDO: {len(fallos)} FALLA(N)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
