"""
BLOQUE 3 (reporte 141) — la conclusion UNICA del informe integrado.

Hasta aqui el integrado tenia dos textos de IA: las «unificadas» (que no se
veian ni se guardaban) y el consolidado POR TIPO DE PRUEBA (con carga y estres,
cuatro cajas). Este modulo arma el prompt de UN solo analisis para todas las
ejecuciones del integrado y parte la respuesta en sus dos cajas.

Lo que recibe el prompt, por ejecucion (D4 de Fredy):
  - su BLOQUE DE LA EJECUCION, el mismo de su informe individual
    (`contexto_prompt.contexto_de_parser`): cifras globales, tabla por
    transaccion, criterios, fases y hechos. Si falta el JTL, las cifras de la
    base (`bloque_desde_base`);
  - su veredicto y las transacciones que el documento detalla (selector R1);
  - sus textos: conclusiones, recomendaciones y analisis de seccion, con las
    correcciones del analista delante;
  - sus capturas de infraestructura y sus evidencias, ya editadas.

Si la IA no responde o no devuelve los dos bloques, `generar` LANZA
`ConclusionUnicaError` con el motivo: el endpoint no guarda nada (D-b). Nunca
dos cajas vacias.

No toca la base ni la pantalla: recibe datos ya reunidos y devuelve texto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai import origen
from app.services.ai.estilo import ms, num, pct, percentiles_bloque

CLAVE = "unico"          # consolidated_analysis[CLAVE] = la caja unica
LEGADO = "_legado"       # el consolidado por tipo, tal cual, al regenerar (D2/D3)
SECCION = "consolidated_unico"

_TIPO = {"load": "prueba de carga", "stress": "prueba de estrés"}
_MARCA_CONC = re.compile(r"^\s*===\s*CONCLUSIONES(?:_CONSOLIDADAS)?\s*===\s*$", re.M | re.I)
_MARCA_RECO = re.compile(r"^\s*===\s*RECOMENDACIONES(?:_CONSOLIDADAS)?\s*===\s*$", re.M | re.I)


class ConclusionUnicaError(RuntimeError):
    """La IA no dio un texto utilizable. `motivo` es legible para la pantalla."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalle = detalle


@dataclass
class Ejecucion:
    """Lo que el prompt necesita de UNA ejecucion del integrado."""
    nombre: str
    tipo: str = "load"                      # load / stress
    bloque: str = ""                        # bloque de la ejecucion (JTL) o cifras de la base
    bloque_de_jtl: bool = False
    veredicto: str = ""
    tx_detalladas: Optional[List[str]] = None   # None = no es una seccion de prueba
    conclusiones: str = ""
    recomendaciones: str = ""
    secciones: str = ""                     # `_section_analyses_for_prompt`
    monitoreo: List[str] = field(default_factory=list)
    evidencias: List[str] = field(default_factory=list)


def bloque_desde_base(execution) -> str:
    """Respaldo de D4: sin JTL, las cifras que guarda la base (las de antes)."""
    return (
        "CIFRAS DE LA EJECUCION (de la base: el JTL de esta ejecucion ya no esta)\n"
        f"- Peticiones: {num(execution.total_requests)}, tasa de error: {pct(execution.error_rate)}\n"
        f"- Tiempo promedio de respuesta: {ms(execution.avg_response_time)}; "
        f"latencia promedio: {ms(execution.avg_latency or 0)}\n"
        f"- Caudal: {num(execution.throughput, 2)} por segundo; "
        f"duracion: {num(execution.duration_seconds or 0)} segundos\n"
        "- Percentiles (dato de apoyo): "
        + percentiles_bloque(p90=execution.p90_response_time, p95=execution.p95_response_time,
                             p99=execution.p99_response_time).replace("\n", "; "))


def armar_prompt(ejecuciones: List[Ejecucion]) -> str:
    """El prompt unico. Lo comun a todas (los datos) delante; la instruccion, al final."""
    pruebas = [e for e in ejecuciones if e.tx_detalladas is not None]
    nombres = ", ".join(f"«{e.nombre}» ({_TIPO.get(e.tipo, e.tipo)})" for e in pruebas) or "ninguna"
    partes = [
        "CONCLUSIONES Y RECOMENDACIONES DEL INFORME INTEGRADO",
        f"Este informe junta {num(len(pruebas))} ejecucion(es) del mismo sistema: {nombres}.",
    ]
    for i, e in enumerate(ejecuciones, 1):
        cab = f"=== EJECUCION {i}: «{e.nombre}» ({_TIPO.get(e.tipo, e.tipo)}) ==="
        bloque = [cab]
        if e.bloque:
            bloque.append(e.bloque.strip())
        if e.veredicto:
            bloque.append(f"RESULTADO FRENTE A LOS CRITERIOS: {e.veredicto}")
        if e.conclusiones or e.recomendaciones or e.secciones:
            bloque.append("LO QUE YA DICE SU INFORME (los textos marcados CORREGIDO POR EL USUARIO son "
                          "correcciones del analista: tienen prioridad sobre cualquier otro texto y sobre "
                          "tu propio criterio; los demas van recortados y solo dan contexto):")
            if e.conclusiones:
                bloque.append(f"Sus conclusiones:\n{e.conclusiones.strip()}")
            if e.recomendaciones:
                bloque.append(f"Sus recomendaciones:\n{e.recomendaciones.strip()}")
            if e.secciones:
                bloque.append(f"Sus secciones:\n{e.secciones.strip()}")
        if e.monitoreo:
            bloque.append("INFRAESTRUCTURA (capturas de monitoreo de esta ejecucion):\n" + "\n".join(e.monitoreo))
        if e.evidencias:
            bloque.append("EVIDENCIAS de esta ejecucion:\n" + "\n".join(e.evidencias))
        partes.append("\n\n".join(bloque))

    # R1 (Fredy, pregunta 3): el mismo formato que leen las suites de R1.
    tx = "\n".join(f"- {e.nombre}: " + (", ".join(e.tx_detalladas) if e.tx_detalladas
                                        else "ninguna (solo el informe general)")
                   for e in pruebas)
    partes.append(
        "INFORMES POR TRANSACCION QUE INCLUYE EL DOCUMENTO (el lector solo encontrara detalle propio de "
        "estas; de las demas, solo su fila en la tabla general. No remitas a un informe por transaccion "
        f"que no este en esta lista):\n{tx or 'Ninguno.'}")
    partes.append(INSTRUCCION)
    return "\n\n".join(partes)


INSTRUCCION = """SECCION: CONCLUSIONES Y RECOMENDACIONES DEL INFORME INTEGRADO

Escribe las conclusiones y recomendaciones del informe integrado siguiendo la guia de
estilo. Es UN solo analisis para todas las pruebas («Tanto en la prueba de carga como
en la de estres…»), nunca un bloque por ejecucion. La infraestructura y las evidencias
van dentro de las vinetas que toquen, no en un bloque aparte.

Responde con dos bloques, con estos encabezados EXACTOS, cada uno en su propia linea:
===CONCLUSIONES===
de 4 a 7 vinetas, cada una en su propia linea y empezando por «• »: un hallazgo con su
porque, cruzando las pruebas con la infraestructura y las evidencias cuando aporten;
la ultima vineta, el dictamen de viabilidad, explicado con su razon.
===RECOMENDACIONES===
de 4 a 7 vinetas, cada una en su propia linea y empezando por «• »: cada una ligada a
un hallazgo concreto de estas pruebas (que transaccion, que error, que componente) y
accionable. Nada generico que valga para cualquier prueba.

Sin repetir las cifras de las secciones, sin titulos aparte, sin parrafo de
introduccion y sin numerar."""


def partir(raw: str) -> Tuple[str, str]:
    """(conclusiones, recomendaciones). Lanza si no estan los dos bloques con texto:
    antes se partia «por la mitad» y un texto vacio daba dos cajas vacias (D-b)."""
    from app.services.ai.gemini import sanitize_ai_text
    texto = raw or ""
    mc, mr = _MARCA_CONC.search(texto), _MARCA_RECO.search(texto)
    if not mc or not mr or mr.start() < mc.end():
        raise ConclusionUnicaError(
            "la IA no devolvio los dos bloques (conclusiones y recomendaciones)",
            texto[:300])
    conc = sanitize_ai_text(texto[mc.end():mr.start()].strip())
    reco = sanitize_ai_text(texto[mr.end():].strip())
    if not conc or not reco:
        raise ConclusionUnicaError("la IA devolvio un bloque vacio", texto[:300])
    return conc, reco


async def generar(analizador, ejecuciones: List[Ejecucion]) -> Dict[str, Any]:
    """Llama a la IA y devuelve {conclusions, recommendations, prompt}. Lanza
    `ConclusionUnicaError` si no hay texto: quien llama no guarda nada."""
    if not any(e.tx_detalladas is not None for e in ejecuciones):
        raise ConclusionUnicaError("el integrado no tiene ninguna ejecucion de carga o de estres")
    prompt = armar_prompt(ejecuciones)
    raw, fallo = await origen.llamar(analizador._generate, prompt, section_name=SECCION,
                                     permite_veredicto=True)
    if not raw:
        tipo = (fallo or {}).get("tipo") or "error"
        raise ConclusionUnicaError(
            f"la IA no respondio: {origen.MOTIVOS.get(tipo, tipo)}", (fallo or {}).get("detalle", ""))
    conc, reco = partir(raw)
    return {"conclusions": conc, "recommendations": reco, "prompt": prompt}
