"""
N4.6 — Generacion IA del mini-informe de UNA transaccion, bajo demanda.

Ocho secciones (SECTIONS de N4.5): resumen, las 5 graficas y las conclusiones y
recomendaciones propias de esa transaccion. Vive FUERA de /upload a proposito:
son 8 llamadas en serie (~90 s) que solo tienen sentido para las transacciones
que se decide abrir, no para cada carga de JTL.

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
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db.models.transaction_chart_analysis import SECTIONS, TransactionChartAnalysis
from app.services.ai.gemini import (
    STYLE_REMINDER,
    SYSTEM_PROMPT,
    get_gemini_analyzer,
    load_ai_config_from_db,
    sanitize_ai_text,
)

logger = logging.getLogger(__name__)

# Regla nueva de N4.6. Va aqui y NO en el SYSTEM_PROMPT: ese prompt lo comparten
# los 12 analisis globales ya validados en C2 (commit ef8636c) y el analisis de
# imagenes; cambiarlo obligaria a revalidar todo eso por una regla que solo
# aplica cuando se habla de UNA transaccion y de sus percentiles.
UX_RULE = """
TRADUCCION A EXPERIENCIA DE USUARIO (obligatorio, el publico es gerencial):
- Todo percentil que menciones va con su lectura en personas: P90 = 1 de cada 10 usuarios, P95 = 1 de cada 20, P99 = 1 de cada 100, mediana = la mitad de los usuarios.
- Forma exacta: "1 de cada 10 usuarios espera mas de 3,5 segundos (P90: 3.515 ms)". Primero las personas y el tiempo en segundos, la cifra tecnica despues entre parentesis.
- Por encima de 1.000 ms expresa el tiempo en segundos con un decimal; por debajo deja los milisegundos.
- Un percentil suelto, sin decir a cuantos usuarios afecta, no sirve para este informe.
"""

# N4.6b, defecto 2: el modelo escribia "8,600 muestras" (miles a la inglesa) y
# mezclaba "1.070 ms" con "1070 ms" en el mismo parrafo. La defensa principal es
# `_n()`: los datos se le entregan YA formateados a la espanola, asi que copiar
# es mas facil que reformatear. Esta regla es el cinturon de seguridad.
FORMATO_NUMERICO = """
FORMATO NUMERICO ESPANOL (obligatorio):
- Miles con punto y decimales con coma: 8.600 muestras, 21.060 ms, 1,1 segundos, 0,27%.
- Las cifras de los datos entregados YA vienen en ese formato: copialas tal cual, no las reescribas.
- PROHIBIDO el formato ingles (8,600 muestras, 1.1 segundos) y PROHIBIDO mezclar los dos estilos en el mismo texto.
"""

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


def _n(valor, dec: int = 0) -> str:
    """Numero a la espanola: miles con punto, decimales con coma."""
    txt = f"{float(valor or 0):,.{dec}f}"
    return txt.replace(",", "\x01").replace(".", ",").replace("\x01", ".")

# Que se le pide a cada seccion y su tope de palabras. Las graficas mantienen el
# tope de las globales (120, regla 8 del SYSTEM_PROMPT); resumen, conclusiones y
# recomendaciones van a 200 por decision de este sprint.
INSTRUCCIONES: Dict[str, tuple] = {
    "summary": ("Resumen ejecutivo del comportamiento de esta transaccion: como respondio, que la separa de un servicio sano y que percentiles duelen.", 200),
    "chart_response_times": ("Analiza la evolucion de sus tiempos de respuesta en el tiempo: nivel base, picos y cuando aparecen.", 120),
    "chart_latency": ("Analiza su latencia frente al tiempo total: cuanto pesa la red o la espera previa contra el procesamiento del servidor.", 120),
    "chart_error_rate": ("Analiza su tasa de error a lo largo de la prueba: si es constante, si se concentra en un tramo o si no hubo errores.", 120),
    "chart_codes": ("Analiza los codigos de respuesta de esta transaccion y que indica su reparto sobre la salud del servicio.", 120),
    "chart_tps": ("Analiza su caudal de transacciones por segundo: si se sostiene, si cae y como se relaciona con sus tiempos.", 120),
    "conclusions": ("Escribe las conclusiones de ESTA transaccion: que quedo demostrado, con sus cifras, y si el servicio esta listo para produccion.", 200),
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
                             f"pico {_n(max(err) if err else 0, 2)}% en un intervalo."),
        "chart_codes": f"Codigos de respuesta acumulados de la transaccion: {codes_txt}.",
        "chart_tps": (f"Serie de transacciones por segundo, promedio {_n(sum(tps)/len(tps) if tps else 0, 2)} TPS "
                      f"y maximo {_n(max(tps) if tps else 0, 2)} TPS."),
    }


def build_section_prompts(label: str, m: Dict[str, Any], series: Dict[str, Any], test_type: str = "load") -> Dict[str, str]:
    """Los 8 prompts de una transaccion, con SUS metricas reales."""
    avg, mx = float(m.get("promedio", 0) or 0), float(m.get("max", 0) or 0)
    ratio = f"{_n(mx / avg, 1)} veces su promedio" if avg > 0 else "sin promedio de referencia"
    digest = _serie_digest(series)
    # N4.6b: cada cifra pasa por `_n()`. Antes se entregaban con `:,` (formato
    # ingles) y el modelo copiaba "8,600 muestras" al texto final.
    metricas = f"""METRICAS REALES DE LA TRANSACCION "{label}" (prueba de {test_type}):
- Muestras ejecutadas: {_n(m.get('muestras', 0))}
- Tiempo promedio: {_n(avg)} ms | Mediana: {_n(m.get('mediana', 0))} ms | Minimo: {_n(m.get('min', 0))} ms
- Percentil 90: {_n(m.get('p90', 0))} ms | Percentil 95: {_n(m.get('p95', 0))} ms | Percentil 99: {_n(m.get('p99', 0))} ms
- Tiempo maximo observado: {_n(mx)} ms ({ratio})
- Errores: {_n(m.get('errores', 0))} ({_n(m.get('tasa_error', 0), 2)}% de sus muestras)
- Caudal de la transaccion: {_n(m.get('rendimiento', 0), 2)} por segundo"""

    prompts: Dict[str, str] = {}
    for section in SECTIONS:
        instruccion, tope = INSTRUCCIONES[section]
        # Las 5 graficas reciben su serie; resumen, conclusiones y recomendaciones
        # reciben las cinco, que es su ambito.
        serie_txt = digest.get(section) or "\n".join(digest.values())
        pico = (
            f"El maximo de {_n(mx)} ms y su ratio ({ratio}) son OBLIGATORIOS en esta seccion."
            if section in PICO_OBLIGATORIO else
            f"El maximo de {_n(mx)} ms se menciona SOLO si aporta a esta grafica en concreto; "
            f"si no aporta, no lo repitas: otras secciones del informe ya lo tratan."
        )
        extra = DEFINICION_LATENCIA if section == "chart_latency" else ""
        prompts[section] = f"""{SYSTEM_PROMPT}

{metricas}

DATOS DE LA SERIE TEMPORAL:
{serie_txt}
{extra}
{instruccion}
Maximo {tope} palabras. Habla SOLO de esta transaccion, no del test completo.
{pico}
{STYLE_REMINDER}{UX_RULE}{FORMATO_NUMERICO}"""
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

    `sections` limita el trabajo a un subconjunto de SECTIONS (N4.6b): sirve
    para rehacer una sola seccion sin pagar las ocho. None = las ocho.
    """
    objetivo = [s for s in SECTIONS if not sections or s in sections]
    counters = {"total": len(objetivo), "generated": 0, "failed": 0}
    prompts = build_section_prompts(label, metrics, series, test_type)

    if analyzer is None:
        try:
            conf = await load_ai_config_from_db(db)
            analyzer = get_gemini_analyzer(
                provider=conf.get("provider", ""), model_name=conf.get("model_name", ""),
                api_key=conf.get("api_key", ""),
            )
        except Exception as e:
            logger.error(f"N4.6: sin analizador disponible ({e}); las 8 secciones quedan sin texto")
            analyzer = None

    for section in objetivo:
        orden = SECTIONS.index(section)   # el orden no depende de que se regenere
        texto = None
        if analyzer is not None:
            try:
                texto = analyzer._generate(prompts[section], section_name=f"txreport_{section}")
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
