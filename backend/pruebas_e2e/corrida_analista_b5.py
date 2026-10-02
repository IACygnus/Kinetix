"""BLOQUE 5, punto 15 — una conversación guionizada de 3 turnos con IA REAL.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/corrida_analista_b5.py
    docker cp jmeter_backend:/tmp/b5_corrida/. C:\\proyectos\\Kinetix_pruebas\\r2\\
    (con --solo-html rehace la página desde el JSON guardado, sin llamar a la IA)

**No escribe en ninguna base** (memoria «comparar informes sin escribir»): la
configuración de IA se lee con una conexión de SOLO LECTURA a la base de Fredy
y se hace rollback; el JTL de «prueba 6» se lee del disco; la sesión, la ficha
y los mensajes viven en memoria y se guardan a JSON y HTML en /tmp/b5_corrida.
Tampoco toca los contadores de uso de la IA (`update_ai_usage_in_db` escribe).

Llamadas: 4 (el primer mensaje y tres turnos). No se genera el informe.
"""
import asyncio
import html
import json
import os
import sys
import time

sys.path.insert(0, "/app")
from sqlalchemy import text   # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine   # noqa: E402

from app.core.config import settings   # noqa: E402
from app.services.ai import gemini as G, origen   # noqa: E402
from app.services.ai.contexto_prompt import contexto_de_parser   # noqa: E402
from app.api.v1.endpoints.upload import parsear_archivos   # noqa: E402
from app.services.analista import chat as CH, ficha as FI, prompt as PA   # noqa: E402

EJECUCION = "b81d713b-af2f-445c-ab87-663149f644b4"     # «prueba 6», load (solo para encontrar su JTL)
SALIDA = "/tmp/b5_corrida"
TURNOS = [
    "Con el cliente se acordó que el 90 % de las peticiones responda en menos de 1 segundo y una "
    "disponibilidad del 99 %. Además, ninguna transacción debería pasar del 5 % de errores.",
    "Era una ronda corta: 5 minutos con 5 usuarios, solo para validar el script antes de la prueba larga. "
    "Corrió en el ambiente de QA.",
    "Desarrollo confirmó que los errores de Put_Update_Booking y Delete_Booking_Id son un fallo de "
    "autenticación del servicio de reservas: esas dos peticiones no envían el token. Ya lo están corrigiendo.",
]
TEL = []


async def leer_config_y_jtl():
    motor = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                                connect_args={"server_settings": {"default_transaction_read_only": "on"}})
    async with async_sessionmaker(motor, class_=AsyncSession, autoflush=False)() as db:
        fila = (await db.execute(text("select jtl_filename, test_type, metric_unit from test_executions "
                                      "where id=:i"), {"i": EJECUCION})).one()
        conf = await G.load_ai_config_from_db(db)
        await db.rollback()
    await motor.dispose()
    jtl = next(f for f in sorted(os.listdir("/app/uploads")) if f.endswith(fila[0]))
    return conf, os.path.join("/app/uploads", jtl), fila[0], fila[1], fila[2] or "TPS"


async def main():
    conf, ruta, nombre, tipo, unidad = await leer_config_y_jtl()
    an = G.get_gemini_analyzer(provider=conf["provider"], model_name=conf["model_name"], api_key=conf["api_key"],
                               reasoning_effort=conf.get("reasoning_effort") or "")

    async def llamar(prompt, sistema, sanear):
        t0 = time.time()
        texto, fallo = await origen.llamar(an._generate, prompt, section_name="analista_chat", max_retries=2,
                                           sistema=sistema, sanear=sanear)
        TEL.append({"segundos": round(time.time() - t0, 1), "prompt": len(prompt), "ok": bool(texto),
                    "fallo": (fallo or {}).get("tipo")})
        return (texto, "") if texto else (None, origen.MOTIVOS.get((fallo or {}).get("tipo") or "error", "error"))

    _df, metrics, parser = parsear_archivos([ruta], [nombre])
    ficha = FI.construir(parser, metrics, cliente="(prueba 6)", cliente_id=None, proyecto="prueba 6",
                         tipo=tipo, unidad=unidad, jtl=[nombre])
    bloque = contexto_de_parser(parser, tipo, unidad, {"analista": {"estado_criterios": "sin_declarar"}}, metrics)[0]
    FI.recalcular(ficha)
    df = parser.df_main
    mensajes = [await CH.primer_mensaje(ficha, bloque, llamar)]
    listos = [dict(ficha["listo"])]
    for texto in TURNOS:
        mensajes = mensajes + [CH.mensaje("analista", texto, mensajes)]
        ficha, mensajes, bien = await CH.turno(ficha, mensajes, texto, bloque, llamar, lambda: df)
        listos.append(dict(ficha["listo"]))
        print(f"turno: {'ok' if bien else 'FALLO'} · listo {ficha['listo']['n']} de {ficha['listo']['m']}")

    crit = PA.criterios_para_generar(ficha, [], None)
    secciones = "\n\n".join(s for s in (PA.seccion_criterios(crit["analista"]), PA.seccion_relato(crit["analista"]),
                                        PA.seccion_errores(crit["analista"])) if s)
    datos = {"modelo": f"{conf['provider']} {conf['model_name']} ({conf.get('reasoning_effort') or 'low'})",
             "jtl": nombre, "telemetria": TEL, "mensajes": mensajes, "listo_por_turno": listos,
             "ficha": {k: v for k, v in ficha.items() if not k.startswith("_")},
             "motor": {k: v for k, v in crit.items() if k != "analista"}, "secciones_para_prompts": secciones,
             "preguntas_de_la_ia": CH.preguntas_hechas(mensajes)}
    os.makedirs(SALIDA, exist_ok=True)
    json.dump(datos, open(f"{SALIDA}/conversacion_analista.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=str)
    open(f"{SALIDA}/conversacion_analista.html", "w", encoding="utf-8").write(pagina(datos))
    print(json.dumps({"llamadas": len(TEL), "segundos": sum(t["segundos"] for t in TEL), "telemetria": TEL,
                      "preguntas": datos["preguntas_de_la_ia"]}, ensure_ascii=False))


# ------------------------------------------------------------------ la página

E = html.escape
COLOR = {"cumple": "#15803d", "no_cumple": "#b91c1c", "no_evaluado": "#6b7280", "lo_confirma_el_analista": "#b45309"}
NOMBRE = {"cumple": "Cumple", "no_cumple": "No cumple", "no_evaluado": "No evaluado",
          "lo_confirma_el_analista": "Lo confirma el analista"}


def pagina(d):
    f = d["ficha"]
    chat = "".join(
        f'<div class="m {m["rol"]}"><div class="q">{"IA" if m["rol"] == "ia" else "Analista"}'
        f'{" · " + E(m["origen"]) if m.get("origen") and m["origen"] != "ia" else ""}</div>'
        f'<div class="t">{E(m["texto"]).replace(chr(10), "<br>")}</div>'
        + (f'<div class="c">Cambios en la ficha: {E(json.dumps(m["cambios"], ensure_ascii=False))}</div>'
           if m.get("cambios") else "")
        + "".join(f'<div class="c aviso">{E(a)}</div>' for a in m.get("avisos") or [])
        + "</div>" for m in d["mensajes"])
    filas = "".join(
        f'<tr><td>{E(c["texto"])}</td><td>{E(c["tipo"])}<br><small>{E(str(c.get("metrica") or ""))} '
        f'{E(str(c.get("operador") or ""))} {E(str(c.get("valor") if c.get("valor") is not None else ""))} '
        f'{E(str(c.get("unidad") or ""))}</small></td>'
        f'<td>{E((c["alcance"] or {}).get("transaccion") or ("cada transacción" if (c["alcance"] or {}).get("tipo") == "cada_transaccion" else "toda la prueba"))}</td>'
        f'<td><b style="color:{COLOR.get(c["resultado"]["estado"], "#000")}">{NOMBRE.get(c["resultado"]["estado"])}</b>'
        f'<br><small>{E(c["resultado"].get("texto") or c["resultado"].get("motivo") or "")}</small>'
        f'{"<br><small>" + E(c["resultado"]["nota"]) + "</small>" if c["resultado"].get("nota") else ""}</td>'
        f'<td>{"sí" if c["en_motor"] else "no"}</td></tr>' for c in f["criterios"]["lista"])
    relato = "".join(f"<li>{E(r['texto'])}</li>" for r in f["relato"]) or "<li><i>(nada)</i></li>"
    pend = "".join(f'<li>{"●" if p["obligatorio"] else "○"} {E(p["pregunta"])} — <b>{E(p["estado"])}</b>'
                   f'{" (" + E(p["respuesta"]) + ")" if p.get("respuesta") else ""}</li>' for p in f["pendientes"])
    tx = "".join(f'<tr><td>{E(t["label"])}</td><td>{t["errores"]}</td><td>{E(t.get("verdict") or "—")}</td>'
                 f'<td>{"sí" if t["critica"] else ""}</td><td>{"✔" if t["informe"] else ""}</td></tr>'
                 for t in f["transacciones"])
    l = f["listo"]
    tel = " · ".join(f'{t["segundos"]} s' for t in d["telemetria"])
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analista IA — conversación</title><style>
body{{font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:#f4f5f7;color:#111}}
header{{background:#0a1628;color:#fff;padding:14px 24px}} header small{{opacity:.75}}
main{{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,6fr);gap:16px;padding:16px 24px}}
section{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px #0002}}
h2{{font-size:15px;margin:0 0 10px}} h3{{font-size:13px;margin:16px 0 6px;color:#4f46e5}}
.m{{margin:0 0 12px;padding:10px 12px;border-radius:10px;max-width:92%}} .m.ia{{background:#eef2ff}}
.m.analista{{background:#f1f5f9;margin-left:auto}} .q{{font-size:11px;color:#6b7280;margin-bottom:4px}}
.c{{font-size:11px;color:#4b5563;margin-top:6px}} .aviso{{color:#b45309}}
table{{border-collapse:collapse;width:100%;font-size:12px}} td,th{{border-bottom:1px solid #e5e7eb;padding:5px;text-align:left;vertical-align:top}}
.listo{{font-size:18px;font-weight:600}} pre{{white-space:pre-wrap;font-size:11px;background:#f8fafc;padding:10px;border-radius:6px}}
@media(max-width:900px){{main{{grid-template-columns:1fr}}}}</style></head><body>
<header><b>Analista IA</b> — conversación guionizada de 3 turnos sobre «{E(d["jtl"])}»<br>
<small>{E(d["modelo"])} · {len(d["telemetria"])} llamadas ({tel}) · preguntas de la IA: {d["preguntas_de_la_ia"]} · nada se escribió en la base</small></header>
<main><section><h2>Chat</h2>{chat}</section>
<section><h2>Ficha del informe</h2>
<div class="listo">Listo para generar: {l["n"]} de {l["m"]}</div>
<small>obligatorios {l["obligatorios"]["listos"]} de {l["obligatorios"]["total"]} · opcionales {l["opcionales"]["listos"]} de {l["opcionales"]["total"]} · {"se puede generar" if l["puede_generar"] else "faltan: " + ", ".join(l["faltan"])}</small>
<h3>Criterios de aceptación ({E(f["criterios"]["estado"])}) — el resultado lo calcula el servidor</h3>
<table><tr><th>Lo que dijo</th><th>Tipo</th><th>Alcance</th><th>Resultado</th><th>Motor</th></tr>{filas}</table>
<h3>Lo que contaste</h3><ul>{relato}</ul>
<p><b>Ambiente:</b> {E(f["contexto"].get("ambiente") or "—")} · <b>Versión:</b> {E(f["contexto"].get("version") or "—")}</p>
<h3>Pendientes</h3><ul>{pend}</ul>
<h3>Transacciones (✔ = informe propio)</h3><table><tr><th>Transacción</th><th>Errores</th><th>Veredicto</th><th>Crítica</th><th>Informe</th></tr>{tx}</table>
<h3>Cifras del JTL</h3><p>{f["cifras"]["peticiones"]} peticiones · {f["cifras"]["errores"]} errores ({f["cifras"]["tasa_error"]:.2f} %) · P90 {f["cifras"]["p90_ms"]:.0f} ms · {E(f["fases"]["texto"])}</p>
<h3>Lo que llegaría a los 16 prompts del informe</h3><pre>{E(d["secciones_para_prompts"])}</pre>
<h3>Claves del motor</h3><pre>{E(json.dumps(d["motor"], ensure_ascii=False, indent=1))}</pre>
</section></main></body></html>"""


if __name__ == "__main__":
    if "--solo-html" in sys.argv:   # rehacer la página desde el JSON, sin llamar a la IA
        d = json.load(open(f"{SALIDA}/conversacion_analista.json", encoding="utf-8"))
        open(f"{SALIDA}/conversacion_analista.html", "w", encoding="utf-8").write(pagina(d))
    else:
        asyncio.run(main())
