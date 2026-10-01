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


def main():
    parte_a()
    if os.environ.get("KX_PARTE_B") and "parte_b" in globals():
        globals()["parte_b"]()
    print()
    print("CONCLUSION UNICA: TODO PASA" if not FALLOS else f"CONCLUSION UNICA: {len(FALLOS)} FALLOS")
    return 0 if not FALLOS else 1


if __name__ == "__main__":
    sys.exit(main())
