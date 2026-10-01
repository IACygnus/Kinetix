"""BLOQUE 3 (3.2-3.4) — la conclusion unica del integrado, sin IA.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/conclusion_unica.py

Parte A (sin base): el modulo `services/ai/conclusion_unica.py`.
  - el prompt junta todas las ejecuciones en UN analisis, con su bloque, sus
    textos, su infraestructura y sus evidencias, y la instruccion de la guia;
  - la respuesta se parte en dos cajas por los marcadores (nuevos y viejos);
  - si la IA no responde, no devuelve los dos bloques o devuelve uno vacio:
    error con motivo, nunca dos cajas vacias (D-b).
Parte B (base de PRUEBAS y endpoint en proceso, 3.3/3.4) se anade en su paso.
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app")

from app.services.ai import conclusion_unica as CU   # noqa: E402

FALLOS = []


def ok(c, m):
    print(("  ok   " if c else "  FALLA ") + m)
    if not c:
        FALLOS.append(m)
    return c


class Stub:
    def __init__(self, respuesta):
        self.respuesta, self.prompts, self.kw = respuesta, [], []

    def _generate(self, prompt, **kw):
        self.prompts.append(prompt)
        self.kw.append(kw)
        return self.respuesta


def parte_a():
    print("A. El modulo")
    ej = [CU.Ejecucion(nombre="ZZTEST carga", tipo="load", bloque="DATOS DE LA EJECUCION\nZZTEST-BLOQUE-1",
                       veredicto="NO APTO", tx_detalladas=["1. Auth"], conclusiones="ZZTEST-CONC-1",
                       recomendaciones="ZZTEST-RECO-1", secciones="[Resumen general] ZZTEST-SEC-1",
                       monitoreo=["[cpu: CPU] ZZTEST-MON-1"], evidencias=["[log: L] ZZTEST-EVI-1"]),
          CU.Ejecucion(nombre="ZZTEST estres", tipo="stress", bloque="ZZTEST-BLOQUE-2",
                       tx_detalladas=[], conclusiones="ZZTEST-CONC-2")]
    p = CU.armar_prompt(ej)
    for marca in ("ZZTEST-BLOQUE-1", "ZZTEST-BLOQUE-2", "ZZTEST-CONC-1", "ZZTEST-CONC-2", "ZZTEST-RECO-1",
                  "ZZTEST-SEC-1", "ZZTEST-MON-1", "ZZTEST-EVI-1", "NO APTO"):
        ok(marca in p, f"el prompt lleva {marca}")
    ok(p.index("ZZTEST-BLOQUE-1") < p.index("ZZTEST-BLOQUE-2") < p.index("SECCION: CONCLUSIONES"),
       "los datos de cada ejecucion delante, la instruccion al final")
    ok("- ZZTEST carga: 1. Auth" in p and "- ZZTEST estres: ninguna (solo el informe general)" in p,
       "dice que transacciones detalla el documento (formato de R1)")
    for frase in ("UN solo analisis para todas las pruebas", "de 4 a 7 vinetas", "dictamen de viabilidad",
                  "no en un bloque aparte", "Sin repetir las cifras", "===CONCLUSIONES===", "===RECOMENDACIONES==="):
        ok(frase in p, f"la instruccion pide: {frase}")
    ok("PRUEBA DE CARGA" not in p.split("SECCION:")[1], "no pide un bloque por tipo de prueba")

    bien = "===CONCLUSIONES===\n- uno\n- dos\n===RECOMENDACIONES===\n• tres\n• cuatro"
    c, r = CU.partir(bien)
    ok(c == "• uno\n• dos" and r == "• tres\n• cuatro", "se parte en dos cajas y las vinetas quedan con «•»")
    c, r = CU.partir("===CONCLUSIONES_CONSOLIDADAS===\nA.\n===RECOMENDACIONES_CONSOLIDADAS===\nB.")
    ok((c, r) == ("A.", "B."), "acepta tambien los marcadores viejos")
    for nombre, raw in (("sin marcadores", "texto suelto que antes se partia por la mitad"),
                        ("un bloque vacio", "===CONCLUSIONES===\n• a\n===RECOMENDACIONES===\n  "),
                        ("al reves", "===RECOMENDACIONES===\n• a\n===CONCLUSIONES===\n• b"),
                        ("vacio", "")):
        try:
            CU.partir(raw)
            ok(False, f"{nombre}: deberia fallar")
        except CU.ConclusionUnicaError as e:
            ok(bool(e.motivo), f"{nombre}: error con motivo («{e.motivo}»)")

    s = Stub(bien)
    res = asyncio.run(CU.generar(s, ej))
    ok(res["conclusions"].startswith("• uno") and len(s.prompts) == 1, "generar: una sola llamada, dos cajas")
    ok(s.kw[0].get("permite_veredicto") is True, "generar: con permiso de dictamen")
    for nombre, stub in (("la IA no responde", Stub(None)), ("la IA da texto sin bloques", Stub("hola"))):
        try:
            asyncio.run(CU.generar(stub, ej))
            ok(False, f"{nombre}: deberia fallar")
        except CU.ConclusionUnicaError as e:
            ok(True, f"{nombre}: ConclusionUnicaError («{e.motivo}»)")
    try:
        asyncio.run(CU.generar(Stub(bien), [CU.Ejecucion(nombre="solo capturas")]))
        ok(False, "sin ejecuciones de prueba: deberia fallar")
    except CU.ConclusionUnicaError:
        ok(True, "sin ejecuciones de carga ni estres: error, no se llama a la IA")


def parte_b():
    """3.3/3.4, en proceso contra la base de PRUEBAS (regla 34). Toca solo el
    integrado «ZZTEST-R1 integrado» y deja su consolidado como estaba."""
    import json
    import uuid as _uuid
    from fastapi import HTTPException
    from sqlalchemy import select, text
    import app.services.ai.gemini as G
    from app.db.session import AsyncSessionLocal
    from app.db.models.user import User
    from app.db.models.integrated_report import IntegratedReport
    import app.api.v1.endpoints.integrated_report as IR

    print("B. El endpoint, contra la base de pruebas")
    respuesta = {"texto": "===CONCLUSIONES===\n• ZZTEST conclusion unica.\n===RECOMENDACIONES===\n• ZZTEST recomendacion unica."}
    prompts = []

    class SinIA:
        def _generate(self, prompt, **kw):
            prompts.append(prompt)
            return respuesta["texto"]
    G.get_gemini_analyzer = lambda **kw: SinIA()
    IR.get_gemini_analyzer = G.get_gemini_analyzer

    async def correr():
        async with AsyncSessionLocal() as db:
            base = (await db.execute(text("select current_database()"))).scalar()
            if "test" not in base:
                sys.exit(f"PARADA: '{base}' no es la base de pruebas")
            rep = (await db.execute(select(IntegratedReport).where(
                IntegratedReport.name == "ZZTEST-R1 integrado"))).scalars().first()
            rid = str(rep.id)
            original = json.loads(json.dumps(rep.consolidated_analysis or {}))
            u = (await db.execute(select(User).where(User.username == "admin"))).scalars().first()
            secs = [IR.SectionInput(**{k: s.get(k) for k in ("order", "type", "source_id", "source_name", "seleccion")})
                    for s in rep.sections]

            async def leer():
                await db.commit()
                r = await db.get(IntegratedReport, _uuid.UUID(rid))
                await db.refresh(r)
                return json.loads(json.dumps(r.consolidated_analysis or {}))

            try:
                # Punto de partida conocido: un consolidado por tipo, como los de antes.
                r = await db.get(IntegratedReport, _uuid.UUID(rid))
                r.consolidated_analysis = {"load": {"conclusions": "ZZTEST conclusiones de carga.",
                                                    "recommendations": "ZZTEST recomendaciones de carga.",
                                                    "generated_at": None, "edited": True}}
                await db.commit()

                out = await IR.generate_consolidated_analysis(
                    IR.ConsolidatedRequest(sections=secs, report_id=rid), db=db, current_user=u)
                ca = await leer()
                ok(len(prompts) == 1, f"una sola llamada a la IA para todo el integrado ({len(prompts)})")
                p = prompts[-1]
                ok(p.count("=== EJECUCION") == 2, "el prompt junta las dos ejecuciones (carga y estres)")
                ok("DATOS DE LA EJECUCION" in p or "CIFRAS DE LA EJECUCION (de la base" in p,
                   "cada ejecucion lleva su bloque (del JTL o, sin JTL, de la base)")
                ok("INFRAESTRUCTURA (capturas de monitoreo de esta ejecucion)" in p,
                   "las capturas van atadas a su ejecucion")
                ok(set(ca) == {"unico", "_legado"}, f"en la base: unico + _legado ({sorted(ca)})")
                ok(ca["unico"]["conclusions"] == "• ZZTEST conclusion unica." and ca["unico"]["edited"] is False,
                   "la caja unica guardada")
                ok(ca["_legado"].get("load", {}).get("conclusions") == "ZZTEST conclusiones de carga."
                   and ca["_legado"]["load"].get("edited") is True,
                   "el consolidado por tipo, entero y con su edicion, en _legado (D2/D3)")
                ok("_legado" not in out["consolidated_analysis"], "la respuesta a la pantalla no lleva el legado")

                # La IA falla: error y nada guardado.
                antes = await leer()
                for nombre, texto in (("no responde", None), ("sin bloques", "texto suelto")):
                    respuesta["texto"] = texto
                    try:
                        await IR.generate_consolidated_analysis(
                            IR.ConsolidatedRequest(sections=secs, report_id=rid), db=db, current_user=u)
                        ok(False, f"la IA {nombre}: deberia dar error")
                    except HTTPException as e:
                        ok(e.status_code == 502 and "No se guardo nada" in e.detail,
                           f"la IA {nombre}: {e.status_code} «{e.detail[:70]}…»")
                    ok(await leer() == antes, f"la IA {nombre}: la base no cambia")

                # Regenerar otra vez: el legado se conserva.
                respuesta["texto"] = "===CONCLUSIONES===\n• ZZTEST dos.\n===RECOMENDACIONES===\n• ZZTEST dos r."
                await IR.generate_consolidated_analysis(
                    IR.ConsolidatedRequest(sections=secs, report_id=rid), db=db, current_user=u)
                ca = await leer()
                ok(ca["unico"]["conclusions"] == "• ZZTEST dos." and "load" in ca["_legado"],
                   "regenerar: la caja unica cambia y el legado sigue")

                # GET y PATCH
                g = await IR.get_integrated_report(rid, db=db, current_user=u)
                ok("_legado" not in g["consolidated_analysis"] and (g["consolidado_anterior"] or {}).get("load"),
                   "GET: el legado aparte, en consolidado_anterior")
                await IR.update_integrated_report(rid, {"consolidated_analysis": {
                    "unico": {**ca["unico"], "conclusions": "• ZZTEST editada.", "edited": True}}},
                    db=db, current_user=u)
                ca = await leer()
                ok(ca["unico"]["conclusions"] == "• ZZTEST editada." and "load" in ca.get("_legado", {}),
                   "PATCH: guarda la edicion y conserva el legado que la pantalla no manda")
                plano = IR._flatten_consolidated(ca)
                ok(plano.startswith("Conclusiones:\n• ZZTEST editada.") and "PRUEBA DE" not in plano,
                   "lo que exportan PDF y HTML: una sola caja, sin rotulo por tipo")
                ok(IR._flatten_consolidated({"load": {"conclusions": "a", "recommendations": "b"}})
                   .startswith("PRUEBA DE CARGA"), "un integrado no regenerado se aplana como siempre (D3)")
                if hasattr(IR, "_texto_conclusiones_para_exportar"):
                    req = IR.IntegratedReportRequest(sections=secs, unified_conclusions="TEXTO QUE NO SE VE",
                                                     report_id=rid)
                    t = await IR._resolve_unified_conclusions(db, req)
                    ok(t == plano, "D-a: la exportacion lee lo guardado, no el texto que manda la pantalla")
            finally:
                r = await db.get(IntegratedReport, _uuid.UUID(rid))
                r.consolidated_analysis = original
                await db.commit()
                ok(await leer() == original, "el consolidado del integrado ZZTEST, como estaba")

    asyncio.run(correr())


def main():
    parte_a()
    if os.environ.get("KX_PARTE_B") and "parte_b" in globals():
        globals()["parte_b"]()
    print()
    print("CONCLUSION UNICA: TODO PASA" if not FALLOS else f"CONCLUSION UNICA: {len(FALLOS)} FALLOS")
    return 0 if not FALLOS else 1


if __name__ == "__main__":
    sys.exit(main())
