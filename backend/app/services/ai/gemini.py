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
import json                                      # E1.2: telemetria por llamada
import threading                                 # ETAPA 1.5 (D6): estado de clase compartido
from datetime import datetime, timezone          # E1.2: marcas de tiempo ISO 8601
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

# ETAPA 1.5 (D3): las clases reales que lanza cada SDK, para clasificar por TIPO y
# no por subcadenas del mensaje. Guardadas igual que el import de arriba: si un SDK
# no esta, su comprobacion simplemente no aplica.
try:
    from openai import RateLimitError as _OpenAIRateLimitError
    from openai import APIStatusError as _OpenAIAPIStatusError
except ImportError:
    _OpenAIRateLimitError = _OpenAIAPIStatusError = None
try:
    from google.api_core.exceptions import ResourceExhausted as _GoogleResourceExhausted
except ImportError:
    _GoogleResourceExhausted = None

# ADENDA B (D9): fallos de red o del servidor que SI merecen reintento. Son los que
# el SDK reintentaba por su cuenta hasta que D5 le puso max_retries=0; sin esto, una
# desconexion puntual tumbaba la seccion al primer intento.
try:
    from openai import APIConnectionError as _OpenAIAPIConnectionError
    from openai import APITimeoutError as _OpenAIAPITimeoutError
except ImportError:
    _OpenAIAPIConnectionError = _OpenAIAPITimeoutError = None
try:
    from google.api_core.exceptions import (
        ServiceUnavailable as _GoogleServiceUnavailable,
        InternalServerError as _GoogleInternalServerError,
        DeadlineExceeded as _GoogleDeadlineExceeded,
    )
except ImportError:
    _GoogleServiceUnavailable = _GoogleInternalServerError = _GoogleDeadlineExceeded = None

from app.services.ai.estilo import (          # ETAPA 3 (D28/D32/D33)
    BLOQUE_ESTILO,
    REFERENCIA_ESTILO,
    bloque_estilo,
    kbs,
    ms,
    num,
    pct,
    percentil_frase,
    percentiles_bloque,
    tiempo,
    veces,
)
# ETAPA 5b (D55): la resolucion del umbral efectivo de cada transaccion vive en
# un solo sitio, y este modulo la usa tanto para calcular los veredictos como
# para contarselos a los prompts.
from app.services.ai.criterios import (
    bloque_completo, bloque_general, criterios_efectivos,
)

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
    # B6.2: la familia gpt-5 exige max_completion_tokens (ver openai_chat_completion).
    # 16384 conservador, alineado con gpt-5-mini; su techo real documentado es mayor.
    "gpt-5": 16384,
    # N4.6b: gpt-5.5 caia al default de 4096 con warning (misma trampa de HF18b).
    # 16384 verificado contra la API con una llamada real: acepta
    # max_completion_tokens=16384 y responde finish_reason=stop. Valor conservador
    # alineado con el resto de la familia gpt-5; su techo documentado es mayor.
    "gpt-5.5": 16384,
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


# ===================== B6.2: max_tokens vs max_completion_tokens =====================
# Los modelos de nueva generacion (gpt-5*, o1*, o3*, o4*) RECHAZAN max_tokens con un
# 400 y exigen max_completion_tokens. Estrategia hibrida: prefijos conocidos para
# acertar a la primera, y aprendizaje del 400 como red de seguridad para modelos
# futuros que no empiecen por esos prefijos. La eleccion se cachea por nombre de
# modelo, asi el 400 se paga UNA vez por proceso y no en cada llamada.
_OPENAI_NEWGEN_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_openai_token_param_cache: Dict[str, str] = {}


def _openai_token_param(model_name: str, limit: int) -> dict:
    """Kwarg de tope de salida que acepta este modelo."""
    key = _openai_token_param_cache.get(model_name)
    if key is None:
        key = ("max_completion_tokens"
               if (model_name or "").lower().startswith(_OPENAI_NEWGEN_PREFIXES)
               else "max_tokens")
        _openai_token_param_cache[model_name] = key
    return {key: limit}


def _openai_is_token_param_error(err) -> bool:
    """True si el 400 se queja justamente del parametro de tope de salida."""
    s = str(err).lower()
    return "max_tokens" in s and ("not supported" in s or "unsupported" in s)


# B6.3: la familia gpt-5/o* tampoco acepta `temperature` distinta de 1. Mandarla
# devuelve un 400 y TODA seccion cae al fallback. Es la causa raiz del informe
# generado con el analizador de respaldo el 16/08 (gpt-5-mini):
#   400 - "Unsupported value: 'temperature' does not support 0.7 with this model."
# Misma estrategia hibrida que B6.2: se evita por prefijo y, si aun asi llega el
# 400, se aprende y se cachea para no volver a pagarlo.
_openai_no_temp_cache: Dict[str, bool] = {}


# ETAPA 2 (D13/D13a): esfuerzo de razonamiento configurable.
REASONING_EFFORTS = ("low", "medium", "high")
REASONING_EFFORT_DEFAULT = "low"


def _openai_soporta_reasoning(model_name: str) -> bool:
    """Mismo criterio de prefijos que `max_completion_tokens` (D13)."""
    return (model_name or "").lower().startswith(_OPENAI_NEWGEN_PREFIXES)


def _openai_reasoning_kwarg(model_name: str, effort: Optional[str]) -> dict:
    """`reasoning_effort` solo para los modelos que lo admiten. {} si no aplica."""
    if not _openai_soporta_reasoning(model_name):
        return {}
    valor = (effort or REASONING_EFFORT_DEFAULT).lower()
    if valor not in REASONING_EFFORTS:
        valor = REASONING_EFFORT_DEFAULT
    return {"reasoning_effort": valor}


def _openai_temperature_kwarg(model_name: str, temperature: float) -> dict:
    """`temperature` solo para los modelos que la admiten."""
    m = (model_name or "").lower()
    if _openai_no_temp_cache.get(model_name) or m.startswith(_OPENAI_NEWGEN_PREFIXES):
        return {}
    return {"temperature": temperature}


def _openai_is_temperature_error(err) -> bool:
    s = str(err).lower()
    return "temperature" in s and ("not support" in s or "unsupported" in s)


def openai_chat_completion(client, model_name: str, messages: list, limit: int, **kwargs):
    """Llamada a OpenAI tolerante al cambio de nombre del parametro (B6.2).

    Si la API rechaza max_tokens, aprende la preferencia del modelo, la cachea y
    reintenta UNA vez. Cualquier otro error se propaga sin tocar.
    """
    # B6.3: la temperatura se filtra aqui, en el unico punto por el que pasan
    # todas las llamadas de chat, para que ninguna seccion la cuele por su cuenta.
    if "temperature" in kwargs and not _openai_temperature_kwarg(model_name, kwargs["temperature"]):
        kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}
    try:
        return client.chat.completions.create(
            model=model_name, messages=messages,
            **_openai_token_param(model_name, limit), **kwargs)
    except Exception as e:
        # B6.3: modelo que rechaza la temperatura -> se aprende y se reintenta sin ella
        if _openai_is_temperature_error(e) and "temperature" in kwargs:
            _openai_no_temp_cache[model_name] = True
            logger.warning("modelo %s no admite temperature; se reintenta sin ella y se cachea", model_name)
            kwargs.pop("temperature", None)
            return client.chat.completions.create(
                model=model_name, messages=messages,
                **_openai_token_param(model_name, limit), **kwargs)
        if not _openai_is_token_param_error(e) or _openai_token_param_cache.get(model_name) == "max_completion_tokens":
            raise
        _openai_token_param_cache[model_name] = "max_completion_tokens"
        logger.warning("modelo %s exige max_completion_tokens; cacheado para las siguientes llamadas", model_name)
        return client.chat.completions.create(
            model=model_name, messages=messages,
            **_openai_token_param(model_name, limit), **kwargs)


# ============ ETAPA 1.5 (HF-2): clasificacion de errores por TIPO ============
# D3: nunca por subcadenas. Antes, cualquier mensaje que contuviera "429", "rate",
# "quota" o "resource" se trataba como rate-limit y dormia 5+10+15 s: un
# "Failed to generate response" o un "resource not found" pagaban 30 s de espera
# por nada. Ahora se mira el tipo de excepcion y el codigo HTTP.
CIRCUITO_ENFRIAMIENTO_S = 60          # D2: tiempo antes de permitir una llamada de prueba
# ADENDA B (D11): el defecto del SDK era read=600 s. Una seccion colgada retenia un hilo
# diez minutos y el informe entero se quedaba esperando. 120 s sobra: la llamada mas lenta
# medida en las dos corridas de linea base fue de 15,9 s.
CLIENTE_TIMEOUT_S = 120.0
ESPERA_TRANSITORIA_S = 2              # D9: esperas de 2 s y 4 s entre intentos transitorios


def _clasificar_error(err) -> str:
    """'quota_exhausted' | 'rate_limit' | 'transient' | 'error'. Sin heuristicas de texto."""
    # D4: cuota agotada. Es un 429 tambien, asi que se mira ANTES que el rate-limit.
    codigo = getattr(getattr(err, "body", None), "get", lambda *_: None)("code") \
        if isinstance(getattr(err, "body", None), dict) else None
    if codigo is None:
        codigo = getattr(err, "code", None)
    if codigo == "insufficient_quota":
        return "quota_exhausted"

    # RateLimitError va ANTES que APIStatusError: es subclase suya.
    if _OpenAIRateLimitError is not None and isinstance(err, _OpenAIRateLimitError):
        return "rate_limit"
    if _OpenAIAPIStatusError is not None and isinstance(err, _OpenAIAPIStatusError):
        estado = getattr(err, "status_code", None)
        if estado == 429:
            return "rate_limit"
        # ADENDA B (D9): los mismos codigos que el SDK reintentaba.
        if estado in (408, 409) or (isinstance(estado, int) and estado >= 500):
            return "transient"
        # D12: el resto de 4xx (400, 401, 403, 404...) es culpa de la peticion.
        # Reintentar no cambia nada: error seco, sin espera y sin abrir el circuito.
        return "error"
    # APITimeoutError es subclase de APIConnectionError; basta comprobar la base.
    if _OpenAIAPIConnectionError is not None and isinstance(err, _OpenAIAPIConnectionError):
        return "transient"
    if _GoogleResourceExhausted is not None and isinstance(err, _GoogleResourceExhausted):
        return "rate_limit"
    transitorias_gemini = tuple(
        c for c in (_GoogleServiceUnavailable, _GoogleInternalServerError, _GoogleDeadlineExceeded)
        if c is not None
    )
    if transitorias_gemini and isinstance(err, transitorias_gemini):
        return "transient"
    return "error"


def _espera_sugerida(err) -> Optional[float]:
    """Segundos de `Retry-After` si el proveedor los manda (D5). None si no vienen."""
    try:
        cabeceras = getattr(getattr(err, "response", None), "headers", None) or {}
        valor = cabeceras.get("retry-after") or cabeceras.get("Retry-After")
        return float(valor) if valor is not None else None
    except Exception:
        return None


# ===================== E1.2: telemetria por llamada de IA =====================
# Una linea `AI_TELEMETRY {json}` por INTENTO de `_generate`. Es solo un log:
# no toca parametros enviados, ni el valor devuelto, ni el control de flujo.
# Todo va dentro de try/except — un fallo de telemetria jamas interrumpe la
# generacion. `usage` solo existe en OpenAI; con Gemini los tokens quedan null.
def _emit_ai_telemetry(section, provider, model, t0, attempt, limit, prompt_chars,
                       outcome, response=None, finish_reason=None,
                       reasoning_effort=None) -> None:   # ETAPA 2 (D13e)
    """E1.1 dejo abierta H1 por no capturar `usage`; esto es lo que la cierra."""
    try:
        fin = datetime.now(timezone.utc)
        u = getattr(response, "usage", None)
        ctd = getattr(u, "completion_tokens_details", None)
        ptd = getattr(u, "prompt_tokens_details", None)
        logger.info("AI_TELEMETRY %s", json.dumps({
            "section": section, "provider": provider, "model": model,
            "ts_start": t0.isoformat(), "ts_end": fin.isoformat(),
            "latency_ms": round((fin - t0).total_seconds() * 1000),
            "attempt": attempt, "max_completion_tokens": limit,
            "reasoning_effort": reasoning_effort,   # ETAPA 2 D13e; null si no aplica
            "prompt_chars": prompt_chars,
            "prompt_tokens": getattr(u, "prompt_tokens", None),
            "completion_tokens": getattr(u, "completion_tokens", None),
            "reasoning_tokens": getattr(ctd, "reasoning_tokens", None),
            "cached_tokens": getattr(ptd, "cached_tokens", None),
            "finish_reason": finish_reason, "outcome": outcome,
        }, default=str, ensure_ascii=False))
    except Exception:
        pass   # la telemetria nunca puede tumbar una generacion


# Performance tier thresholds (ms)
TIER_EXCELLENT = 500
TIER_ACCEPTABLE = 2000
TIER_DEGRADED = 5000

# ETAPA 3 (D28 + D34): el estilo vive en UN solo sitio (`estilo.py`) y viaja UNA
# sola vez por llamada — lo inyecta `_generate`, no cada prompt. Antes habia
# cuatro bloques (SYSTEM_PROMPT, STYLE_REMINDER, UX_RULE, FORMATO_NUMERICO) que
# se solapaban, se contradecian entre si y no llegaban a los mismos prompts; y
# el SYSTEM_PROMPT viajaba dos veces por llamada con OpenAI (reporte 30 §2).
_PERSONA = (
    "Eres un analista senior de performance con 15 anos de experiencia. "
    "Redactas informes tecnicos para gerentes de TI en espanol profesional colombiano."
)

SYSTEM_PROMPT = f"""{_PERSONA}

{BLOQUE_ESTILO}

{REFERENCIA_ESTILO}"""

# El mismo bloque con el permiso de dictaminar (D30): solo lo reciben las
# conclusiones, las recomendaciones y el consolidado del informe integrado.
SYSTEM_PROMPT_VEREDICTO = f"""{_PERSONA}

{bloque_estilo(permite_veredicto=True)}

{REFERENCIA_ESTILO}"""


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

    verdicts = {}
    for _, row in summary_df.iterrows():
        label = row['label']
        # ETAPA 5b (D55): la misma resolucion que reciben los prompts. Antes se
        # calculaba aqui a mano; ahora sale de `criterios.py`, para que el texto
        # de la IA y esta tabla no puedan hablar de umbrales distintos.
        rt_threshold, avail_threshold, _propios = criterios_efectivos(acceptance_criteria, label)
        er_threshold = 100.0 - avail_threshold

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

        # GRAF1-A: tambien es variabilidad un max muy por encima del promedio (picos/timeouts).
        # GRAF1-C: y un max de 10s o mas en absoluto, aunque el ratio sea bajo (timeouts).
        if tx['avg'] > 0 and (tx['p99'] / tx['avg'] > 3 or tx['max'] / tx['avg'] > 10 or tx['max'] >= 10000):
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
    """ETAPA 3 (D29 + D32): el mismo bloque de datos, sin una palabra de jerga.

    Antes escribia `=== TIER CRITICO ===`, `=== TIER EXCELENTE ===` y
    `=== ALERTA: ALTA VARIABILIDAD ===`, y los modelos copiaban esas etiquetas
    al informe (reporte 30 §2). Ahora los mismos grupos se nombran por lo que
    significan, las cifras van en formato espanol y los percentiles llegan ya
    traducidos a personas. La clasificacion interna (`insights['tiers']`) NO
    cambia: solo cambia como se le cuenta al modelo.

    El nombre de la funcion se conserva porque lo importan otros modulos; la
    palabra "tier" no sale de aqui.
    """
    tiers = insights['tiers']
    lines = []

    lines.append(f"TOTAL DE TRANSACCIONES ANALIZADAS: {insights['total_transactions']}")
    lines.append("")

    grupos = (
        ('critical', f"TIEMPOS MUY ALTOS (promedio por encima de {num(TIER_DEGRADED)} ms)"),
        ('degraded', f"TIEMPOS ALTOS (promedio entre {num(TIER_ACCEPTABLE)} y {num(TIER_DEGRADED)} ms)"),
        ('acceptable', f"TIEMPOS MEDIOS (promedio entre {num(TIER_EXCELLENT)} y {num(TIER_ACCEPTABLE)} ms)"),
        ('excellent', f"TIEMPOS BAJOS (promedio por debajo de {num(TIER_EXCELLENT)} ms)"),
    )
    for clave, titulo in grupos:
        if not tiers[clave]:
            continue
        lines.append(f"=== {titulo} — {len(tiers[clave])} transacciones ===")
        for tx in sorted(tiers[clave], key=lambda x: -x['avg']):
            lines.append(
                f"  {tx['name']}: promedio {ms(tx['avg'])}, maximo {ms(tx['max'])}, "
                f"errores {num(tx['errors'])}, caudal {num(tx['tps'], 2)} por segundo"
            )
            lines.append(f"    {percentil_frase(90, tx['p90'])}")
            lines.append(f"    {percentil_frase(95, tx['p95'])}")
            lines.append(f"    {percentil_frase(99, tx['p99'])}")
        lines.append("")

    if insights['high_variability']:
        lines.append(
            f"=== TRANSACCIONES DONDE UNOS USUARIOS ESPERAN MUCHO MAS QUE OTROS "
            f"— {len(insights['high_variability'])} transacciones ===")
        for tx in insights['high_variability']:
            ratio = tx['p99'] / tx['avg'] if tx['avg'] > 0 else 0
            ratio_max = tx['max'] / tx['avg'] if tx['avg'] > 0 else 0
            lines.append(
                f"  {tx['name']}: promedio {ms(tx['avg'])}, y 1 de cada 100 usuarios "
                f"espera {veces(ratio)} eso. El maximo de {ms(tx['max'])} es "
                f"{veces(ratio_max)} el promedio."
            )
        lines.append("")

    best = insights['best_transaction']
    worst = insights['worst_transaction']
    if best and worst:
        lines.append(f"TRANSACCION MAS RAPIDA: {best['name']} (promedio {ms(best['avg'])})")
        lines.append(f"TRANSACCION MAS LENTA: {worst['name']} (promedio {ms(worst['avg'])})")
        if best['avg'] > 0:
            lines.append(
                f"LA MAS LENTA ES {veces(worst['avg'] / best['avg'])} LA MAS RAPIDA "
                f"(usa esta cifra tal cual, no la estimes)")

    return "\n".join(lines)


# ==================== GEMINI ANALYZER ====================

class GeminiAnalyzer:
    """AI Analyzer supporting Gemini and OpenAI providers."""

    # Usage counters (in-memory, synced to DB by upload endpoint)
    _total_requests: int = 0
    _total_errors: int = 0

    # Circuit breaker: after first rate-limit failure, skip all subsequent calls
    _circuit_open: bool = False
    _last_error: Optional[str] = None   # B6.3: motivo del ultimo fallo, para ai_status

    # ETAPA 1.5 (D2): cuando se abrio, para dejar pasar UNA prueba tras el enfriamiento.
    _circuit_opened_at: Optional[float] = None
    _probe_in_flight: bool = False
    # D6: tras H4 hay varios hilos (to_thread) tocando este estado a la vez.
    _lock = threading.Lock()

    @classmethod
    def _abrir_circuito(cls, motivo: str) -> None:
        with cls._lock:
            cls._circuit_open = True
            cls._circuit_opened_at = time.monotonic()
            cls._probe_in_flight = False
        logger.warning(f"AI CIRCUIT OPEN: {motivo}. Enfriamiento {CIRCUITO_ENFRIAMIENTO_S}s.")

    @classmethod
    def _cerrar_circuito(cls) -> None:
        with cls._lock:
            if not cls._circuit_open and not cls._probe_in_flight:
                return
            cls._circuit_open = False
            cls._circuit_opened_at = None
            cls._probe_in_flight = False
        logger.info("AI CIRCUIT CLOSED: el proveedor responde de nuevo.")

    @classmethod
    def _circuito_bloquea(cls) -> Tuple[bool, bool]:
        """(bloquea, es_prueba). D2: pasado el enfriamiento deja pasar UNA sola prueba.

        Devuelve tambien si ESTA llamada es la prueba, porque quien la recibe tiene
        que liberar el flag pase lo que pase (ADENDA A).
        """
        with cls._lock:
            if not cls._circuit_open:
                return False, False
            abierto_desde = cls._circuit_opened_at
            if abierto_desde is None or (time.monotonic() - abierto_desde) < CIRCUITO_ENFRIAMIENTO_S:
                return True, False
            if cls._probe_in_flight:       # ya hay otra prueba en curso
                return True, False
            cls._probe_in_flight = True    # esta llamada es la prueba
            return False, True

    @classmethod
    def _fin_de_prueba(cls, motivo: str) -> None:
        """ADENDA A: cierra el ciclo de una llamada de prueba, gane o pierda.

        Va en un `finally`: antes, tres caminos (respuesta vacia por `length`, error
        no-rate-limit y provider no soportado) salian con `return None` sin soltar
        `_probe_in_flight`. Como `_circuito_bloquea` corta en seco si el flag esta
        puesto, el circuito quedaba bloqueado PARA SIEMPRE: ni el enfriamiento ni un
        proveedor ya sano lo recuperaban. Regla: solo el exito cierra el circuito;
        cualquier otro desenlace lo reabre con marca nueva y otro enfriamiento.
        """
        with cls._lock:
            ya_cerrado = not cls._circuit_open      # el exito lo cerro por su cuenta
            cls._probe_in_flight = False
        if not ya_cerrado:
            cls._abrir_circuito(motivo)             # marca nueva -> otros 60 s

    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-flash", api_key: str = "",
                 reasoning_effort: Optional[str] = None):   # ETAPA 2 (D13)
        self.reasoning_effort = reasoning_effort or REASONING_EFFORT_DEFAULT
        self.provider = provider or DEFAULT_PROVIDER
        self.model_name = model_name or MODEL_NAME
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        # Reset circuit breaker on new instance
        GeminiAnalyzer._cerrar_circuito()   # ETAPA 1.5: limpia tambien marca y prueba
        GeminiAnalyzer._circuit_open = False
        GeminiAnalyzer._last_error = None   # B6.3

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
            # ETAPA 1.5 (D5): max_retries=0. El SDK reintentaba 2 veces por su cuenta y,
            # sumado al bucle propio de 3 intentos, una sola seccion podia lanzar hasta
            # 9 peticiones HTTP invisibles para la telemetria. Los reintentos los hace
            # SOLO el bucle de `_generate`, y asi cada intento deja su linea.
            self._openai_client = OpenAI(
                api_key=self._api_key, max_retries=0, timeout=CLIENTE_TIMEOUT_S)
            logger.info(f"AIAnalyzer v4.0 iniciado: provider=openai, model={self.model_name}")
        else:
            raise ValueError(f"Proveedor no soportado: {self.provider}")

    def _generate(self, prompt: str, section_name: str = "unknown", max_retries: int = 3,
                  permite_veredicto: bool = False) -> Optional[str]:
        """Call AI API with retry logic. Returns None on failure to trigger fallback.
        Circuit breaker: if AI was rate-limited once, skip all subsequent calls immediately.

        ETAPA 3 (D34): el bloque de estilo lo pone AQUI, una sola vez por llamada
        y para los dos proveedores. Ningun prompt lo vuelve a incluir. Con Gemini
        va delante del prompt (el modelo se crea sin `system_instruction`); con
        OpenAI va como mensaje `system`. `permite_veredicto` elige la variante con
        el permiso de dictaminar (D30): conclusiones, recomendaciones y el
        consolidado del integrado. El resto de las secciones no dictaminan.
        """
        sistema = SYSTEM_PROMPT_VEREDICTO if permite_veredicto else SYSTEM_PROMPT

        # E1.2: `_t0` se reinicia en cada intento; `_tel` solo evita repetir 8 argumentos.
        _t0 = datetime.now(timezone.utc)

        def _tel(outcome, attempt, response=None, finish_reason=None):
            # Los argumentos se evaluan ANTES de entrar en el try/except de
            # `_emit_ai_telemetry`, asi que aqui no puede haber nada que lance:
            # romperia el invariante de E1.2 (la telemetria nunca tumba una
            # generacion). De ahi el getattr con defecto.
            _emit_ai_telemetry(
                section_name, self.provider, self.model_name, _t0, attempt,
                _openai_max_tokens_for(self.model_name) if self.provider == "openai" else None,
                # ETAPA 3 (D34): lo que SE ENVIA de verdad — estilo + prompt. Antes
                # el prompt ya traia el estilo dentro y `len(prompt)` bastaba.
                len(sistema) + 2 + len(prompt), outcome, response, finish_reason,
                # ETAPA 2 (D13e): el valor REALMENTE enviado, o null si no aplica.
                _openai_reasoning_kwarg(
                    self.model_name, getattr(self, "reasoning_effort", None)
                ).get("reasoning_effort")
                if self.provider == "openai" else None)

        # Circuit breaker — skip immediately if API already proven unavailable.
        # ETAPA 1.5 (D2): pasado el enfriamiento, esta llamada pasa como prueba.
        bloquea, es_prueba = GeminiAnalyzer._circuito_bloquea()
        if bloquea:
            logger.info(f"AI CIRCUIT OPEN: skipping {section_name} (using fallback)")
            GeminiAnalyzer._total_errors += 1
            _tel("circuit_open", 0)
            return None

        logger.info(f"AI CALL: provider={self.provider}, model={self.model_name}, section={section_name}, prompt_len={len(prompt)}")
        GeminiAnalyzer._total_requests += 1

        try:
            for attempt in range(max_retries):
                _t0 = datetime.now(timezone.utc)   # E1.2: latencia POR intento
                response = None
                try:
                    if self.provider == "gemini":
                        response = self.model.generate_content(f"{sistema}\n\n{prompt}")
                        result = response.text
                    elif self.provider == "openai":
                        response = openai_chat_completion(   # B6.2
                            self._openai_client,
                            self.model_name,
                            [
                                {"role": "system", "content": sistema},
                                {"role": "user", "content": prompt},
                            ],
                            _openai_max_tokens_for(self.model_name),
                            temperature=GENERATION_CONFIG["temperature"],
                            # ETAPA 2 (D13): viaja solo si el modelo lo soporta.
                            **_openai_reasoning_kwarg(
                                self.model_name, getattr(self, "reasoning_effort", None)),
                        )
                        result = response.choices[0].message.content if response.choices else None
                        if not result:
                            # B6.3: antes esto volvia None en silencio — sin log y sin
                            # motivo — y por eso el fallback era invisible (error=null).
                            fin = getattr(response.choices[0], "finish_reason", "?") if response.choices else "sin choices"
                            motivo = (f"{self.model_name} devolvio contenido vacio "
                                      f"(finish_reason={fin})")
                            logger.error(f"AI EMPTY for {section_name}: {motivo}")
                            GeminiAnalyzer._last_error = motivo
                            GeminiAnalyzer._total_errors += 1
                            # E1.2: el caso B6.3 (tope agotado por razonamiento) queda
                            # visible con sus tokens, que es justo lo que faltaba ver.
                            _tel("empty", attempt + 1, response, fin)
                            return None
                    else:
                        GeminiAnalyzer._total_errors += 1
                        _tel("error", attempt + 1)
                        return None

                    result = sanitize_ai_text(result)
                    # ETAPA 1.5 (D2): exito = el proveedor responde; el circuito se cierra.
                    GeminiAnalyzer._cerrar_circuito()
                    logger.info(f"AI OK: section={section_name}, response_len={len(result)}, preview={result[:80]}")
                    _tel("ok", attempt + 1, response,
                         getattr(response.choices[0], "finish_reason", None)
                         if getattr(response, "choices", None) else None)
                    return result

                except Exception as e:
                    error_str = str(e)
                    # ETAPA 1.5 (D3): por TIPO/codigo, nunca por subcadenas del mensaje.
                    tipo = _clasificar_error(e)

                    if tipo == "quota_exhausted":
                        # D4: reintentar no sirve. Fallo rapido, motivo visible y circuito
                        # abierto para no quemar las llamadas restantes contra un muro.
                        motivo = f"{self.model_name}: cuota agotada (insufficient_quota)"
                        logger.error(f"AI QUOTA EXHAUSTED for {section_name}: {error_str[:180]}")
                        GeminiAnalyzer._last_error = motivo
                        GeminiAnalyzer._total_errors += 1
                        GeminiAnalyzer._abrir_circuito(f"cuota agotada en {section_name}")
                        _tel("quota_exhausted", attempt + 1)
                        return None

                    if tipo == "rate_limit":
                        # D5: se respeta Retry-After si el proveedor lo manda; si no, 5/10/15.
                        wait_time = _espera_sugerida(e) or min((attempt + 1) * 5, 15)
                        logger.warning(f"AI RATE LIMITED (attempt {attempt+1}/{max_retries}) for {section_name}. Waiting {wait_time}s...")
                        _tel("rate_limited", attempt + 1)   # E1.2: antes de dormir
                        # ETAPA 2 (D14): sin dormir tras el ultimo intento — mismo
                        # criterio que los transitorios. Ahorra los 15 s finales,
                        # que se esperaban para nada antes de rendirse.
                        if attempt + 1 < max_retries:
                            time.sleep(wait_time)
                        continue

                    if tipo == "transient":
                        # ADENDA B (D9): red caida, timeout o 5xx. Son los casos que el SDK
                        # reintentaba antes de D5; sin este reintento, un corte de un segundo
                        # dejaba la seccion sin texto. Esperas cortas: 2 s y 4 s.
                        wait_time = ESPERA_TRANSITORIA_S * (attempt + 1)
                        logger.warning(f"AI TRANSIENT (attempt {attempt+1}/{max_retries}) for {section_name}: {error_str[:120]}. Waiting {wait_time}s...")
                        GeminiAnalyzer._last_error = f"{self.model_name}: {error_str[:180]}"
                        _tel("transient_error", attempt + 1)
                        # Sin dormir tras el ultimo intento: no queda nada que esperar.
                        # Con max_retries=3 las esperas son 2 s y 4 s, no 2/4/6.
                        if attempt + 1 < max_retries:
                            time.sleep(wait_time)
                        continue

                    # D3: cualquier otro error NO es rate-limit: sin espera y SIN abrir el
                    # circuito. Un fallo puntual de una seccion no puede dejar sin IA al resto.
                    logger.error(f"AI ERROR for {section_name}: {error_str}")
                    GeminiAnalyzer._last_error = f"{self.model_name}: {error_str[:180]}"   # B6.3
                    GeminiAnalyzer._total_errors += 1
                    _tel("error", attempt + 1)
                    return None

            # All retries exhausted — open circuit breaker for remaining calls
            logger.warning(f"AI UNAVAILABLE: {section_name} - max retries exceeded. CIRCUIT BREAKER OPEN — all remaining calls will use fallback.")
            GeminiAnalyzer._abrir_circuito(f"{max_retries} intentos agotados en {section_name}")
            GeminiAnalyzer._total_errors += 1
            _tel("fallback", max_retries)
            return None
        finally:
            # ADENDA A: la prueba suelta el flag pase lo que pase.
            if es_prueba:
                GeminiAnalyzer._fin_de_prueba(
                    f"la llamada de prueba de {section_name} no tuvo exito")

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

        # ETAPA 3 (D27/D28): el analisis de imagen es uno de los textos que
        # aparecen en el informe, asi que recibe el MISMO bloque de estilo que
        # todos los demas. Antes no recibia ninguno: era la unica salida de IA
        # del producto que escribia sin reglas.
        prompt = (
            f"{BLOQUE_ESTILO}\n\n"
            f"Analiza esta imagen de {type_label}.\n{context}\n\n"
            f"INSTRUCCIONES:\n{instructions}\n"
            f"Parrafos narrativos de 3 a 5 oraciones. Maximo 300 palabras. "
            f"Se especifico con los datos que ves y no inventes cifras que no "
            f"aparezcan en la imagen."
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
                response = openai_chat_completion(   # B6.2
                    self._openai_client,
                    self.model_name,
                    [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime_type};base64,{b64_data}"
                            }}
                        ]
                    }],
                    min(_openai_max_tokens_for(self.model_name), 1024),
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
            f"Genera el analisis a partir del texto extraido. Parrafos narrativos, "
            f"maximo 200 palabras. Si el texto es pobre o esta vacio, di que no fue "
            f"posible analizar el contenido."
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
        """Tabla de TODAS las transacciones (sin limite), en formato espanol.

        ETAPA 3 (D32): antes salia con `{:,}` y punto decimal, y el modelo copiaba
        "10,075 muestras" y "28.20%" al informe. Ahora cada cifra pasa por los
        helpers de `estilo.py`, asi que copiarla bien es lo mas facil.
        """
        lines = []
        lines.append("| Transaccion | Muestras | Errores | Error | Promedio | P95 | P99 | Minimo | Maximo | Caudal |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        logger.info(f"Construyendo tabla con {len(summary_df)} transacciones")
        for _, row in summary_df.iterrows():
            lines.append(
                f"| {row['label']} | {num(row['muestras'])} | {num(row['errores'])} | "
                f"{pct(row['tasa_error'])} | {ms(row['promedio'])} | {ms(row['p95'])} | "
                f"{ms(row['p99'])} | {ms(row['min'])} | {ms(row['max'])} | "
                f"{num(row['rendimiento'], 2)} por segundo |"
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
                    criteria_text += f"- Concurrencia esperada: {num(acceptance_criteria['concurrency'])} usuarios\n"
                if acceptance_criteria.get("response_time"):
                    criteria_text += f"- Tiempo de respuesta maximo aceptable: {ms(acceptance_criteria['response_time'])}\n"
                if acceptance_criteria.get("availability"):
                    criteria_text += f"- Disponibilidad minima: {pct(acceptance_criteria['availability'], 1)}\n"
                # ETAPA 5b (D55): las que NO se miden con ese criterio.
                criteria_text += bloque_general(acceptance_criteria)

            logger.info(f"Enviando {len(summary_df)} transacciones a Gemini para analisis de tabla resumen")

            # ETAPA 3 (D30): esta seccion NO dictamina — `permite_veredicto` se
            # queda en False y la estructura ya no pide "Listo para produccion?".
            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

TABLA DE RESULTADOS POR TRANSACCION:
{table}

LAS TRANSACCIONES AGRUPADAS POR SU TIEMPO DE RESPUESTA:
{tier_summary}

RESUMEN GLOBAL DE LA PRUEBA:
- Total de muestras: {num(metrics['total_requests'])}
- Tasa de error global: {pct(metrics['error_rate'])}
- Tiempo promedio global: {ms(metrics['avg_response_time'])}
- Caudal global: {num(metrics['throughput'], 2)} por segundo
- Duracion de la prueba: {num(metrics['duration_seconds'])} segundos
LECTURA DE LOS PERCENTILES GLOBALES (copia estas frases tal cual):
{percentiles_bloque(metrics.get('median_response_time', 0), metrics['p90_response_time'], metrics['p95_response_time'], metrics['p99_response_time'])}{criteria_text}

Escribe el analisis del resumen de la prueba. Maximo 180 palabras.
NO repitas la tabla: interpreta lo que dice.

Cuenta el recorrido del usuario en el orden en que ocurre, agrupando las
transacciones que se comportan igual en vez de listarlas una a una:

1. Cuantas transacciones se ejecutaron, cuanto tardaron en conjunto y que parte
   del flujo funciono bien.
2. Donde se rompe: nombra las transacciones con errores o con tiempos altos, con
   sus cifras, y di que significa funcionalmente que fallen justo ahi.
3. Si unos usuarios esperan mucho mas que otros, dilo con la frase de personas y
   su cifra.

Las {insights['total_transactions']} transacciones tienen que aparecer por su
nombre, aunque sea agrupadas. No digas si el sistema esta listo para produccion:
eso va en las conclusiones del informe.
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
        acceptance_criteria: Optional[Dict] = None,   # ETAPA 5b (D55)
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
                # ETAPA 3: la variable local se llamaba `pct` y tapaba al helper
                # del mismo nombre importado de `estilo.py`.
                porcentaje = (item['count'] / total_requests * 100) if total_requests > 0 else 0
                lines.append(
                    f"| {item['label']} | {num(item['count'])} | {item.get('code', 'N/A')} | "
                    f"{item.get('message', 'N/A')} | {pct(porcentaje)} |"
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

            error_classification = "\nLOS ERRORES AGRUPADOS POR CODIGO DE RESPUESTA:\n"
            for code, info in sorted(error_by_code.items()):
                code_str = str(code)
                category = "respuesta correcta" if code_str.startswith('2') else \
                           "redireccion" if code_str.startswith('3') else \
                           "la peticion fue rechazada" if code_str.startswith('4') else \
                           "fallo del servidor" if code_str.startswith('5') else "otro"
                error_classification += (
                    f"  HTTP {code} ({category}): {num(info['count'])} errores en "
                    f"{len(info['transactions'])} transacciones: {', '.join(info['transactions'])}\n"
                )

            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

ERRORES DETECTADOS:
{errors_table}
{error_classification}

CONTEXTO:
- Total de errores: {num(total_errors)}
- Tasa de error global: {pct(error_rate)}
- Total de peticiones: {num(total_requests)}
- Transacciones con errores: {len(error_data)}
- Codigos de respuesta distintos: {len(error_by_code)}
{bloque_completo(acceptance_criteria)}
Escribe el analisis de los errores. Maximo 140 palabras. Nombra CADA transaccion
con error. NO repitas la tabla: interpreta lo que dice.

1. Cuantos fallos hubo y en que punto del flujo de negocio aparecen. Agrupa las
   transacciones que fallan por el mismo motivo.
2. Que significa cada codigo en terminos de negocio y cual es su causa probable,
   marcada como hipotesis.
3. Que gravedad tiene para la operacion.

No digas si el sistema esta listo para produccion ni propongas un plan de
trabajo: eso va en las conclusiones y recomendaciones del informe.
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
        acceptance_criteria: Optional[Dict] = None,   # ETAPA 5b (D55)
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
                tier_context = (
                    "\n\nLAS TRANSACCIONES AGRUPADAS POR SU TIEMPO DE RESPUESTA:\n"
                    f"{build_tier_summary(insights)}\n")

            # ETAPA 3 (D29): estas instrucciones pedian literalmente "distribucion
            # por tiers" y "variabilidad P99/avg", y el modelo escribia esas dos
            # palabras en el informe (reporte 30 §2). Ahora piden lo mismo dicho
            # como lo tiene que leer un gerente.
            chart_specific_instructions = {
                'response_times': f"""Los datos traen las {insights['total_transactions'] if insights else ''} transacciones agrupadas por su tiempo de respuesta.
Nombra todas, aunque sea agrupando las que se comportan igual, y sigue el orden del flujo de negocio.
Contrasta la mas rapida con la mas lenta usando la cifra de "LA MAS LENTA ES ... LA MAS RAPIDA" que ya viene calculada.
El grupo se asigna por el promedio, pero mira SIEMPRE tambien el maximo: si el maximo supera de largo al promedio (diez veces o mas), senala ese pico con su cifra y su causa probable (esperas, tiempos agotados, contencion) aunque el promedio se vea sano. Los ratios llegan calculados como "[PICO: el maximo es N veces el promedio]": usalos tal cual.
Cuando unos usuarios esperen mucho mas que otros, dilo con la frase de personas que viene en los datos.""",

                'response_time_over_time': """Cubre: si los tiempos se mantienen o empeoran segun avanza la prueba, en que momento cambian, y que picos aparecen y por que.""",

                'throughput': """Cubre: cuanto trafico aguanto el sistema, si lo sostuvo, cuando cayo y cuanto margen queda frente a la carga esperada.""",

                'latency': """Cubre: cuanto del tiempo total se va en la espera previa a la respuesta, que peso tiene sobre lo que espera el usuario, y que picos apuntan a problemas de red.""",

                'error_rate': """Cubre: si los fallos son constantes, intermitentes o van a mas, si crecen con la carga, si el sistema se recupera, y que disponibilidad real deja eso.""",

                'codes_per_second': """Cubre: que responde el sistema y en que proporcion, que significa cada codigo en terminos de negocio, y si los fallos se concentran en algun tramo.""",

                'transactions_per_second': """Cubre: como se reparte el trabajo entre transacciones, si el caudal se sostiene, y si alguna operacion se queda atras.""",

                'active_threads': """Cubre: como entraron los usuarios (subida, meseta, bajada), cuantos llegaron a la vez, y si los tiempos empeoraron al subir la concurrencia.""",
            }

            chart_name = chart_names.get(chart_type, chart_type)
            specific = chart_specific_instructions.get(chart_type, "Analiza los datos de esta grafica en detalle.")

            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

DATOS DE LA GRAFICA "{chart_name}":
{data_summary}
{tier_context}{bloque_completo(acceptance_criteria)}
Escribe el analisis de esta grafica. Maximo 130 palabras.
NO repitas los datos: interpreta lo que muestran.

{specific}

No digas si el sistema esta listo para produccion ni propongas tareas: eso va en
las conclusiones y recomendaciones del informe."""
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

            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Se han detectado REDIRECCIONES HTTP separadas del trafico principal.

TABLA DE REDIRECCIONES:
{table}

CONTEXTO DEL TRAFICO PRINCIPAL:
- Muestras principales: {num(main_metrics.get('total_main_samples', 0))}
- Muestras de redireccion: {num(main_metrics.get('total_redirects', 0))}
- Nombres de las redirecciones: {', '.join(main_metrics.get('redirect_labels', []))}

Escribe el analisis de las redirecciones. Maximo 130 palabras. Nombra cada una.
NO repitas la tabla: interpreta lo que dice.

1. Cuantas son, que parte del trafico representan y en que punto del flujo
   aparecen.
2. Cuanto tiempo anaden a lo que espera el usuario frente a las transacciones
   principales, con su cifra.
3. Si su presencia es coherente con el diseno de la aplicacion o apunta a algo
   mal configurado, marcado como hipotesis.

No digas si el sistema esta listo para produccion ni propongas tareas: eso va en
las conclusiones y recomendaciones del informe.
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
        # ETAPA 2 (D19): se siguen aceptando para no tocar a los llamadores, pero
        # YA NO ENTRAN en el prompt: las dos secciones salieron del producto.
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
                # ETAPA 3 (D29): mismo contenido, sin la palabra "tier" ni
                # "ALTA VARIABILIDAD", que el modelo copiaba al informe.
                def _nombres(lista):
                    return ', '.join(tx['name'] for tx in lista) if lista else 'ninguna'
                insights_summary = f"""
LAS TRANSACCIONES AGRUPADAS POR SU TIEMPO DE RESPUESTA:
- Tiempos muy altos (por encima de {num(TIER_DEGRADED)} ms): {len(tiers['critical'])} ({_nombres(tiers['critical'])})
- Tiempos altos (entre {num(TIER_ACCEPTABLE)} y {num(TIER_DEGRADED)} ms): {len(tiers['degraded'])} ({_nombres(tiers['degraded'])})
- Tiempos medios (entre {num(TIER_EXCELLENT)} y {num(TIER_ACCEPTABLE)} ms): {len(tiers['acceptable'])} ({_nombres(tiers['acceptable'])})
- Tiempos bajos (por debajo de {num(TIER_EXCELLENT)} ms): {len(tiers['excellent'])} ({_nombres(tiers['excellent'])})
- Transacciones donde unos usuarios esperan mucho mas que otros: {len(insights['high_variability'])} ({_nombres(insights['high_variability'])})
- Transacciones con errores: {len(insights['error_transactions'])} ({_nombres(insights['error_transactions'])})
"""

            # Build acceptance criteria section for Gemini
            criteria_section = ""
            if acceptance_criteria and not acceptance_criteria.get('raw_text'):
                verdict = compute_verdict(metrics, acceptance_criteria)
                criteria_section = f"""
CRITERIOS DE ACEPTACION ACORDADOS CON EL CLIENTE:
- Concurrencia esperada: {num(acceptance_criteria.get('concurrency', 0))} usuarios
- Tiempo de respuesta maximo: {ms(acceptance_criteria.get('response_time', 0))}
- Disponibilidad minima: {pct(acceptance_criteria.get('availability', 0), 1)}
- RESULTADO CALCULADO: {verdict}

IMPORTANTE: tu primera conclusion DEBE ser ese resultado, "{verdict}", comparando
las cifras contra estos criterios. Si es NO APTO, di que criterios se incumplen.
Si es APTO CON RESERVAS, di que cifras quedan cerca del limite.
{bloque_general(acceptance_criteria)}"""

            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Has terminado de analizar una prueba de performance. Sintetiza TODO en las
conclusiones ejecutivas del informe. Esta es la parte del informe donde SI se
dictamina.

CIFRAS CLAVE DE LA PRUEBA:
- Total de peticiones: {num(metrics['total_requests'])}
- Tasa de error global: {pct(metrics['error_rate'])}
- Tiempo promedio global: {ms(metrics['avg_response_time'])}
- Caudal global: {num(metrics['throughput'], 2)} por segundo
- Duracion de la prueba: {num(metrics['duration_seconds'])} segundos
- Muestras principales: {num(metrics.get('total_main_samples', metrics['total_requests']))}
- Redirecciones: {num(metrics.get('total_redirects', 0))}
LECTURA DE LOS PERCENTILES GLOBALES (copia estas frases tal cual):
{percentiles_bloque(metrics.get('median_response_time', 0), metrics['p90_response_time'], metrics['p95_response_time'], metrics['p99_response_time'])}
{insights_summary}{criteria_section}
LO QUE YA SE ANALIZO, SECCION POR SECCION:

1. RESUMEN DE LA PRUEBA:
{ai_analysis_summary}

2. ERRORES:
{ai_analysis_errors}

3. TIEMPOS DE RESPUESTA POR TRANSACCION:
{ai_analysis_response_times}

4. LATENCIA:
{ai_analysis_latency}

5. TASA DE ERROR:
{ai_analysis_error_rate}

6. CODIGOS DE RESPUESTA:
{ai_analysis_codes_per_second}

7. CAUDAL DE TRANSACCIONES:
{ai_analysis_transactions_per_second}

8. USUARIOS ACTIVOS:
{ai_analysis_active_threads}
{redirect_section}
Escribe 6 conclusiones, cada una un parrafo completo de 3 a 5 oraciones,
numeradas. Maximo 350 palabras en total. Cubre: el resultado frente a los
criterios, los tiempos, los errores, la capacidad, la estabilidad y lo que hay
que resolver primero.

Cada conclusion cruza varias secciones y nombra transacciones concretas con sus
cifras. No repitas literalmente lo que ya dijo una seccion: sintetiza.
"""
            return self._generate(prompt, section_name="conclusions", permite_veredicto=True)

        except Exception as e:
            logger.error(f"GEMINI FAILED for conclusions: {str(e)}")
            return None

    def generate_recommendations(
        self,
        metrics: Dict,
        ai_analysis_summary: str,
        ai_analysis_errors: str,
        ai_analysis_response_times: str,
        # ETAPA 2 (D19): se siguen aceptando para no tocar a los llamadores, pero
        # YA NO ENTRAN en el prompt: las dos secciones salieron del producto.
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
                # ETAPA 3 (D29): los mismos grupos, sin jerga.
                if tiers['critical']:
                    items.append(f"Tiempos muy altos - {len(tiers['critical'])} transacciones por encima de {num(TIER_DEGRADED)} ms: {', '.join(tx['name'] for tx in tiers['critical'])}")
                if tiers['degraded']:
                    items.append(f"Tiempos altos - {len(tiers['degraded'])} transacciones entre {num(TIER_ACCEPTABLE)} y {num(TIER_DEGRADED)} ms: {', '.join(tx['name'] for tx in tiers['degraded'])}")
                if insights['high_variability']:
                    items.append(f"Unos usuarios esperan mucho mas que otros - {len(insights['high_variability'])} transacciones: {', '.join(tx['name'] for tx in insights['high_variability'])}")
                if insights['error_transactions']:
                    items.append(f"Con errores - {len(insights['error_transactions'])} transacciones: {', '.join(tx['name'] for tx in insights['error_transactions'])}")
                if items:
                    action_items = "\nPROBLEMAS DETECTADOS EN LA PRUEBA:\n" + "\n".join(f"  {i}" for i in items) + "\n"

            # Build acceptance criteria context for recommendations
            criteria_section = ""
            if acceptance_criteria and not acceptance_criteria.get('raw_text'):
                criteria_section = f"""
CRITERIOS DE ACEPTACION ACORDADOS CON EL CLIENTE:
- Concurrencia esperada: {num(acceptance_criteria.get('concurrency', 0))} usuarios
- Tiempo de respuesta maximo: {ms(acceptance_criteria.get('response_time', 0))}
- Disponibilidad minima: {pct(acceptance_criteria.get('availability', 0), 1)}

Las recomendaciones tienen que apuntar a cumplir esos criterios concretos.
{bloque_general(acceptance_criteria)}"""

            prompt = f"""{get_metric_unit_instruction(metric_unit)}
{test_ctx}

Escribe las recomendaciones del informe a partir de los resultados de la prueba.
Esta es una de las dos partes del informe donde SI se dictamina.

CIFRAS CLAVE DE LA PRUEBA:
- Total de peticiones: {num(metrics['total_requests'])}
- Tasa de error global: {pct(metrics['error_rate'])}
- Tiempo promedio global: {ms(metrics['avg_response_time'])}
- Caudal global: {num(metrics['throughput'], 2)} por segundo
LECTURA DE LOS PERCENTILES GLOBALES (copia estas frases tal cual):
{percentiles_bloque(p95=metrics['p95_response_time'], p99=metrics['p99_response_time'])}
{action_items}{criteria_section}
LO QUE DICEN LOS ANALISIS:

RESUMEN Y TRANSACCIONES:
{ai_analysis_summary}

ERRORES:
{ai_analysis_errors}

TIEMPOS DE RESPUESTA:
{ai_analysis_response_times}

CAPACIDAD:
{ai_analysis_transactions_per_second}

INFRAESTRUCTURA:
{ai_analysis_latency}
{ai_analysis_active_threads}
{redirect_section}
Escribe las recomendaciones ordenadas por prioridad. Maximo 350 palabras.
CRITICAS (2 o 3): hay que resolverlas antes de salir a produccion.
ALTAS (2 o 3): hay que resolverlas pronto.
MEDIAS (1 o 2): mejoras que pueden esperar.

Cada recomendacion es un parrafo de 3 o 4 oraciones con el problema, la accion
concreta y las transacciones afectadas con sus cifras.
"""
            return self._generate(prompt, section_name="recommendations", permite_veredicto=True)

        except Exception as e:
            logger.error(f"GEMINI FAILED for recommendations: {str(e)}")
            return None


# Instancia global - lazy initialization
_analyzer_instance: Optional[GeminiAnalyzer] = None
_analyzer_config_key: str = ""


def reset_circuit_breaker() -> None:
    """ETAPA 1.5 (D2): cierra el circuito a mano.

    Lo llama el guardado de config de IA: si el circuito se abrio por una key
    caducada o una cuota agotada, cambiar la config debe volver a habilitar la IA
    sin esperar el enfriamiento y sin reiniciar el proceso.
    """
    GeminiAnalyzer._cerrar_circuito()
    GeminiAnalyzer._last_error = None


def get_gemini_analyzer(
    provider: str = "",
    model_name: str = "",
    api_key: str = "",
    reasoning_effort: str = "",          # ETAPA 2 (D13c)
) -> GeminiAnalyzer:
    """Obtener instancia de GeminiAnalyzer (lazy init, recreates on config change)"""
    global _analyzer_instance, _analyzer_config_key

    # D13c: el effort forma parte de la clave. Sin esto, cambiarlo en la pantalla de
    # configuracion no tendria efecto hasta reiniciar el proceso: el singleton se
    # reutilizaria con el valor viejo.
    efecto = (reasoning_effort or REASONING_EFFORT_DEFAULT).lower()
    config_key = f"{provider}:{model_name}:{api_key[:8] if api_key else ''}:{efecto}"

    if _analyzer_instance is None or (config_key and config_key != _analyzer_config_key):
        _analyzer_instance = GeminiAnalyzer(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            reasoning_effort=efecto,
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
            # ETAPA 2 (D13): NULL en base significa 'low'.
            "reasoning_effort": config.reasoning_effort or REASONING_EFFORT_DEFAULT,
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
