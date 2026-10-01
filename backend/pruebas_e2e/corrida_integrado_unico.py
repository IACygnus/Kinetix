"""BLOQUE 3.6 — la conclusion unica de un integrado REAL, con IA y SIN escribir.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/corrida_integrado_unico.py <report_id>

Lee el integrado en una conexion de SOLO LECTURA (`default_transaction_read_only`),
reune sus datos con el mismo codigo que el endpoint (`_reunir_conclusion_unica`),
llama UNA vez a la IA con `conclusion_unica.generar` y acaba en rollback. No llama
al endpoint: ese guarda.

Salida: /tmp/r2/integrado_unico.html — el consolidado de hoy (por tipo de
prueba) y el unico, lado a lado — y /tmp/r2/integrado_unico.json (cifras, prompt
y respuesta). LLEVA DATOS DE CLIENTES: se copia a C:\\proyectos\\Kinetix_pruebas\\r2\\.
"""
import asyncio
import html
import inspect
import json
import re
import sys
import time
import uuid

sys.path.insert(0, "/app")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models.integrated_report import IntegratedReport
from app.services.ai import gemini as G
from app.services.ai import conclusion_unica as CU
from app.services.ai.estilo import _NUMERO, detectar_estilo
import app.api.v1.endpoints.integrated_report as IR

TEL = []
_orig = G._emit_ai_telemetry
_firma = inspect.signature(_orig)


def _tel(*a, **kw):
    arg = _firma.bind(*a, **kw).arguments
    u = getattr(arg.get("response"), "usage", None)
    TEL.append({"outcome": arg.get("outcome"), "finish_reason": arg.get("finish_reason"),
                "entrada": getattr(u, "prompt_tokens", None), "salida": getattr(u, "completion_tokens", None),
                "razonamiento": getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", None)})
    return _orig(*a, **kw)


G._emit_ai_telemetry = _tel
VINETA = re.compile(r"^\s*(?:[•\-*]|\d{1,2}[.)])\s+", re.M)


def medir(texto):
    t = texto or ""
    return {"palabras": len(t.split()), "vinetas": len(VINETA.findall(t)),
            "cifras": len(_NUMERO.findall(VINETA.sub("", t))),
            "avisos_estilo": [a["tipo"] for a in detectar_estilo(t, "consolidated_conclusions")]}


async def main(rid):
    motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                                connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    async with async_sessionmaker(motor, class_=AsyncSession, autoflush=False)() as db:
        rep = await db.get(IntegratedReport, uuid.UUID(rid))
        nombre = rep.name
        hoy = json.loads(json.dumps(rep.consolidated_analysis or {}))
        secs = [IR.SectionInput(**{k: s.get(k) for k in ("order", "type", "source_id", "source_name", "seleccion")})
                for s in rep.sections if s.get("type") != "__meta"]
        overrides = await IR._load_section_overrides(db, rid)
        ejecuciones = await IR._reunir_conclusion_unica(db, secs, overrides)
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
    await motor.dispose()

    an = G.get_gemini_analyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                               reasoning_effort=conf.get("reasoning_effort") or "")
    t0 = time.time()
    try:
        res = await CU.generar(an, ejecuciones)
    except CU.ConclusionUnicaError as e:
        print(json.dumps({"RESPALDO": e.motivo, "detalle": e.detalle[:300], "telemetria": TEL}))
        return 3
    seg = round(time.time() - t0, 1)

    datos = {
        "integrado": rid, "segundos": seg, "telemetria": TEL,
        "ejecuciones": [{"tipo": e.tipo, "bloque_de_jtl": e.bloque_de_jtl, "es_prueba": e.tx_detalladas is not None,
                         "capturas": len(e.monitoreo), "evidencias": len(e.evidencias)} for e in ejecuciones],
        "hoy": {tt: {k: medir(d.get(k)) for k in ("conclusions", "recommendations")} | {"editado": d.get("edited")}
                for tt, d in hoy.items() if isinstance(d, dict) and not tt.startswith("_")},
        "unico": {k: medir(res[k]) for k in ("conclusions", "recommendations")},
        "prompt_caracteres": len(res["prompt"]),
    }
    json.dump({**datos, "prompt": res["prompt"], "respuesta": res, "consolidado_hoy": hoy},
              open("/tmp/r2/integrado_unico.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def caja(titulo, texto, extra=""):
        return (f"<div class='caja'><h4>{html.escape(titulo)}{extra}</h4>"
                f"{html.escape(texto or '').replace(chr(10), '<br>') or '<em>vacío</em>'}</div>")

    izq = []
    for tt, d in hoy.items():
        if not isinstance(d, dict) or tt.startswith("_"):
            continue
        rot = {"load": "Prueba de carga", "stress": "Prueba de estrés"}.get(tt, tt)
        marca = " · <span class='ed'>editado a mano</span>" if d.get("edited") else ""
        izq.append(caja(f"{rot} — Conclusiones", d.get("conclusions"), marca))
        izq.append(caja(f"{rot} — Recomendaciones", d.get("recommendations"), marca))
    der = [caja("Conclusiones", res["conclusions"]), caja("Recomendaciones", res["recommendations"])]

    def fila_cifras(et, f):
        return f"<tr><td>{et}</td>" + "".join(f"<td>{x}</td>" for x in f) + "</tr>"
    tabla = ["<table><tr><th>Caja</th><th>Viñetas</th><th>Palabras</th><th>Cifras</th></tr>"]
    for tt, d in datos["hoy"].items():
        for k, et in (("conclusions", "conclusiones"), ("recommendations", "recomendaciones")):
            m = d[k]
            tabla.append(fila_cifras(f"Hoy · {tt} · {et}", (m["vinetas"], m["palabras"], m["cifras"])))
    for k, et in (("conclusions", "conclusiones"), ("recommendations", "recomendaciones")):
        m = datos["unico"][k]
        tabla.append(fila_cifras(f"Única · {et}", (m["vinetas"], m["palabras"], m["cifras"])))
    tabla.append("</table>")
    t = TEL[-1] if TEL else {}
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Integrado: conclusión única</title>
<style>
:root{{--fondo:#f6f7fb;--papel:#fff;--tinta:#1d2433;--suave:#5b6477;--borde:#dfe3ec;--acento:#4f46e5}}
@media (prefers-color-scheme:dark){{:root{{--fondo:#12151c;--papel:#1b2029;--tinta:#e6e9f0;--suave:#9aa3b5;--borde:#2c3340;--acento:#8b85ff}}}}
body{{margin:0;background:var(--fondo);color:var(--tinta);font:15px/1.55 system-ui,Segoe UI,Roboto,sans-serif}}
main{{max-width:1400px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:24px;margin:0 0 6px}}
.nota{{color:var(--suave)}} .par{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.col h3{{margin:0 0 8px;color:var(--acento)}} .caja{{background:var(--papel);border:1px solid var(--borde);border-radius:10px;padding:12px 14px;margin-bottom:12px;overflow-wrap:anywhere}}
.caja h4{{margin:0 0 6px;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--suave)}}
.ed{{color:#b45309;text-transform:none}} table{{border-collapse:collapse;background:var(--papel);margin:12px 0}}
td,th{{border:1px solid var(--borde);padding:5px 10px;text-align:right}} td:first-child,th:first-child{{text-align:left}}
@media (max-width:760px){{.par{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>{html.escape(nombre)} — conclusión única</h1>
<p class="nota">Izquierda: el consolidado guardado hoy, uno por tipo de prueba (lo que pasaría a
«anterior», de solo lectura). Derecha: la conclusión única de la versión 3.4, generada ahora sin guardar nada.
Una llamada, {seg} s, {t.get('entrada')} tokens de entrada, {t.get('salida')} de salida
({t.get('razonamiento')} de razonamiento), finish_reason={t.get('finish_reason')}.
Ejecuciones: {html.escape(', '.join(f"{e['tipo']} (bloque {'del JTL' if e['bloque_de_jtl'] else 'de la base'}, {e['capturas']} capturas, {e['evidencias']} evidencias)" for e in datos['ejecuciones'] if e['es_prueba']))}.</p>
{''.join(tabla)}
<div class="par"><div class="col"><h3>Hoy (por tipo de prueba)</h3>{''.join(izq)}</div>
<div class="col"><h3>Única</h3>{''.join(der)}</div></div>
</main></body></html>"""
    open("/tmp/r2/integrado_unico.html", "w", encoding="utf-8").write(doc)
    print(json.dumps(datos, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1])))
