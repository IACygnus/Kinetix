"""
N4.6 — Generacion IA del mini-informe de UNA transaccion, bajo demanda.

ETAPA 2 (D20): SEIS secciones (SECTIONS_GENERADAS) — resumen y las 5 graficas.
Eran ocho: las conclusiones y recomendaciones por transaccion se retiraron
(v1.2 §1.1), porque van una sola vez al final del informe. Las filas antiguas de
esas dos secciones se conservan en base; solo se dejan de generar y de pintar.

Vive FUERA de /upload a proposito: son 6 llamadas en serie que solo tienen
sentido para las transacciones que se decide abrir, no para cada carga de JTL.

Decisiones de este modulo:
  - Tolerancia por seccion: la fila se escribe SIEMPRE, con texto o sin el. Un
    429 o un timeout deja esa seccion vacia y las otras siete siguen. El
    mini-informe nunca se pierde entero por una llamada.
  - Idempotencia: cada seccion se guarda con UPDATE sobre el UNIQUE de N4.5
    (execution_id, label, section). Regenerar reescribe, no duplica.
  - Progreso: COMMIT despues de cada seccion, asi que el avance es legible desde
    la base (n filas de 8). No hay registro en memoria porque en produccion el
    backend corre con --workers 2 y el proceso que atiende el sondeo puede no
    ser el que esta generando. La base es el unico canal que ven los dos.
  - Regla 14 (`sanitize_ai_text`) y leccion GRAF1 (el max con su ratio en todos
    los prompts) se respetan igual que en N3.4.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.models.transaction_chart_analysis import (
    SECTIONS, SECTIONS_GENERADAS, TransactionChartAnalysis)   # ETAPA 2 (D20)
from app.services.ai.gemini import (
    get_gemini_analyzer,
    load_ai_config_from_db,
    sanitize_ai_text,
)
# ETAPA 3 (D28): `UX_RULE` y `FORMATO_NUMERICO` vivian aqui porque solo hacian
# falta para hablar de UNA transaccion. Resulto que hacian falta en todas partes:
# los bloques por transaccion salieron con 3 avisos de estilo y el informe
# general con 121 (reporte 30 §5). Las dos reglas estan ahora dentro de
# `BLOQUE_ESTILO`, que llega a los diecinueve prompts por igual.
from app.services.ai.estilo import num as _n
from app.services.ai.estilo import ms, percentil_frase, pct, veces

logger = logging.getLogger(__name__)

# N4.6b, defecto 1: el texto de la primera corrida invirtio la definicion y
# atribuyo la descarga del cuerpo al procesamiento del servidor. Va solo en el
# prompt de chart_latency, que es la unica seccion que interpreta esa resta.
DEFINICION_LATENCIA = """
COMO SE LEE LA LATENCIA EN JMETER (definicion obligatoria, no la inviertas):
- Latency es el tiempo hasta el PRIMER BYTE de la respuesta: incluye la conexion, el envio de la peticion Y el procesamiento del servidor.
- Elapsed menos Latency es el tiempo de DESCARGA del cuerpo de la respuesta.
- Por tanto: una latencia alta apunta a servidor lento o red lenta de ida; una diferencia elapsed-latency alta apunta a respuestas pesadas o ancho de banda limitado.
- PROHIBIDO atribuir el tiempo de descarga al procesamiento del servidor.
- PROHIBIDO explicar la latencia como si fuera solo red: el procesamiento del servidor esta dentro de ella.
"""

# N4.6b, defecto 3: el pico aparecia en las 8 secciones. Aqui es obligatorio; en
# las otras cuatro se menciona solo si aporta a ESA grafica. La leccion GRAF1
# sigue intacta porque estas cuatro cubren el mini-informe de punta a punta.
PICO_OBLIGATORIO = ("summary", "chart_response_times", "conclusions", "recommendations")


# Que se le pide a cada seccion y su tope de palabras. Las graficas mantienen el
# tope de las globales (130); resumen, conclusiones y recomendaciones van a 200
# por decision de este sprint.
INSTRUCCIONES: Dict[str, tuple] = {
    "summary": ("Resumen del comportamiento de esta transaccion: como respondio, que la separa de un servicio sano y a cuantos usuarios les duele la espera.", 200),
    "chart_response_times": ("Analiza la evolucion de sus tiempos de respuesta en el tiempo: nivel base, picos y cuando aparecen.", 130),
    "chart_latency": ("Analiza su latencia frente al tiempo total: cuanto pesa la red o la espera previa contra el procesamiento del servidor.", 130),
    "chart_error_rate": ("Analiza su tasa de error a lo largo de la prueba: si es constante, si se concentra en un tramo o si no hubo errores.", 130),
    "chart_codes": ("Analiza los codigos de respuesta de esta transaccion y que indica su reparto sobre la salud del servicio.", 130),
    "chart_tps": ("Analiza su caudal de transacciones por segundo: si se sostiene, si cae y como se relaciona con sus tiempos.", 130),
    # D30: estas dos ya no se generan (D20), pero si alguien las reactiva no
    # pueden dictaminar sobre produccion desde el bloque de UNA transaccion.
    "conclusions": ("Escribe las conclusiones de ESTA transaccion: que quedo demostrado, con sus cifras.", 200),
    "recommendations": ("Escribe las recomendaciones para ESTA transaccion, priorizadas, accionables y justificadas con sus cifras.", 200),
}


def _serie_digest(series: Dict[str, Any]) -> Dict[str, str]:
    """Resume las 5 series a una linea cada una. El prompt no puede llevar los
    ~500 KB de puntos que devuelve N4.3, pero si su forma: pico, promedio y
    cuando pasa lo relevante."""
    interval = int(series.get("interval_seconds", 1) or 1)

    def _vals(nombre: str, key: str = "value") -> List[float]:
        return [float(p.get(key, 0) or 0) for p in (series.get(nombre) or [])]

    rt, rt_max = _vals("response_times"), _vals("response_times", "value_max")
    hora_pico = ""
    if rt_max:
        pico = max(rt_max)
        for p in series["response_times"]:
            if float(p.get("value_max", 0) or 0) == pico:
                hora_pico = f" a las {str(p['timestamp'])[11:19]}"
                break
    lat, err, tps = _vals("latency"), _vals("error_rate"), _vals("tps")

    conteo: Dict[str, float] = {}
    for p in series.get("codes") or []:
        conteo[str(p.get("code"))] = conteo.get(str(p.get("code")), 0.0) + float(p.get("value", 0) or 0) * interval
    codes_txt = "; ".join(f"{c}: {_n(n)} respuestas" for c, n in sorted(conteo.items(), key=lambda x: -x[1])) or "sin dato de codigos"

    con_error = [v for v in err if v > 0]
    # N4.6b: todas las cifras salen de `_n()`, en formato espanol.
    return {
        "chart_response_times": (f"Serie de tiempos de respuesta en bucket de {interval} s, {_n(len(rt))} puntos. "
                                 f"Promedio de la serie {_n(sum(rt)/len(rt) if rt else 0)} ms, pico maximo {_n(max(rt_max) if rt_max else 0)} ms{hora_pico}."),
        "chart_latency": (f"Serie de latencia, {_n(len(lat))} puntos, promedio {_n(sum(lat)/len(lat) if lat else 0)} ms y maximo {_n(max(lat) if lat else 0)} ms."
                          if lat else "Serie de latencia sin dato en este JTL."),
        "chart_error_rate": (f"Serie de tasa de error, {_n(len(err))} intervalos: {_n(len(con_error))} con al menos un fallo, "
                             f"pico {pct(max(err) if err else 0)} en un intervalo."),
        "chart_codes": f"Codigos de respuesta acumulados de la transaccion: {codes_txt}.",
        "chart_tps": (f"Serie de transacciones por segundo, promedio {_n(sum(tps)/len(tps) if tps else 0, 2)} TPS "
                      f"y maximo {_n(max(tps) if tps else 0, 2)} TPS."),
    }


def build_section_prompts(label: str, m: Dict[str, Any], series: Dict[str, Any], test_type: str = "load") -> Dict[str, str]:
    """Los prompts de una transaccion, con SUS metricas reales.

    ETAPA 3 (D33/D34): las cifras siguen saliendo formateadas a la espanola —
    eso ya funcionaba —, los percentiles pasan a entregarse como la frase de
    usuario completa, y el bloque de estilo deja de repetirse aqui: lo pone
    `_generate` una sola vez por llamada.
    """
    avg, mx = float(m.get("promedio", 0) or 0), float(m.get("max", 0) or 0)
    ratio = veces(mx / avg) + " su promedio" if avg > 0 else "sin promedio de referencia"
    digest = _serie_digest(series)
    metricas = f"""METRICAS REALES DE LA TRANSACCION "{label}" (prueba de {test_type}):
- Muestras ejecutadas: {_n(m.get('muestras', 0))}
- Tiempo promedio: {ms(avg)} | Minimo: {ms(m.get('min', 0))}
- Tiempo maximo observado: {ms(mx)} ({ratio})
- Errores: {_n(m.get('errores', 0))} ({pct(m.get('tasa_error', 0))} de sus muestras)
- Caudal de la transaccion: {_n(m.get('rendimiento', 0), 2)} por segundo

LECTURA DE SUS PERCENTILES (copia estas frases tal cual):
- {percentil_frase(50, m.get('mediana', 0))}
- {percentil_frase(90, m.get('p90', 0))}
- {percentil_frase(95, m.get('p95', 0))}
- {percentil_frase(99, m.get('p99', 0))}"""

    prompts: Dict[str, str] = {}
    for section in SECTIONS_GENERADAS:   # ETAPA 2 (D20): ya no se arman los 8
        instruccion, tope = INSTRUCCIONES[section]
        # Las 5 graficas reciben su serie; resumen, conclusiones y recomendaciones
        # reciben las cinco, que es su ambito.
        serie_txt = digest.get(section) or "\n".join(digest.values())
        pico = (
            f"El maximo de {ms(mx)} y su relacion ({ratio}) son OBLIGATORIOS en esta seccion."
            if section in PICO_OBLIGATORIO else
            f"El maximo de {ms(mx)} se menciona SOLO si aporta a esta grafica en concreto; "
            f"si no aporta, no lo repitas: otras secciones del informe ya lo tratan."
        )
        extra = DEFINICION_LATENCIA if section == "chart_latency" else ""
        prompts[section] = f"""{metricas}

DATOS DE LA SERIE TEMPORAL:
{serie_txt}
{extra}
{instruccion}
Maximo {tope} palabras. Habla SOLO de esta transaccion, no del test completo.
{pico}
No digas si el servicio esta listo para produccion: eso va en las conclusiones
del informe, no en el bloque de una transaccion."""
    return prompts


async def _upsert(db, execution_id, label: str, section: str, texto: Optional[str], orden: int) -> None:
    """Guarda una seccion. UPDATE si ya existia (UNIQUE de N4.5), INSERT si no.
    Commit por seccion: es lo que hace legible el progreso desde la base."""
    row = (await db.execute(
        select(TransactionChartAnalysis).where(
            TransactionChartAnalysis.execution_id == execution_id,
            TransactionChartAnalysis.label == label,
            TransactionChartAnalysis.section == section,
        )
    )).scalar_one_or_none()

    if row is None:
        db.add(TransactionChartAnalysis(
            execution_id=execution_id, label=label, section=section,
            ai_analysis=texto, generated_at=datetime.utcnow(), sort_order=orden,
        ))
    else:
        row.ai_analysis = texto
        row.generated_at = datetime.utcnow()
        row.sort_order = orden
        # Regenerar produce texto de IA nuevo: la marca de edicion manual se cae.
        row.is_edited = False
        row.ai_analysis_updated_at = None
    await db.commit()


async def generate_transaction_report(
    db, execution_id, label: str, metrics: Dict[str, Any], series: Dict[str, Any],
    test_type: str = "load", analyzer=None, sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Genera y persiste las secciones. Nunca lanza por un fallo de IA.

    `sections` limita el trabajo a un subconjunto (N4.6b): sirve para rehacer una
    sola seccion sin pagar las demas. None = todas las que se generan.

    ETAPA 2 (D20): "todas" son SEIS — resumen + las 5 graficas. Las conclusiones y
    recomendaciones por transaccion ya no se generan (v1.2 §1.1): van una sola vez
    al final del informe. Si alguien pide explicitamente una de esas dos por
    `sections`, se ignora: el filtro parte de SECTIONS_GENERADAS.
    """
    objetivo = [s for s in SECTIONS_GENERADAS if not sections or s in sections]
    counters = {"total": len(objetivo), "generated": 0, "failed": 0}
    prompts = build_section_prompts(label, metrics, series, test_type)

    if analyzer is None:
        try:
            conf = await load_ai_config_from_db(db)
            analyzer = get_gemini_analyzer(
                provider=conf.get("provider", ""), model_name=conf.get("model_name", ""),
                api_key=conf.get("api_key", ""),
                reasoning_effort=(conf.get("reasoning_effort") or ""),   # ETAPA 2 D13c
            )
        except Exception as e:
            logger.error(f"N4.6: sin analizador disponible ({e}); las 8 secciones quedan sin texto")
            analyzer = None

    for section in objetivo:
        orden = SECTIONS.index(section)   # el orden no depende de que se regenere
        texto = None
        if analyzer is not None:
            try:
                # N4.10: `_generate` es SINCRONO. Invocado tal cual desde una
                # corrutina bloquea el event loop entero, y en background eso
                # significa que el backend no atiende nada durante los ~90 s —
                # incluido el sondeo del progreso, que es justo lo que la
                # pantalla necesita. Misma adaptacion que hizo F3.1 con _call_ai.
                texto = await asyncio.to_thread(
                    analyzer._generate, prompts[section], section_name=f"txreport_{section}"
                )
                if texto:
                    texto = sanitize_ai_text(texto)   # regla 14
            except Exception as e:
                # Tolerancia por seccion: se registra vacia y el resto sigue.
                logger.error(f"N4.6: fallo la seccion '{section}' de '{label}': {e}")
        try:
            await _upsert(db, execution_id, label, section, texto, orden)
        except Exception as e:
            logger.error(f"N4.6: no se pudo persistir '{section}' de '{label}': {e}")
            await db.rollback()
        counters["generated" if texto else "failed"] += 1
        logger.info(f"N4.6: {label} — {section} {'ok' if texto else 'VACIA'} ({counters['generated']}/{counters['total']})")

    logger.info(f"N4.6: mini-informe de '{label}' terminado {counters}")
    return counters
