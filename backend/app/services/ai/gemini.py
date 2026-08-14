"""
Servicio de Analisis con IA - v4.0
Soporta Google Gemini y OpenAI como proveedores.
Pre-clasificacion de datos en tiers de performance,
SYSTEM_PROMPT con ejemplos de buen/mal analisis,
sin truncacion, sin limites de transacciones.
Rate-limit safe con delays entre llamadas.
FallbackAnalyzer para cuando la IA no esta disponible.
"""
import os
import time
import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
import logging

# DPERF-1 (fix C): el SDK de OpenAI se importa aqui, al cargar el modulo, para que
# el costo del import se pague al arrancar el contenedor y no en el primer analisis.
# Guardado con try/except porque el provider puede ser solo Gemini.
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================

# Default model - can be overridden by DB config
MODEL_NAME = "gemini-2.5-flash"
DEFAULT_PROVIDER = "gemini"

# Mapeo de test_type a descripcion en espanol
TEST_TYPE_DESCRIPTIONS: Dict[str, str] = {
    "load": "Prueba de Carga (Load Test) - valida comportamiento bajo carga esperada",
    "stress": "Prueba de Estres (Stress Test) - identifica punto de quiebre del sistema",
    "endurance": "Prueba de Resistencia (Endurance/Soak Test) - valida estabilidad en ejecucion prolongada",
    "scalability": "Prueba de Escalabilidad (Scalability Test) - mide capacidad de escalar con incremento gradual",
    "spike": "Prueba de Picos (Spike Test) - evalua respuesta ante incrementos subitos de carga",
    "smoke": "Prueba de Humo (Smoke Test) - validacion basica con carga minima",
}

GENERATION_CONFIG = {
    "max_output_tokens": 8192,
    "temperature": 0.7,
}

# Max completion tokens per OpenAI model (Gemini uses GENERATION_CONFIG directly)
OPENAI_MAX_TOKENS = {
    "gpt-3.5-turbo": 4096,
    "gpt-4": 4096,
    "gpt-4-turbo": 4096,
    "gpt-4o": 16384,
    "gpt-4o-mini": 16384,
    "gpt-4.1": 32768,
    "gpt-4.1-mini": 32768,  # HF18b: familia gpt-4.1 soporta 32K de output
    "gpt-4.1-nano": 32768,  # HF18b: idem — evita truncacion si se cambia a nano
    "gpt-5-mini": 16384,
    "gpt-5-nano": 8192,
    "o4-mini": 16384,
    # B6: familias de razonamiento que ofrece la lista viva. Su limite real de
    # salida documentado es MAYOR; se fija 16384 como valor conservador (igual
    # que o4-mini) para que no caigan al default de 4096 y trunquen. Subirlo es
    # seguro si algun analisis se queda corto.
    "o3": 16384,
    "o3-mini": 16384,
    "o1": 16384,
    "o1-mini": 16384,
}
OPENAI_DEFAULT_MAX_TOKENS = 4096


def _openai_max_tokens_for(model_name: str) -> int:
    """Techo de salida del modelo, avisando cuando no esta en el dict.

    B6 (leccion HF18b): un modelo ausente de OPENAI_MAX_TOKENS caia al default
    de 4096 EN SILENCIO y truncaba los analisis. Ahora queda registrado en el
    log con el nombre del modelo. Mismo patron que ya usa script_ai.py.
    """
    if model_name in OPENAI_MAX_TOKENS:
        return OPENAI_MAX_TOKENS[model_name]
    logger.warning(
        "modelo %s sin entrada en OPENAI_MAX_TOKENS, usando default %s "
        "(riesgo de truncacion: agregarlo al dict si el analisis sale corto)",
        model_name, OPENAI_DEFAULT_MAX_TOKENS,
    )
    return OPENAI_DEFAULT_MAX_TOKENS

# Performance tier thresholds (ms)
TIER_EXCELLENT = 500
TIER_ACCEPTABLE = 2000
TIER_DEGRADED = 5000

SYSTEM_PROMPT = """Eres un analista senior de performance con 15 anos de experiencia. Redactas informes tecnicos para gerentes de TI en espanol profesional colombiano.

REGLAS DE ESTILO OBLIGATORIAS:

1. PROHIBIDO usar markdown: nada de **, ##, *, -, ni vinetas con asteriscos o guiones.
2. PROHIBIDO usar las palabras: "veredicto", "hallazgo", "se evidencia", "cabe destacar", "es importante mencionar", "en conclusion".
3. PROHIBIDO encerrar palabras entre asteriscos o comillas para dar enfasis.
4. PROHIBIDO numerar parrafos (1. 2. 3.) excepto en conclusiones y recomendaciones.
5. Escribe en parrafos narrativos fluidos de 3-5 oraciones cada uno.
6. Usa datos concretos (numeros, porcentajes, milisegundos) dentro de las frases, no como listas aparte.
7. Cuando menciones transacciones, usa su nombre natural en el texto sin resaltarlo con formato especial.
8. Maximo 200 palabras por analisis de grafica. Para conclusiones y recomendaciones maximo 600 palabras.
9. Compara la transaccion mas rapida vs la mas lenta. Agrupa por comportamiento similar.
10. Explica el impacto para el usuario final.
11. El texto debe leerse como si un humano lo hubiera escrito, no generado por IA.

EJEMPLO CORRECTO:
"La transaccion de inicio de sesion mantuvo un tiempo de respuesta promedio de 245ms durante toda la prueba, dentro del umbral de 2000ms definido por el cliente. Sin embargo, a partir del minuto 15 los tiempos comenzaron a incrementarse de forma gradual, alcanzando picos de 890ms en el percentil 99. Este comportamiento sugiere que el pool de conexiones podria estar saturandose conforme aumenta la concurrencia sostenida."
"""


def sanitize_ai_text(text: str) -> str:
    """Clean Gemini output by removing markdown formatting artifacts."""
    if not text:
        return text
    import re as _re
    # Remove markdown headers
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
    # Remove bold markdown
    text = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = _re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic markdown (careful with contractions)
    text = _re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', text)
    # Remove bullet markers at start of line
    text = _re.sub(r'^[\*\-]\s+', '', text, flags=_re.MULTILINE)
    # Remove backticks
    text = _re.sub(r'`(.+?)`', r'\1', text)
    # Remove horizontal rules
    text = _re.sub(r'^[\-\*]{3,}$', '', text, flags=_re.MULTILINE)
    # Collapse multiple blank lines
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# KNX-08: Metric unit names for consistent AI analysis
METRIC_UNIT_NAMES = {
    "TPS": "Transacciones por segundo (TPS)",
    "UVC": "Usuarios virtuales concurrentes (UVC)",
}


def get_metric_unit_instruction(metric_unit: str = "TPS") -> str:
    """Returns the instruction to append to prompts for consistent metric unit usage."""
    unit_name = METRIC_UNIT_NAMES.get(metric_unit, METRIC_UNIT_NAMES["TPS"])
    return (
        f"\n\nUNIDAD DE MEDIDA: Cuando menciones metricas de rendimiento/carga, "
        f"usa siempre '{unit_name}'. NO mezcles TPS con UVC. Se consistente."
    )


# ==================== VERDICT CALCULATOR ====================

def compute_verdict(metrics: Dict, acceptance_criteria: Optional[Dict] = None) -> str:
    """
    Compute verdict (APTO / NO APTO / APTO CON RESERVAS) based on acceptance criteria.
    If no criteria provided, uses default thresholds.
    """
    avg_rt = float(metrics.get('avg_response_time', metrics.get('avg_rt', 0)))
    error_rate = float(metrics.get('error_rate', 0))
    total_requests = int(metrics.get('total_requests', 0))
    total_errors = int(metrics.get('total_errors', 0))

    # Derive availability from error_rate
    availability = 100.0 - error_rate

    # Get thresholds from criteria or defaults
    if acceptance_criteria and not acceptance_criteria.get('raw_text'):
        max_rt = float(acceptance_criteria.get('response_time', 2000))
        min_avail = float(acceptance_criteria.get('availability', 99.0))
    else:
        max_rt = 2000.0
        min_avail = 99.0

    # Evaluate
    rt_fail = avg_rt > max_rt
    avail_fail = availability < min_avail
    rt_warning = avg_rt > (max_rt * 0.8)  # within 80-100% of threshold
    avail_warning = availability < (min_avail + 0.5) and availability >= min_avail

    if rt_fail or avail_fail:
        return "NO APTO"
    elif rt_warning or avail_warning:
        return "APTO CON RESERVAS"
    else:
        return "APTO"


def compute_per_transaction_verdicts(
    summary_df, acceptance_criteria: Optional[Dict] = None
) -> Dict:
    """
    KNX-09: Evaluate PASS/FAIL per transaction using per-transaction or global criteria.
    Returns dict with 'verdicts_per_transaction' and updated 'verdict'.
    """
    if acceptance_criteria is None or acceptance_criteria.get('raw_text'):
        return {}

    global_rt = float(acceptance_criteria.get('response_time', 2000))
    global_avail = float(acceptance_criteria.get('availability', 99.0))
    per_txn = acceptance_criteria.get('per_transaction', {})

    verdicts = {}
    for _, row in summary_df.iterrows():
        label = row['label']
        txn_criteria = per_txn.get(label, {})
        rt_threshold = float(txn_criteria.get('response_time', global_rt))
        er_threshold = 100.0 - float(txn_criteria.get('availability', global_avail))

        p90 = float(row['p90'])
        error_rate = float(row['tasa_error'])

        rt_fail = p90 > rt_threshold
        er_fail = error_rate > er_threshold
        rt_warning = p90 > (rt_threshold * 0.8) and not rt_fail

        if rt_fail or er_fail:
            verdicts[label] = "NO APTO"
        elif rt_warning:
            verdicts[label] = "APTO CON RESERVAS"
        else:
            verdicts[label] = "APTO"

    global_verdict = "APTO"
    if any(v == "NO APTO" for v in verdicts.values()):
        global_verdict = "NO APTO"
    elif any(v == "APTO CON RESERVAS" for v in verdicts.values()):
        global_verdict = "APTO CON RESERVAS"

    return {
        'verdicts_per_transaction': verdicts,
        'verdict': global_verdict,
    }


# ==================== FALLBACK ANALYZER ====================

class FallbackAnalyzer:
    """Generates basic analysis without AI when Gemini is unavailable."""

    @staticmethod
    def analyze_summary_table(stats_data, insights=None):
        """Generate fallback summary table analysis from raw stats."""
        import pandas as pd
        if isinstance(stats_data, pd.DataFrame):
            stats_data = stats_data.to_dict('records')
        if not stats_data or len(stats_data) == 0:
            return "No hay datos disponibles para el analisis."

        # Normalize keys (DataFrame .to_dict uses Spanish column names)
        transactions = []
        for row in stats_data:
            transactions.append({
                'label': row.get('label', 'N/A'),
                'samples': int(row.get('muestras', row.get('samples', 0))),
                'errors': int(row.get('errores', row.get('errors', 0))),
                'error_pct': float(row.get('tasa_error', row.get('error_pct', 0))),
                'avg': float(row.get('promedio', row.get('avg', 0))),
                'p90': float(row.get('p90', 0)),
                'p95': float(row.get('p95', 0)),
                'p99': float(row.get('p99', 0)),
                'min': float(row.get('min', 0)),
                'max': float(row.get('max', 0)),
                'tps': float(row.get('rendimiento', row.get('tps', 0))),
            })

        # Sort by avg response time descending
        transactions.sort(key=lambda x: x['avg'], reverse=True)

        total_requests = sum(t['samples'] for t in transactions)
        total_errors = sum(t['errors'] for t in transactions)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        avg_rt = sum(t['avg'] * t['samples'] for t in transactions) / total_requests if total_requests > 0 else 0

        slowest = transactions[0] if transactions else None
        fastest = transactions[-1] if transactions else None

        # Count tiers
        critical = [t for t in transactions if t['avg'] > 5000]
        degraded = [t for t in transactions if 2000 < t['avg'] <= 5000]
        acceptable = [t for t in transactions if 500 < t['avg'] <= 2000]
        excellent = [t for t in transactions if t['avg'] <= 500]
        with_errors = [t for t in transactions if t['errors'] > 0]

        analysis = f"La prueba proceso {total_requests:,} solicitudes con una tasa de error del {error_rate:.2f}% "
        analysis += f"y un tiempo de respuesta promedio de {avg_rt:.0f}ms. "
        analysis += f"Se evaluaron {len(transactions)} transacciones: "
        analysis += f"{len(excellent)} con rendimiento excelente (<500ms), "
        analysis += f"{len(acceptable)} aceptables (500-2000ms), "
        analysis += f"{len(degraded)} degradadas (2000-5000ms) y "
        analysis += f"{len(critical)} criticas (>5000ms). "

        if slowest:
            analysis += f"\n\nLa transaccion mas lenta es \"{slowest['label']}\" con {slowest['avg']:.0f}ms de promedio"
            if fastest and fastest['avg'] > 0:
                analysis += f", contrastando con \"{fastest['label']}\" que es la mas rapida con {fastest['avg']:.0f}ms. "
                if fastest['avg'] > 0:
                    analysis += f"Esta diferencia de {slowest['avg']/fastest['avg']:.0f}x indica una disparidad significativa en el rendimiento."

        if with_errors:
            analysis += f"\n\nSe detectaron errores en {len(with_errors)} transacciones: "
            error_details = []
            for t in with_errors[:5]:
                error_details.append(f"\"{t['label']}\" ({t['error_pct']:.2f}%)")
            analysis += ", ".join(error_details) + ". "
            analysis += "Se recomienda investigar las causas de estos errores antes de desplegar en produccion."

        if avg_rt > 2000:
            analysis += "\n\nEl sistema NO cumple con los criterios de rendimiento aceptables y requiere optimizacion antes de produccion."
        elif avg_rt > 1000:
            analysis += "\n\nEl sistema cumple parcialmente con los criterios de rendimiento. Se recomienda optimizar las transacciones degradadas."
        else:
            analysis += "\n\nEl sistema presenta un rendimiento dentro de los parametros aceptables."

        return analysis

    @staticmethod
    def analyze_errors(error_data, total_requests):
        """Generate fallback error analysis."""
        import pandas as pd
        if isinstance(error_data, pd.DataFrame):
            error_data = error_data.to_dict('records')
        if not error_data or len(error_data) == 0:
            return "No se detectaron errores en la ejecucion. El sistema respondio correctamente a todas las solicitudes."

        total_errors = sum(item['count'] for item in error_data)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

        analysis = f"Se detectaron {total_errors:,} errores ({error_rate:.2f}%) de {total_requests:,} solicitudes totales. "

        # Group by code
        by_code = {}
        for item in error_data:
            code = str(item.get('code', 'N/A'))
            if code not in by_code:
                by_code[code] = {'count': 0, 'labels': []}
            by_code[code]['count'] += item['count']
            if item['label'] not in by_code[code]['labels']:
                by_code[code]['labels'].append(item['label'])

        for code, info in sorted(by_code.items()):
            category = "error del servidor" if code.startswith('5') else \
                       "error del cliente" if code.startswith('4') else \
                       "redireccion" if code.startswith('3') else "otro"
            analysis += f"HTTP {code} ({category}): {info['count']:,} errores en {', '.join(info['labels'][:3])}. "

        if error_rate > 5:
            analysis += "\n\nLa tasa de error es CRITICA y requiere atencion inmediata antes de cualquier despliegue."
        elif error_rate > 1:
            analysis += "\n\nLa tasa de error es significativa y debe investigarse para garantizar la estabilidad."
        else:
            analysis += "\n\nLa tasa de error es baja pero debe monitorearse en produccion."

        return analysis

    @staticmethod
    def analyze_chart(chart_type, stats_summary):
        """Generate fallback chart analysis from summary stats."""
        if stats_summary is None or not isinstance(stats_summary, dict):
            stats_summary = {}
        avg_rt = stats_summary.get('avg_rt', 0)
        min_rt = stats_summary.get('min_rt', 0)
        max_rt = stats_summary.get('max_rt', 0)
        p95 = stats_summary.get('p95', 0)
        throughput = stats_summary.get('throughput', 0)
        total_requests = stats_summary.get('total_requests', 0)
        duration = stats_summary.get('duration', 0)
        error_rate = stats_summary.get('error_rate', 0)
        total_errors = stats_summary.get('total_errors', 0)
        avg_latency = stats_summary.get('avg_latency', 0)
        kb_received = stats_summary.get('kb_received', 0)
        kb_sent = stats_summary.get('kb_sent', 0)
        num_transactions = stats_summary.get('num_transactions', 0)

        templates = {
            "response_times": (
                f"El grafico de tiempos de respuesta muestra la distribucion de latencias por transaccion. "
                f"El tiempo promedio global es {avg_rt:.0f}ms con un rango entre {min_rt:.0f}ms y {max_rt:.0f}ms. "
                f"El percentil 95 se ubica en {p95:.0f}ms, indicando que el 5% de las solicitudes experimentan tiempos superiores a este valor. "
                f"Se recomienda analizar las transacciones que superan los 2000ms de promedio para identificar cuellos de botella."
            ),
            "response_time_over_time": (
                f"El grafico temporal muestra la evolucion de los tiempos de respuesta durante los {duration:.0f}s de prueba. "
                f"El tiempo promedio fue {avg_rt:.0f}ms con variaciones entre {min_rt:.0f}ms y {max_rt:.0f}ms. "
                f"Se debe verificar si existen patrones de degradacion progresiva que indiquen problemas de memoria o recursos."
            ),
            "throughput": (
                f"El throughput promedio fue de {throughput:.2f} req/s durante {duration:.0f}s de prueba, "
                f"procesando un total de {total_requests:,} solicitudes. "
                f"La consistencia del throughput indica la capacidad del sistema para mantener la carga sostenida."
            ),
            "latency": (
                f"La latencia promedio de red fue {avg_latency:.0f}ms. "
                f"Se recibieron {kb_received:.2f} KB/s y se enviaron {kb_sent:.2f} KB/s. "
                f"Variaciones significativas en la latencia pueden indicar problemas de red o saturacion del servidor."
            ),
            "error_rate": (
                f"La tasa de error global fue {error_rate:.2f}% ({total_errors:,} de {total_requests:,} solicitudes). "
                f"Se debe investigar la distribucion temporal de errores para determinar si son constantes, intermitentes o crecientes bajo carga."
            ),
            "codes_per_second": (
                f"La distribucion de codigos HTTP muestra el patron de respuestas del servidor. "
                f"Los codigos 2xx indican exito, 3xx redirecciones, 4xx errores del cliente y 5xx errores del servidor. "
                f"Una proporcion alta de codigos no-2xx requiere investigacion."
            ),
            "transactions_per_second": (
                f"El grafico de transacciones por segundo muestra la distribucion de carga entre las {num_transactions} transacciones. "
                f"El TPS total fue {throughput:.2f} req/s. "
                f"La uniformidad en el TPS por transaccion indica un balanceo adecuado del plan de pruebas."
            ),
            "active_threads": (
                f"El grafico de hilos activos muestra el patron de concurrencia durante los {duration:.0f}s de prueba. "
                f"Se debe verificar que el ramp-up fue gradual y que la meseta de carga se mantuvo estable. "
                f"Correlacionar los picos de concurrencia con degradaciones en tiempo de respuesta ayuda a identificar el punto de saturacion."
            ),
        }

        return templates.get(chart_type, f"Analisis automatico no disponible para {chart_type}.")

    @staticmethod
    def generate_conclusions(stats_summary, acceptance_criteria=None):
        """Generate fallback conclusions using acceptance criteria if available."""
        if stats_summary is None or not isinstance(stats_summary, dict):
            stats_summary = {}
        avg_rt = float(stats_summary.get('avg_rt', 0))
        error_rate = float(stats_summary.get('error_rate', 0))
        throughput = stats_summary.get('throughput', 0)
        total_requests = stats_summary.get('total_requests', 0)
        duration = stats_summary.get('duration', 0)
        availability = 100.0 - error_rate

        # Use real criteria thresholds
        if acceptance_criteria and not acceptance_criteria.get('raw_text'):
            max_rt = float(acceptance_criteria.get('response_time', 2000))
            min_avail = float(acceptance_criteria.get('availability', 99.0))
            expected_concurrency = acceptance_criteria.get('concurrency')
        else:
            max_rt = 2000.0
            min_avail = 99.0
            expected_concurrency = None

        verdict = compute_verdict(stats_summary, acceptance_criteria)

        criteria_label = f"(criterio: <{max_rt:.0f}ms tiempo de respuesta, >{min_avail:.1f}% disponibilidad)"

        conclusions = f"1. VEREDICTO: {verdict} {criteria_label}. "
        if verdict == "NO APTO":
            reasons = []
            if avg_rt > max_rt:
                reasons.append(f"tiempo promedio {avg_rt:.0f}ms excede el umbral de {max_rt:.0f}ms")
            if availability < min_avail:
                reasons.append(f"disponibilidad {availability:.2f}% esta por debajo del minimo de {min_avail:.1f}%")
            conclusions += f"El sistema no cumple con los criterios de aceptacion: {'; '.join(reasons)}. "
        elif verdict == "APTO CON RESERVAS":
            conclusions += f"El sistema cumple marginalmente los criterios. Tiempo promedio: {avg_rt:.0f}ms (limite: {max_rt:.0f}ms), disponibilidad: {availability:.2f}% (minimo: {min_avail:.1f}%). "
        else:
            conclusions += f"El sistema cumple satisfactoriamente los criterios. Tiempo promedio: {avg_rt:.0f}ms (limite: {max_rt:.0f}ms), disponibilidad: {availability:.2f}% (minimo: {min_avail:.1f}%). "

        if expected_concurrency:
            conclusions += f"\n\n2. CONCURRENCIA: La prueba se ejecuto con {expected_concurrency} usuarios concurrentes esperados. "
            conclusions += f"El throughput de {throughput:.2f} req/s durante {duration:.0f}s proceso {total_requests:,} solicitudes bajo esta carga."
        else:
            conclusions += f"\n\n2. RENDIMIENTO: El throughput de {throughput:.2f} req/s durante {duration:.0f}s proceso {total_requests:,} solicitudes. "
            conclusions += "Se debe evaluar si este throughput es suficiente para la carga esperada en produccion."

        conclusions += f"\n\n3. ESTABILIDAD: Con una disponibilidad del {availability:.2f}%, "
        if error_rate == 0:
            conclusions += "el sistema demostro alta confiabilidad sin errores durante la prueba. Sin embargo, se recomienda ejecutar pruebas de estres para validar el comportamiento bajo carga extrema."
        elif availability >= min_avail:
            conclusions += "los errores detectados son menores pero requieren investigacion para garantizar la estabilidad en produccion."
        else:
            conclusions += f"la disponibilidad esta por debajo del criterio minimo de {min_avail:.1f}% y debe resolverse antes del despliegue."

        conclusions += "\n\n4. PROXIMOS PASOS: Se recomienda ejecutar pruebas adicionales de estres y resistencia para validar el comportamiento del sistema bajo condiciones extremas y prolongadas."

        return conclusions

    @staticmethod
    def generate_recommendations(stats_summary, acceptance_criteria=None):
        """Generate fallback recommendations using acceptance criteria if available."""
        if stats_summary is None or not isinstance(stats_summary, dict):
            stats_summary = {}
        avg_rt = float(stats_summary.get('avg_rt', 0))
        error_rate = float(stats_summary.get('error_rate', 0))

        # Use real thresholds from criteria
        if acceptance_criteria and not acceptance_criteria.get('raw_text'):
            max_rt = float(acceptance_criteria.get('response_time', 2000))
            min_avail = float(acceptance_criteria.get('availability', 99.0))
        else:
            max_rt = 2000.0
            min_avail = 99.0

        availability = 100.0 - error_rate

        recs = "PRIORIDAD CRITICA:\n\n"

        if avg_rt > max_rt:
            recs += f"1. Optimizar las transacciones con tiempos de respuesta superiores a {max_rt:.0f}ms (criterio de aceptacion). Revisar queries a base de datos, llamadas a servicios externos y procesamiento en el servidor de aplicaciones.\n\n"
        else:
            recs += f"1. Mantener el rendimiento actual ({avg_rt:.0f}ms promedio, dentro del criterio de {max_rt:.0f}ms) y establecer alertas tempranas si los tiempos se acercan al umbral.\n\n"

        if availability < min_avail:
            recs += f"2. Resolver los errores para alcanzar la disponibilidad minima de {min_avail:.1f}% (actual: {availability:.2f}%). Revisar logs del servidor, validaciones de datos y manejo de excepciones.\n\n"
        elif error_rate > 0:
            recs += "2. Investigar los errores detectados durante la prueba para mantener la disponibilidad dentro del criterio.\n\n"
        else:
            recs += "2. Validar el comportamiento del sistema bajo carga extrema para identificar el punto de quiebre.\n\n"

        recs += "PRIORIDAD ALTA:\n\n"
        recs += "3. Implementar cache en las transacciones mas frecuentes para reducir la carga en la base de datos y mejorar tiempos de respuesta.\n\n"
        recs += "4. Revisar la configuracion de connection pooling y thread pooling del servidor de aplicaciones para optimizar el uso de recursos.\n\n"

        recs += "PRIORIDAD MEDIA:\n\n"
        recs += "5. Ejecutar pruebas de estres incrementando la carga gradualmente hasta encontrar el punto de quiebre del sistema.\n\n"
        recs += "6. Configurar monitoreo de recursos (CPU, memoria, disco, red) durante las pruebas para correlacionar degradaciones con el consumo de infraestructura."

        return recs

    @staticmethod
    def analyze_redirects(redirect_count, main_samples):
        """Generate fallback redirect analysis."""
        pct = (redirect_count / main_samples * 100) if main_samples > 0 else 0
        return (
            f"Se detectaron {redirect_count:,} redirecciones HTTP que representan el {pct:.1f}% del trafico principal ({main_samples:,} solicitudes). "
            f"Las redirecciones agregan latencia adicional al flujo del usuario. "
            f"Se recomienda evaluar si estas redirecciones son necesarias o si pueden eliminarse para optimizar los tiempos de respuesta."
        )


# ==================== INSIGHTS HELPERS ====================

def prepare_insights_for_prompt(summary_df) -> Dict:
    """
    Pre-procesa datos del summary DataFrame en insights estructurados
    clasificados por tiers de performance.
    """
    tiers = {
        'excellent': [],
        'acceptable': [],
        'degraded': [],
        'critical': [],
    }

    all_transactions = []
    high_variability = []
    error_transactions = []

    for _, row in summary_df.iterrows():
        tx = {
            'name': row['label'],
            'samples': int(row['muestras']),
            'errors': int(row['errores']),
            'error_rate': float(row['tasa_error']),
            'avg': float(row['promedio']),
            'p90': float(row.get('p90', 0)),
            'p95': float(row.get('p95', 0)),
            'p99': float(row.get('p99', 0)),
            'min': float(row['min']),
            'max': float(row['max']),
            'tps': float(row.get('rendimiento', 0)),
        }
        all_transactions.append(tx)

        avg = tx['avg']
        if avg < TIER_EXCELLENT:
            tiers['excellent'].append(tx)
        elif avg < TIER_ACCEPTABLE:
            tiers['acceptable'].append(tx)
        elif avg < TIER_DEGRADED:
            tiers['degraded'].append(tx)
        else:
            tiers['critical'].append(tx)

        if tx['avg'] > 0 and tx['p99'] / tx['avg'] > 3:
            high_variability.append(tx)

        if tx['errors'] > 0:
            error_transactions.append(tx)

    sorted_by_avg = sorted(all_transactions, key=lambda x: x['avg'])
    best = sorted_by_avg[0] if sorted_by_avg else None
    worst = sorted_by_avg[-1] if sorted_by_avg else None

    insights = {
        'tiers': tiers,
        'total_transactions': len(all_transactions),
        'all_transactions': all_transactions,
        'best_transaction': best,
        'worst_transaction': worst,
        'high_variability': high_variability,
        'error_transactions': error_transactions,
    }

    logger.info(
        f"Insights preparados: {len(all_transactions)} transacciones total - "
        f"excelente={len(tiers['excellent'])}, aceptable={len(tiers['acceptable'])}, "
        f"degradado={len(tiers['degraded'])}, critico={len(tiers['critical'])}, "
        f"alta variabilidad={len(high_variability)}, con errores={len(error_transactions)}"
    )

    return insights


def build_tier_summary(insights: Dict) -> str:
    """Builds a formatted summary grouped by performance tiers."""
    tiers = insights['tiers']
    lines = []

    lines.append(f"TOTAL DE TRANSACCIONES ANALIZADAS: {insights['total_transactions']}")
    lines.append("")

    if tiers['critical']:
        lines.append(f"=== TIER CRITICO (>{TIER_DEGRADED}ms) - {len(tiers['critical'])} transacciones ===")
        for tx in sorted(tiers['critical'], key=lambda x: -x['avg']):
            lines.append(
                f"  {tx['name']}: avg={tx['avg']:.0f}ms, P95={tx['p95']:.0f}ms, "
                f"P99={tx['p99']:.0f}ms, errores={tx['errors']}, TPS={tx['tps']:.2f}"
            )
        lines.append("")

    if tiers['degraded']:
        lines.append(f"=== TIER DEGRADADO ({TIER_ACCEPTABLE}-{TIER_DEGRADED}ms) - {len(tiers['degraded'])} transacciones ===")
        for tx in sorted(tiers['degraded'], key=lambda x: -x['avg']):
            lines.append(
                f"  {tx['name']}: avg={tx['avg']:.0f}ms, P95={tx['p95']:.0f}ms, "
                f"P99={tx['p99']:.0f}ms, errores={tx['errors']}, TPS={tx['tps']:.2f}"
            )
        lines.append("")

    if tiers['acceptable']:
        lines.append(f"=== TIER ACEPTABLE ({TIER_EXCELLENT}-{TIER_ACCEPTABLE}ms) - {len(tiers['acceptable'])} transacciones ===")
        for tx in sorted(tiers['acceptable'], key=lambda x: -x['avg']):
            lines.append(
                f"  {tx['name']}: avg={tx['avg']:.0f}ms, P95={tx['p95']:.0f}ms, "
                f"P99={tx['p99']:.0f}ms, errores={tx['errors']}, TPS={tx['tps']:.2f}"
            )
        lines.append("")

    if tiers['excellent']:
        lines.append(f"=== TIER EXCELENTE (<{TIER_EXCELLENT}ms) - {len(tiers['excellent'])} transacciones ===")
        for tx in sorted(tiers['excellent'], key=lambda x: -x['avg']):
            lines.append(
                f"  {tx['name']}: avg={tx['avg']:.0f}ms, P95={tx['p95']:.0f}ms, "
                f"P99={tx['p99']:.0f}ms, errores={tx['errors']}, TPS={tx['tps']:.2f}"
            )
        lines.append("")

    if insights['high_variability']:
        lines.append(f"=== ALERTA: ALTA VARIABILIDAD (P99/avg > 3x) - {len(insights['high_variability'])} transacciones ===")
        for tx in insights['high_variability']:
            ratio = tx['p99'] / tx['avg'] if tx['avg'] > 0 else 0
            lines.append(
                f"  {tx['name']}: avg={tx['avg']:.0f}ms vs P99={tx['p99']:.0f}ms (ratio {ratio:.1f}x)"
            )
        lines.append("")

    best = insights['best_transaction']
    worst = insights['worst_transaction']
    if best and worst:
        lines.append(f"MEJOR TRANSACCION: {best['name']} (avg={best['avg']:.0f}ms)")
        lines.append(f"PEOR TRANSACCION: {worst['name']} (avg={worst['avg']:.0f}ms)")
        if best['avg'] > 0:
            lines.append(f"RATIO PEOR/MEJOR: {worst['avg']/best['avg']:.1f}x")

    return "\n".join(lines)


# ==================== GEMINI ANALYZER ====================

class GeminiAnalyzer:
    """AI Analyzer supporting Gemini and OpenAI providers."""

    # Usage counters (in-memory, synced to DB by upload endpoint)
    _total_requests: int = 0
    _total_errors: int = 0

    # Circuit breaker: after first rate-limit failure, skip all subsequent calls
    _circuit_open: bool = False

    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-flash", api_key: str = ""):
        self.provider = provider or DEFAULT_PROVIDER
        self.model_name = model_name or MODEL_NAME
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        # Reset circuit breaker on new instance
        GeminiAnalyzer._circuit_open = False

        if not self._api_key:
            raise ValueError("API key no configurada para el proveedor de IA")

        # Log key prefix for debugging (never log full key)
        logger.info(f"AIAnalyzer: using key prefix={self._api_key[:10]}...")

        if self.provider == "gemini":
            genai.configure(api_key=self._api_key, transport="rest")
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=GENERATION_CONFIG,
            )
            logger.info(f"AIAnalyzer v4.0 iniciado: provider=gemini, model={self.model_name}")
        elif self.provider == "openai":
            if OpenAI is None:
                raise ValueError("SDK de OpenAI no disponible: falta el paquete 'openai'")
            self._openai_client = OpenAI(api_key=self._api_key)
            logger.info(f"AIAnalyzer v4.0 iniciado: provider=openai, model={self.model_name}")
        else:
            raise ValueError(f"Proveedor no soportado: {self.provider}")

    def _generate(self, prompt: str, section_name: str = "unknown", max_retries: int = 3) -> Optional[str]:
        """Call AI API with retry logic. Returns None on failure to trigger fallback.
        Circuit breaker: if AI was rate-limited once, skip all subsequent calls immediately."""

        # Circuit breaker — skip immediately if API already proven unavailable
        if GeminiAnalyzer._circuit_open:
            logger.info(f"AI CIRCUIT OPEN: skipping {section_name} (using fallback)")
            GeminiAnalyzer._total_errors += 1
            return None

        logger.info(f"AI CALL: provider={self.provider}, model={self.model_name}, section={section_name}, prompt_len={len(prompt)}")
        GeminiAnalyzer._total_requests += 1

        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    response = self.model.generate_content(prompt)
                    result = response.text
                elif self.provider == "openai":
                    response = self._openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=_openai_max_tokens_for(self.model_name),
                        temperature=GENERATION_CONFIG["temperature"],
                    )
                    result = response.choices[0].message.content if response.choices else None
                    if not result:
                        GeminiAnalyzer._total_errors += 1
                        return None
                else:
                    GeminiAnalyzer._total_errors += 1
                    return None

                result = sanitize_ai_text(result)
                logger.info(f"AI OK: section={section_name}, response_len={len(result)}, preview={result[:80]}")
                return result

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower() or "resource" in error_str.lower():
                    wait_time = min((attempt + 1) * 5, 15)
                    logger.warning(f"AI RATE LIMITED (attempt {attempt+1}/{max_retries}) for {section_name}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"AI ERROR for {section_name}: {error_str}")
                    GeminiAnalyzer._total_errors += 1
                    return None

        # All retries exhausted — open circuit breaker for remaining calls
        logger.warning(f"AI UNAVAILABLE: {section_name} - max retries exceeded. CIRCUIT BREAKER OPEN — all remaining calls will use fallback.")
        GeminiAnalyzer._circuit_open = True
        GeminiAnalyzer._total_errors += 1
        return None

    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        category: str,
        title: str = "",
        description: str = "",
        attachment_type: str = "monitoring",
    ) -> str:
        """Analyze an image using Gemini Vision (multimodal) with OCR fallback."""
        import base64

        type_label = "monitoreo de performance" if attachment_type == "monitoring" else "evidencia de pruebas de performance"
        ctx_parts = [f"Categoria: {category}"]
        if title:
            ctx_parts.append(f"Titulo: {title}")
        if description:
            ctx_parts.append(f"Descripcion del usuario: {description}")
        context = "\n".join(ctx_parts)

        if attachment_type == "monitoring":
            instructions = (
                "Describe lo que ves en la imagen de forma precisa y tecnica. "
                "Si es una grafica identifica tendencias, picos, valores min/max y promedios aproximados. "
                "Si es un dashboard describe cada metrica visible y su estado. "
                "Si hay umbrales o alertas visibles mencionalos. "
                "Relaciona los datos con el rendimiento del sistema."
            )
        else:
            instructions = (
                "Describe lo que muestra la imagen de forma precisa. "
                "Si es un error identifica tipo, codigo HTTP, mensaje y stack trace si es visible. "
                "Si es un log extrae las lineas relevantes. "
                "Clasifica la severidad (critico, mayor, menor, informativo). "
                "Sugiere posible causa raiz basandote en lo visible."
            )

        prompt = (
            f"Analiza esta imagen de {type_label}.\n{context}\n\n"
            f"INSTRUCCIONES:\n{instructions}\n"
            f"Escribe en espanol profesional colombiano. "
            f"Parrafos narrativos de 3-5 oraciones, sin markdown, sin bullets, sin asteriscos. "
            f"Maximo 300 palabras. Se especifico con los datos que ves."
        )

        # ---- Multimodal analysis by provider ----
        if self.provider == "gemini":
            try:
                image_part = {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("utf-8")}
                response = self.model.generate_content(
                    [prompt, image_part],
                    generation_config={"max_output_tokens": 1024, "temperature": 0.3},
                )
                if response and response.text:
                    result = sanitize_ai_text(response.text)
                    logger.info(f"Gemini Vision OK: {len(result)} chars for {category}/{title}")
                    return result
            except Exception as e:
                logger.warning(f"Gemini Vision failed for {category}/{title}: {e}")

        elif self.provider == "openai":
            try:
                b64_data = base64.b64encode(image_bytes).decode("utf-8")
                response = self._openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime_type};base64,{b64_data}"
                            }}
                        ]
                    }],
                    max_tokens=min(_openai_max_tokens_for(self.model_name), 1024),
                    temperature=0.3,
                )
                text = response.choices[0].message.content if response.choices else None
                if text:
                    result = sanitize_ai_text(text)
                    logger.info(f"OpenAI Vision OK: {len(result)} chars for {category}/{title}")
                    return result
            except Exception as e:
                logger.warning(f"OpenAI Vision failed for {category}/{title}: {e}")

        # ---- Fallback: OCR + text analysis ----
        logger.info(f"Falling back to OCR for {category}/{title}")
        return self._analyze_image_ocr_fallback(image_bytes, category, title, description, attachment_type)

    def _analyze_image_ocr_fallback(
        self, image_bytes: bytes, category: str, title: str, description: str, attachment_type: str
    ) -> str:
        """Fallback: extract text via OCR then analyze with Gemini text model."""
        import io
        extracted_text = ""

        try:
            from PIL import Image
            import pytesseract
            image = Image.open(io.BytesIO(image_bytes))
            extracted_text = pytesseract.image_to_string(image, lang="spa+eng").strip()
        except Exception as e:
            logger.warning(f"OCR failed: {e}")

        if not extracted_text:
            extracted_text = "(No se pudo extraer texto de la imagen)"

        type_label = "monitoreo" if attachment_type == "monitoring" else "evidencia"
        prompt = (
            f"Se extrajo el siguiente texto de una imagen de {type_label} de pruebas de performance usando OCR.\n"
            f"Categoria: {category}\n"
            f"{f'Titulo: {title}' if title else ''}\n"
            f"{f'Descripcion: {description}' if description else ''}\n\n"
            f"Texto extraido:\n---\n{extracted_text}\n---\n\n"
            f"Genera un analisis tecnico basado en el texto extraido. "
            f"Espanol profesional, parrafos narrativos, sin markdown. Maximo 200 palabras. "
            f"Si el texto es pobre o vacio, indica que no fue posible analizar el contenido."
        )

        result = self._generate(prompt, section_name=f"ocr_fallback_{category}")
        if result:
            return result
        return (
            f"No fue posible analizar esta imagen automaticamente. "
            f"Se recomienda agregar una descripcion manual. "
            f"Categoria: {category}. Titulo: {title or 'Sin titulo'}."
        )

    def _build_test_type_context(self, test_type: str) -> str:
        """Construye contexto del tipo de prueba"""
        desc = TEST_TYPE_DESCRIPTIONS.get(test_type, f"Tipo de prueba: {test_type}")
        return f"\nTIPO DE PRUEBA: {desc}\n"

    def _build_transactions_table(self, summary_df) -> str:
        """Construye tabla formateada de TODAS las transacciones (sin limite)"""
        lines = []
        lines.append("| Transaccion | Muestras | Errores | Error% | Promedio(ms) | P95(ms) | P99(ms) | Min(ms) | Max(ms) | TPS |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        logger.info(f"Construyendo tabla con {len(summary_df)} transacciones")
        for _, row in summary_df.iterrows():
            lines.append(
                f"| {row['label']} | {int(row['muestras']):,} | {int(row['errores'])} | "
                f"{row['tasa_error']:.2f}% | {row['promedio']:.0f} | {row['p95']:.0f} | "
                f"{row['p99']:.0f} | {row['min']:.0f} | {row['max']:.0f} | "
                f"{row['rendimiento']:.2f} |"
            )
        return "\n".join(lines)

    def analyze_summary_table(
        self,
        summary_df,
        metrics: Dict,
        test_type: str = "load",
        acceptance_criteria: Optional[Dict] = None,
        insights: Optional[Dict] = None,
        test_date: str = "N/A",
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Analisis de la tabla resumen con datos completos por transaccion"""
        try:
            test_ctx = self._build_test_type_context(test_type)
            table = self._build_transactions_table(summary_df)

            if insights is None:
                insights = prepare_insights_for_prompt(summary_df)

            tier_summary = build_tier_summary(insights)

            criteria_text = ""
            if acceptance_criteria:
                criteria_text = "\n\nCRITERIOS DE ACEPTACION:\n"
                if acceptance_criteria.get("concurrency"):
                    criteria_text += f"- Concurrencia esperada: {acceptance_criteria['concurrency']} usuarios\n"
                if acceptance_criteria.get("response_time"):
                    criteria_text += f"- Tiempo de respuesta maximo aceptable: {acceptance_criteria['response_time']}ms\n"
                if acceptance_criteria.get("availability"):
                    criteria_text += f"- Disponibilidad minima: {acceptance_criteria['availability']}%\n"

            logger.info(f"Enviando {len(summary_df)} transacciones a Gemini para analisis de tabla resumen")

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

TABLA DE RESULTADOS POR TRANSACCION:
{table}

CLASIFICACION POR TIERS DE PERFORMANCE:
{tier_summary}

RESUMEN GLOBAL:
- Total de muestras: {metrics['total_requests']:,}
- Tasa de error global: {metrics['error_rate']:.2f}%
- Tiempo promedio global: {metrics['avg_response_time']:.2f}ms
- Mediana: {metrics.get('median_response_time', 0):.2f}ms
- P90: {metrics['p90_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- P99: {metrics['p99_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s
- Duracion: {metrics['duration_seconds']:.0f}s{criteria_text}

Analiza esta tabla de resultados. Escribe un analisis NARRATIVO y CONCISO en espanol (maximo 250 palabras).
NO repitas datos que ya estan en la tabla, enfocate en INTERPRETACION.

ESTRUCTURA (parrafos breves de 2-3 oraciones):

1. VISION GENERAL: {insights['total_transactions']} transacciones, distribucion por tiers, veredicto general.

2. PROBLEMAS: Transacciones criticas/degradadas por nombre con datos. Variabilidad alta ({len(insights['high_variability'])} transacciones). Errores ({len(insights['error_transactions'])} con errores).

3. VEREDICTO: Listo para produccion? Prioridades de mejora.

Menciona TODAS las {insights['total_transactions']} transacciones por nombre de forma compacta.
"""
            return self._generate(prompt, section_name="summary_table")

        except Exception as e:
            logger.error(f"GEMINI FAILED for summary_table: {str(e)}")
            return None

    def analyze_errors(
        self,
        error_data: List[Dict],
        total_requests: int,
        test_type: str = "load",
        test_date: str = "N/A",
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Analisis detallado de errores por transaccion y codigo HTTP"""
        if not error_data or len(error_data) == 0:
            return "No se detectaron errores en la ejecucion. El sistema respondio correctamente a todas las solicitudes."

        try:
            test_ctx = self._build_test_type_context(test_type)
            total_errors = sum(item['count'] for item in error_data)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

            lines = []
            lines.append("| Transaccion | Errores | Codigo HTTP | Mensaje | % del Total |")
            lines.append("|---|---|---|---|---|")
            for item in error_data:
                pct = (item['count'] / total_requests * 100) if total_requests > 0 else 0
                lines.append(
                    f"| {item['label']} | {item['count']:,} | {item.get('code', 'N/A')} | "
                    f"{item.get('message', 'N/A')} | {pct:.2f}% |"
                )
            logger.info(f"Enviando {len(error_data)} entradas de error a Gemini")
            errors_table = "\n".join(lines)

            error_by_code = {}
            for item in error_data:
                code = str(item.get('code', 'N/A'))
                if code not in error_by_code:
                    error_by_code[code] = {'count': 0, 'transactions': []}
                error_by_code[code]['count'] += item['count']
                error_by_code[code]['transactions'].append(item['label'])

            error_classification = "\nCLASIFICACION DE ERRORES POR CODIGO:\n"
            for code, info in sorted(error_by_code.items()):
                code_str = str(code)
                category = "Exito" if code_str.startswith('2') else \
                           "Redireccion" if code_str.startswith('3') else \
                           "Error Cliente" if code_str.startswith('4') else \
                           "Error Servidor" if code_str.startswith('5') else "Otro"
                error_classification += (
                    f"  HTTP {code} ({category}): {info['count']:,} errores en "
                    f"{len(info['transactions'])} transacciones: {', '.join(info['transactions'])}\n"
                )

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

ERRORES DETECTADOS:
{errors_table}
{error_classification}

CONTEXTO:
- Total de errores: {total_errors:,}
- Tasa de error global: {error_rate:.2f}%
- Total de requests: {total_requests:,}
- Transacciones con errores: {len(error_data)}
- Codigos HTTP distintos: {len(error_by_code)}

Escribe un analisis NARRATIVO y CONCISO de los errores (maximo 200 palabras). Menciona CADA transaccion con error POR NOMBRE.
NO repitas datos que ya estan en la tabla, enfocate en INTERPRETACION.

1. Panorama: total errores, porcentaje, codigos HTTP con sus transacciones.
2. Causas probables e impacto en usuarios.
3. Severidad (critico/alto/medio/bajo) y acciones inmediatas.
"""
            return self._generate(prompt, section_name="errors")

        except Exception as e:
            logger.error(f"GEMINI FAILED for errors: {str(e)}")
            return None

    def analyze_chart(
        self,
        chart_type: str,
        data_summary: str,
        test_type: str = "load",
        insights: Optional[Dict] = None,
        test_date: str = "N/A",
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Analisis de graficos individuales con contexto del tipo de prueba"""
        try:
            test_ctx = self._build_test_type_context(test_type)

            chart_names = {
                'response_times': 'Tiempos de Respuesta por Transaccion',
                'response_time_over_time': 'Tiempo de Respuesta en el Tiempo',
                'throughput': 'Throughput Over Time',
                'latency': 'Latencia Over Time',
                'error_rate': 'Tasa de Error Over Time',
                'codes_per_second': 'Codigos HTTP por Segundo',
                'transactions_per_second': 'Transacciones por Segundo (TPS)',
                'active_threads': 'Hilos/Usuarios Activos',
            }

            tier_context = ""
            if chart_type == 'response_times' and insights:
                tier_context = f"\n\nCLASIFICACION POR TIERS:\n{build_tier_summary(insights)}\n"

            chart_specific_instructions = {
                'response_times': f"""Los datos incluyen {insights['total_transactions'] if insights else 'todas las'} transacciones por tier.
Menciona CADA transaccion por nombre. Cubre: distribucion por tiers, mas rapida vs mas lenta, variabilidad P99/avg, impacto en produccion.""",

                'response_time_over_time': """Cubre: estabilidad temporal (mejora/degrada), fases ramp-up/meseta/cool-down, picos de latencia y sus causas, tendencia general.""",

                'throughput': """Cubre: capacidad maxima req/s, consistencia, periodos de caida, saturacion, headroom vs carga esperada.""",

                'latency': """Cubre: latencia promedio y variacion, proporcion respecto al tiempo total, picos que indiquen problemas de red.""",

                'error_rate': """Cubre: patron de errores (constantes/intermitentes/crecientes), correlacion con carga, recuperacion del sistema, disponibilidad efectiva.""",

                'codes_per_second': """Cubre: distribucion de codigos HTTP, patron temporal de errores, significado de cada codigo, redirecciones 3xx.""",

                'transactions_per_second': """Cubre: distribucion de carga entre transacciones, estabilidad TPS, balance de carga, cuellos de botella.""",

                'active_threads': """Cubre: patron de concurrencia (ramp-up/meseta/ramp-down), usuarios maximos, degradacion al escalar, correlacion con tiempos de respuesta.""",
            }

            chart_name = chart_names.get(chart_type, chart_type)
            specific = chart_specific_instructions.get(chart_type, "Analiza los datos de esta grafica en detalle.")

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

DATOS DE LA GRAFICA "{chart_name}":
{data_summary}
{tier_context}
Analiza esta grafica de {chart_name}. Escribe un analisis NARRATIVO y CONCISO en espanol (maximo 200 palabras).
NO repitas datos que ya estan en la grafica, enfocate en INTERPRETACION.

{specific}

Cierra con una oracion sobre el impacto en produccion.
"""
            return self._generate(prompt, section_name=f"chart_{chart_type}")

        except Exception as e:
            logger.error(f"GEMINI FAILED for chart_{chart_type}: {str(e)}")
            return None

    def analyze_redirects(
        self,
        redirect_summary_df,
        main_metrics: Dict,
        test_type: str = "load",
        test_date: str = "N/A",
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Analisis de redirecciones separadas del trafico principal"""
        try:
            test_ctx = self._build_test_type_context(test_type)
            table = self._build_transactions_table(redirect_summary_df)

            logger.info(f"Enviando {len(redirect_summary_df)} redirecciones a Gemini")

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Se han detectado REDIRECCIONES HTTP separadas del trafico principal.

TABLA DE REDIRECCIONES:
{table}

CONTEXTO DEL TRAFICO PRINCIPAL:
- Muestras principales: {main_metrics.get('total_main_samples', 0):,}
- Muestras de redireccion: {main_metrics.get('total_redirects', 0):,}
- Labels de redireccion: {', '.join(main_metrics.get('redirect_labels', []))}

Escribe un analisis NARRATIVO y CONCISO (maximo 200 palabras). Menciona CADA redireccion por nombre.
NO repitas datos que ya estan en la tabla, enfocate en INTERPRETACION.

1. Cuantas redirecciones, porcentaje del trafico, patron de nombres.
2. Tiempos de respuesta vs transacciones principales. Agregan latencia significativa?
3. Esperadas o problematicas? Recomendacion: optimizar, eliminar o aceptar.
"""
            return self._generate(prompt, section_name="redirects")

        except Exception as e:
            logger.error(f"GEMINI FAILED for redirects: {str(e)}")
            return None

    def generate_conclusions(
        self,
        metrics: Dict,
        ai_analysis_summary: str,
        ai_analysis_errors: str,
        ai_analysis_response_times: str,
        ai_analysis_response_time_over_time: str,
        ai_analysis_throughput: str,
        ai_analysis_latency: str,
        ai_analysis_error_rate: str,
        ai_analysis_codes_per_second: str,
        ai_analysis_transactions_per_second: str,
        ai_analysis_active_threads: str,
        ai_analysis_redirects: str = "",
        test_type: str = "load",
        insights: Optional[Dict] = None,
        test_date: str = "N/A",
        acceptance_criteria: Optional[Dict] = None,
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Sintetiza TODOS los analisis en conclusiones ejecutivas"""
        try:
            test_ctx = self._build_test_type_context(test_type)

            redirect_section = ""
            if ai_analysis_redirects:
                redirect_section = f"""
11. REDIRECCIONES:
{ai_analysis_redirects}
"""

            insights_summary = ""
            if insights:
                tiers = insights['tiers']
                insights_summary = f"""
RESUMEN DE INSIGHTS PRE-CLASIFICADOS:
- Transacciones en tier CRITICO: {len(tiers['critical'])} ({', '.join(tx['name'] for tx in tiers['critical']) if tiers['critical'] else 'ninguna'})
- Transacciones en tier DEGRADADO: {len(tiers['degraded'])} ({', '.join(tx['name'] for tx in tiers['degraded']) if tiers['degraded'] else 'ninguna'})
- Transacciones en tier ACEPTABLE: {len(tiers['acceptable'])} ({', '.join(tx['name'] for tx in tiers['acceptable']) if tiers['acceptable'] else 'ninguna'})
- Transacciones en tier EXCELENTE: {len(tiers['excellent'])} ({', '.join(tx['name'] for tx in tiers['excellent']) if tiers['excellent'] else 'ninguna'})
- Transacciones con ALTA VARIABILIDAD: {len(insights['high_variability'])} ({', '.join(tx['name'] for tx in insights['high_variability']) if insights['high_variability'] else 'ninguna'})
- Transacciones con ERRORES: {len(insights['error_transactions'])} ({', '.join(tx['name'] for tx in insights['error_transactions']) if insights['error_transactions'] else 'ninguna'})
"""

            # Build acceptance criteria section for Gemini
            criteria_section = ""
            if acceptance_criteria and not acceptance_criteria.get('raw_text'):
                verdict = compute_verdict(metrics, acceptance_criteria)
                criteria_section = f"""
CRITERIOS DE ACEPTACION:
- Concurrencia esperada: {acceptance_criteria.get('concurrency', 'N/A')} usuarios
- Tiempo de respuesta maximo: {acceptance_criteria.get('response_time', 'N/A')}ms
- Disponibilidad minima: {acceptance_criteria.get('availability', 'N/A')}%
- VEREDICTO CALCULADO: {verdict}

IMPORTANTE: Tu primera conclusion DEBE ser el veredicto "{verdict}" comparando las metricas contra estos criterios.
Si el veredicto es NO APTO, explica que criterios se incumplen.
Si es APTO CON RESERVAS, explica que metricas estan cerca del limite.
"""

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Has completado el analisis de una prueba de performance JMeter. Sintetiza TODO en conclusiones ejecutivas.

METRICAS CLAVE:
- Total requests: {metrics['total_requests']:,}
- Error rate: {metrics['error_rate']:.2f}%
- Avg response time: {metrics['avg_response_time']:.2f}ms
- P90: {metrics['p90_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- P99: {metrics['p99_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s
- Duracion: {metrics['duration_seconds']:.0f}s
- Muestras principales: {metrics.get('total_main_samples', metrics['total_requests']):,}
- Redirecciones: {metrics.get('total_redirects', 0):,}
{insights_summary}{criteria_section}
ANALISIS REALIZADOS:

1. TABLA RESUMEN:
{ai_analysis_summary}

2. ERRORES:
{ai_analysis_errors}

3. RESPONSE TIMES POR TRANSACCION:
{ai_analysis_response_times}

4. RESPONSE TIME OVER TIME:
{ai_analysis_response_time_over_time}

5. THROUGHPUT:
{ai_analysis_throughput}

6. LATENCY:
{ai_analysis_latency}

7. ERROR RATE:
{ai_analysis_error_rate}

8. CODIGOS HTTP:
{ai_analysis_codes_per_second}

9. TPS:
{ai_analysis_transactions_per_second}

10. ACTIVE THREADS:
{ai_analysis_active_threads}
{redirect_section}
Escribe 6 conclusiones ejecutivas como parrafos completos. Maximo 600 palabras total.
Cubre: veredicto general, tiempos criticos, errores, throughput, estabilidad, acciones prioritarias.

Cada conclusion es un PARRAFO COMPLETO de 3-5 oraciones numerado.
Menciona transacciones especificas POR NOMBRE con datos.

CADA conclusion debe sintetizar multiples analisis y nombrar transacciones especificas.
"""
            return self._generate(prompt, section_name="conclusions")

        except Exception as e:
            logger.error(f"GEMINI FAILED for conclusions: {str(e)}")
            return None

    def generate_recommendations(
        self,
        metrics: Dict,
        ai_analysis_summary: str,
        ai_analysis_errors: str,
        ai_analysis_response_times: str,
        ai_analysis_response_time_over_time: str,
        ai_analysis_throughput: str,
        ai_analysis_latency: str,
        ai_analysis_error_rate: str,
        ai_analysis_codes_per_second: str,
        ai_analysis_transactions_per_second: str,
        ai_analysis_active_threads: str,
        ai_analysis_redirects: str = "",
        test_type: str = "load",
        insights: Optional[Dict] = None,
        test_date: str = "N/A",
        acceptance_criteria: Optional[Dict] = None,
        metric_unit: str = "TPS",
    ) -> Optional[str]:
        """Genera recomendaciones tecnicas basadas en TODOS los analisis"""
        try:
            test_ctx = self._build_test_type_context(test_type)

            redirect_section = ""
            if ai_analysis_redirects:
                redirect_section = f"""
REDIRECCIONES:
{ai_analysis_redirects}
"""

            action_items = ""
            if insights:
                tiers = insights['tiers']
                items = []
                if tiers['critical']:
                    items.append(f"CRITICO - {len(tiers['critical'])} transacciones sobre {TIER_DEGRADED}ms: {', '.join(tx['name'] for tx in tiers['critical'])}")
                if tiers['degraded']:
                    items.append(f"DEGRADADO - {len(tiers['degraded'])} transacciones entre {TIER_ACCEPTABLE}-{TIER_DEGRADED}ms: {', '.join(tx['name'] for tx in tiers['degraded'])}")
                if insights['high_variability']:
                    items.append(f"ALTA VARIABILIDAD - {len(insights['high_variability'])} transacciones con P99/avg > 3x: {', '.join(tx['name'] for tx in insights['high_variability'])}")
                if insights['error_transactions']:
                    items.append(f"CON ERRORES - {len(insights['error_transactions'])} transacciones: {', '.join(tx['name'] for tx in insights['error_transactions'])}")
                if items:
                    action_items = "\nPROBLEMAS IDENTIFICADOS PARA RECOMENDACIONES:\n" + "\n".join(f"  {i}" for i in items) + "\n"

            # Build acceptance criteria context for recommendations
            criteria_section = ""
            if acceptance_criteria and not acceptance_criteria.get('raw_text'):
                criteria_section = f"""
CRITERIOS DE ACEPTACION DEL CLIENTE:
- Concurrencia esperada: {acceptance_criteria.get('concurrency', 'N/A')} usuarios
- Tiempo de respuesta maximo: {acceptance_criteria.get('response_time', 'N/A')}ms
- Disponibilidad minima: {acceptance_criteria.get('availability', 'N/A')}%

Las recomendaciones DEBEN estar orientadas a cumplir estos criterios especificos.
"""

            prompt = f"""{SYSTEM_PROMPT}{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Genera recomendaciones tecnicas accionables basadas en los resultados de la prueba.

METRICAS CLAVE:
- Total requests: {metrics['total_requests']:,}
- Error rate: {metrics['error_rate']:.2f}%
- Avg time: {metrics['avg_response_time']:.2f}ms
- P95: {metrics['p95_response_time']:.2f}ms
- P99: {metrics['p99_response_time']:.2f}ms
- Throughput: {metrics['throughput']:.2f} req/s
{action_items}{criteria_section}
HALLAZGOS DE LOS ANALISIS:

TABLA & TRANSACCIONES:
{ai_analysis_summary}

ERRORES:
{ai_analysis_errors}

PATRONES DE TIEMPOS:
{ai_analysis_response_times}
{ai_analysis_response_time_over_time}

CAPACIDAD:
{ai_analysis_throughput}
{ai_analysis_transactions_per_second}

INFRAESTRUCTURA:
{ai_analysis_latency}
{ai_analysis_active_threads}
{redirect_section}
Escribe recomendaciones organizadas por prioridad. Maximo 600 palabras total.
CRITICAS (2-3): Resolver antes de produccion.
ALTAS (2-3): Resolver pronto.
MEDIAS (1-2): Optimizaciones opcionales.
Cada recomendacion: parrafo de 3-4 oraciones con problema, accion y transacciones afectadas.

Cada recomendacion debe nombrar las transacciones afectadas con datos.
"""
            return self._generate(prompt, section_name="recommendations")

        except Exception as e:
            logger.error(f"GEMINI FAILED for recommendations: {str(e)}")
            return None


# Instancia global - lazy initialization
_analyzer_instance: Optional[GeminiAnalyzer] = None
_analyzer_config_key: str = ""


def get_gemini_analyzer(
    provider: str = "",
    model_name: str = "",
    api_key: str = "",
) -> GeminiAnalyzer:
    """Obtener instancia de GeminiAnalyzer (lazy init, recreates on config change)"""
    global _analyzer_instance, _analyzer_config_key

    config_key = f"{provider}:{model_name}:{api_key[:8] if api_key else ''}"

    if _analyzer_instance is None or (config_key and config_key != _analyzer_config_key):
        _analyzer_instance = GeminiAnalyzer(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
        )
        _analyzer_config_key = config_key

    return _analyzer_instance


async def load_ai_config_from_db(db) -> dict:
    """
    Load AI config from database. Returns dict with provider, model_name, api_key.
    Falls back to env vars GEMINI_API_KEY / GEMINI_MODEL if no DB config exists.
    Also checks daily/monthly limits and auto-resets counters.
    """
    from sqlalchemy import select
    from app.db.models.ai_config import AIConfig
    from cryptography.fernet import Fernet
    from app.core.config import settings
    from datetime import date
    import base64

    try:
        result = await db.execute(select(AIConfig).limit(1))
        config = result.scalar_one_or_none()

        if config is None:
            # Fallback to env vars (backwards compatibility)
            env_key = os.getenv("GEMINI_API_KEY", "") or (settings.GEMINI_API_KEY if hasattr(settings, 'GEMINI_API_KEY') else "")
            env_model = os.getenv("GEMINI_MODEL", "") or (settings.GEMINI_MODEL if hasattr(settings, 'GEMINI_MODEL') else "gemini-2.5-flash")
            if env_key:
                logger.info(f"Usando API key desde ENV (no hay config en DB), key_prefix={env_key[:10]}...")
                return {
                    "provider": "gemini",
                    "model_name": env_model or "gemini-2.5-flash",
                    "api_key": env_key,
                }
            logger.warning("No hay API key configurada ni en DB ni en ENV")
            return {}

        if not config.is_active:
            logger.warning("AI config en DB esta desactivada (is_active=False), no se usara")
            return {}

        # Auto-reset daily/monthly counters
        today = date.today()
        if config.last_reset_daily is None or config.last_reset_daily < today:
            config.daily_requests_used = 0
            config.last_reset_daily = today

        first_of_month = today.replace(day=1)
        if config.last_reset_monthly is None or config.last_reset_monthly < first_of_month:
            config.monthly_requests_used = 0
            config.last_reset_monthly = first_of_month

        # Check limits
        daily_limit = config.daily_request_limit or 1000
        monthly_limit = config.monthly_request_limit or 20000
        if (config.daily_requests_used or 0) >= daily_limit:
            logger.warning(f"AI daily limit reached: {config.daily_requests_used}/{daily_limit}")
            return {"limit_reached": "daily", "provider": config.provider}
        if (config.monthly_requests_used or 0) >= monthly_limit:
            logger.warning(f"AI monthly limit reached: {config.monthly_requests_used}/{monthly_limit}")
            return {"limit_reached": "monthly", "provider": config.provider}

        if not config.api_key_encrypted:
            # No key in DB, try env var fallback
            env_key = os.getenv("GEMINI_API_KEY", "") or (settings.GEMINI_API_KEY if hasattr(settings, 'GEMINI_API_KEY') else "")
            if env_key:
                logger.info(f"Usando API key desde ENV (config en DB sin api_key_encrypted), key_prefix={env_key[:10]}...")
                return {
                    "provider": config.provider or "gemini",
                    "model_name": config.model_name or "gemini-2.5-flash",
                    "api_key": env_key,
                }
            logger.warning("No hay API key: DB config sin api_key_encrypted y ENV vacio")
            return {}

        # Decrypt API key
        key = settings.FERNET_KEY
        if not key:
            logger.warning("FERNET_KEY no configurada, no se puede desencriptar key de DB — fallback a ENV")
            env_key = os.getenv("GEMINI_API_KEY", "") or (settings.GEMINI_API_KEY if hasattr(settings, 'GEMINI_API_KEY') else "")
            if env_key:
                logger.info(f"Usando API key desde ENV (FERNET_KEY vacia), key_prefix={env_key[:10]}...")
                return {
                    "provider": config.provider or "gemini",
                    "model_name": config.model_name or "gemini-2.5-flash",
                    "api_key": env_key,
                }
            logger.warning("No hay API key: FERNET_KEY vacia y ENV vacio")
            return {}
        try:
            f = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            raw = key.encode('utf-8')[:32].ljust(32, b'\0')
            valid_key = base64.urlsafe_b64encode(raw)
            f = Fernet(valid_key)

        api_key = f.decrypt(config.api_key_encrypted.encode('utf-8')).decode('utf-8')
        logger.info(f"Usando API key desde DB (desencriptada OK), key_prefix={api_key[:10]}...")

        return {
            "provider": config.provider or "gemini",
            "model_name": config.model_name or "gemini-2.5-flash",
            "api_key": api_key,
        }
    except Exception as e:
        logger.warning(f"Error al cargar AI config desde DB: {e}")

    # Final fallback to env vars
    env_key = os.getenv("GEMINI_API_KEY", "")
    if env_key:
        logger.info(f"Usando API key desde ENV (fallback por error en DB), key_prefix={env_key[:10]}...")
        return {
            "provider": "gemini",
            "model_name": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "api_key": env_key,
        }
    logger.warning("No hay API key disponible: DB fallo y ENV vacio")
    return {}


async def update_ai_usage_in_db(db):
    """Sync in-memory usage counters to DB (daily + monthly)."""
    from sqlalchemy import select
    from app.db.models.ai_config import AIConfig

    try:
        result = await db.execute(select(AIConfig).limit(1))
        config = result.scalar_one_or_none()
        if config and GeminiAnalyzer._total_requests > 0:
            config.daily_requests_used = (config.daily_requests_used or 0) + GeminiAnalyzer._total_requests
            config.monthly_requests_used = (config.monthly_requests_used or 0) + GeminiAnalyzer._total_requests
            await db.flush()
            logger.info(f"AI usage synced: +{GeminiAnalyzer._total_requests} requests (daily={config.daily_requests_used}, monthly={config.monthly_requests_used})")
            # Reset in-memory counters
            GeminiAnalyzer._total_requests = 0
            GeminiAnalyzer._total_errors = 0
    except Exception as e:
        logger.warning(f"Could not update AI usage in DB: {e}")
