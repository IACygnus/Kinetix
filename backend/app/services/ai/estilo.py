"""ETAPA 3 — Estilo de los textos de IA: formato, reglas y detectores.

Un solo modulo para las cinco piezas que la Etapa 3 comparte entre los
diecinueve prompts del informe (D27):

  1. Formato espanol determinista (D32) — `num`, `pct`, `ms`, `tiempo`, `veces`.
     Los bloques de datos se le entregan al modelo YA formateados: copiar es
     mas facil que reformatear, y por eso los textos por transaccion de la
     Etapa 2 (que ya usaban esta idea) salieron con cero cifras a la inglesa.
  2. Frases de percentil (D33) — `percentil_frase`, `mediana_frase`.
  3. El bloque de estilo unico (D28) — `BLOQUE_ESTILO`, `PERMISO_VEREDICTO`,
     `REFERENCIA_ESTILO`. Sustituye a `STYLE_REMINDER`, `UX_RULE` y
     `FORMATO_NUMERICO`, que se solapaban y no llegaban a los mismos prompts.
  4. El detector de estilo (D35) — `detectar_estilo`, `terminos_de`.
  5. La trazabilidad de cifras (D37) — `trazar_cifras`.

Los dos detectores SOLO DETECTAN Y REPORTAN. No regeneran, no reescriben, no
bloquean y no llaman a la IA. Son deterministas: mismo texto, mismo resultado.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


# ====================================================================
# 1. FORMATO ESPANOL (D32)
# ====================================================================

def num(valor: Any, dec: int = 0) -> str:
    """Numero a la espanola: miles con punto, decimales con coma.

    >>> num(10075)
    '10.075'
    >>> num(0.2734, 2)
    '0,27'
    """
    try:
        txt = f"{float(valor or 0):,.{dec}f}"
    except (TypeError, ValueError):
        return str(valor)
    # ',' -> '.' y '.' -> ',' en un solo paso, con un centinela.
    return txt.replace(",", "\x01").replace(".", ",").replace("\x01", ".")


def pct(valor: Any, dec: int = 2) -> str:
    """Porcentaje a la espanola, con el simbolo pegado (D32).

    `valor` ya viene en porcentaje: 0.2734 -> '0,27%'.
    """
    return f"{num(valor, dec)}%"


def ms(valor: Any) -> str:
    """Milisegundos con la unidad separada (D32): 125 -> '125 ms'."""
    return f"{num(valor)} ms"


def tiempo(valor_ms: Any) -> str:
    """Tiempo legible: por encima de 1.000 ms, segundos con un decimal.

    >>> tiempo(3515)
    '3,5 segundos'
    >>> tiempo(125)
    '125 ms'
    """
    try:
        v = float(valor_ms or 0)
    except (TypeError, ValueError):
        return str(valor_ms)
    if v >= 1000:
        return f"{num(v / 1000.0, 1)} segundos"
    return ms(v)


def veces(ratio: Any, dec: int = 1) -> str:
    """Ratio en palabras (D32): 3.79 -> '3,8 veces'. Nunca '3.8x'."""
    return f"{num(ratio, dec)} veces"


def kbs(valor: Any, dec: int = 2) -> str:
    """Caudal de bytes con la unidad separada: 259.85 -> '259,85 KB/s'."""
    return f"{num(valor, dec)} KB/s"


# ====================================================================
# 2. FRASES DE PERCENTIL (D33)
# ====================================================================

# Cuantas personas hay detras de cada percentil (v1.2 §4.1).
_PERSONAS = {50: None, 90: 10, 95: 20, 99: 100}


def percentil_frase(p: int, valor_ms: Any) -> str:
    """El percentil ya traducido, listo para que el modelo lo copie.

    La tilde de "más" va a proposito, aunque el resto de los prompts del
    proyecto sea ASCII: el modelo copia esta frase LITERALMENTE al informe
    (asi se le pide), asi que lo que se escriba aqui es lo que lee el cliente.

    >>> percentil_frase(90, 3515)
    '1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)'
    """
    cifra = f"(P{p}: {ms(valor_ms)})"
    if p == 50:
        return f"la mitad de los usuarios espera más de {tiempo(valor_ms)} {cifra}"
    cada = _PERSONAS.get(p)
    if cada is None:
        return f"{tiempo(valor_ms)} {cifra}"
    return f"1 de cada {cada} usuarios espera más de {tiempo(valor_ms)} {cifra}"


def mediana_frase(valor_ms: Any) -> str:
    """La mediana con su lectura en personas."""
    return percentil_frase(50, valor_ms)


def percentiles_bloque(p50: Any = None, p90: Any = None,
                       p95: Any = None, p99: Any = None) -> str:
    """Las cuatro frases de percentil de una transaccion o de la prueba."""
    partes = []
    for p, v in ((50, p50), (90, p90), (95, p95), (99, p99)):
        if v is None:
            continue
        partes.append(f"- {percentil_frase(p, v)}")
    return "\n".join(partes)


# ====================================================================
# 3. EL BLOQUE DE ESTILO UNICO (D28, D29, D30, D31, D33)
# ====================================================================

# BLOQUE 2.3 — la guia de estilo de Fredy (30/09/2026). Sustituye a las reglas
# que obligaban a llenar de cifras (apertura con dato, cifras exactas en todo,
# percentiles traducidos en lista, parrafos de 2 a 4 oraciones, cierre con
# impacto) y al ejemplo de tono anterior. Se mantienen: formato espanol,
# hipotesis marcadas, sin disculpas, vocabulario prohibido, sin markdown y sin
# dictamen fuera de las secciones con permiso.
BLOQUE_ESTILO = """GUÍA DE ESTILO

- Quién lee: el gerente del cliente, muchas veces sin un técnico al lado. Escribimos para que entienda cómo le fue a su sistema sin saber de performance.
- Voz: primera persona del plural («observamos», «encontramos», «recomendamos»).
- Cómo contamos: como quien cuenta cómo nos fue en la prueba: qué pasó, dónde está el problema y qué significa para la operación. Los números sostienen el relato, no lo reemplazan: solo las cifras que prueban el hallazgo. Nunca enumeramos métricas una tras otra ni listamos percentiles; si un percentil hace falta, uno solo y contado en personas.
- Forma de las secciones: un solo párrafo continuo, de unas 120 a 160 palabras, sin partirlo, sin viñetas ni formato. Orden: comportamiento general → qué destaca y dónde (transacción, fase de la prueba) → qué sugiere (causa posible, como hipótesis) → qué conviene revisar, si aplica. Lo que pasa en las rampas se cuenta como tal, no como hallazgo principal.
- Conclusiones: viñetas, de 4 a 7, un hallazgo con su porqué en cada una. El dictamen de viabilidad al final y siempre explicado con la razón. No repiten las cifras de las secciones.
- Recomendaciones: viñetas, de 4 a 7, cada una ligada a un hallazgo concreto de esta prueba (qué transacción, qué error, qué componente) y accionable. Nada genérico que valga para cualquier prueba. Sin repetir cifras.
- Varias ejecuciones: un solo análisis para todas («Tanto en la prueba de carga como en la de estrés…»), nunca un bloque por ejecución.

REGLAS QUE SE MANTIENEN

1. VOCABULARIO PROHIBIDO. No escribas NUNCA estas palabras, ni siquiera dentro
   de una frase útil: tier (ni ninguna variante), variabilidad, alta
   variabilidad, dispersión, latencia crítica, veredicto, hallazgo, se
   evidencia, se observa que, cabe destacar, es importante mencionar, en
   conclusión. Si los datos que recibes usan alguna, tu texto no la repite.

2. FORMATO ESPAÑOL. Miles con punto y decimales con coma: 8.600 muestras,
   21.060 ms, 0,27%. La unidad va separada del número (125 ms, 33,59 TPS) y el
   porcentaje, pegado (0,27%). Por encima de 1.000 ms, segundos con un decimal
   (1,1 segundos). Las comparaciones, en palabras: «3,9 veces más lenta», nunca
   «3.9x». Las cifras que recibes ya vienen así: cópialas tal cual. PROHIBIDO
   el formato inglés (8,600 · 1.1 segundos · 179.73ms) y PROHIBIDO inventar una
   cifra que no esté en los datos.

3. UN PERCENTIL, SI HACE FALTA, EN PERSONAS. P90 es 1 de cada 10 usuarios, P95
   1 de cada 20 y P99 1 de cada 100, con esta forma: «1 de cada 10 usuarios
   espera más de 3,5 segundos (P90: 3.515 ms)». Nunca un percentil a secas.

4. HIPÓTESIS MARCADAS. Una causa es una lectura probable: «sugiere», «apunta
   a», «es coherente con». PROHIBIDO afirmar causas como hechos demostrados.

5. SIN DISCULPAS. PROHIBIDO escribir sobre lo que los datos no traen: «con la
   información agregada no es posible», «no se puede determinar», «los datos no
   permiten», «si existieran…», «no se dispone de». Si un dato no está, no lo
   menciones: habla de lo que sí está.

6. SIN MARKDOWN. Nada de **, ##, encabezados, tablas ni énfasis con asteriscos
   o comillas. Las viñetas, solo donde se piden (conclusiones y
   recomendaciones): cada una en su propia línea y empezando por «• ». Los
   nombres de transacción van tal cual, sin resaltar.

7. SIN DICTAMEN FUERA DE SU SITIO. PROHIBIDO decir si el sistema está listo,
   apto o no apto para producción, o si debe o no liberarse, salvo en las
   secciones que reciben el permiso al final de su mensaje. Una sección sin ese
   permiso describe, interpreta y dice qué conviene revisar; no dictamina."""


PERMISO_VEREDICTO = """ESTA SECCIÓN SÍ PUEDE DICTAMINAR (excepción a la regla 7).
Aquí va, cuando corresponda, si el sistema está listo para producción, siempre
explicado con su razón, y aquí sí caben acciones y recomendaciones concretas. El
resto de la guía y de las reglas sigue vigente."""


# D31 / BLOQUE 2.3: los ejemplos los aprobo Fredy. Son de OTRA prueba: la
# prohibicion de copiar sus cifras y nombres es obligatoria, o no habria forma de
# distinguir un texto bien hecho de una copia del ejemplo.
REFERENCIA_ESTILO = """EJEMPLO DE SECCIÓN (de OTRA prueba, solo por su forma de contar):

«La ejecución presentó tiempos de respuesta estables y bajos en la mayoría de las transacciones, con promedios inferiores a 100 ms para ConsultaDeudores, ConsultaFacturasCliente y ConsultaLoteDeudores. Sin embargo, la transacción ConsultaContratosCliente registró 1.299 errores (32,89%), concentrando prácticamente la totalidad de las fallas observadas y elevando la tasa de error global al 8,28%. Este comportamiento sugiere una posible intermitencia o inestabilidad del servicio asociado a esta operación durante la ejecución de la prueba. Aunque el rendimiento general fue adecuado, recomendamos analizar la causa de estos errores para garantizar la estabilidad del servicio.»

EJEMPLO DE CONCLUSIONES Y RECOMENDACIONES (dos ejecuciones, un solo análisis; de OTRA prueba):

Conclusiones:
• Tanto en la prueba de carga como en la de estrés, la plataforma mantuvo tiempos de respuesta estables y una adecuada capacidad de procesamiento, sin evidenciar una degradación progresiva del rendimiento ante el incremento de la demanda.
• La transacción ConsultaContratosCliente concentró la totalidad de los errores observados en ambos escenarios, con respuestas recurrentes HTTP 500, lo que evidencia una condición de inestabilidad persistente del servicio.
• Los análisis de infraestructura no evidenciaron saturación de CPU, memoria, pods ni limitaciones en el API Gateway que expliquen los errores, por lo que la afectación se asocia principalmente al comportamiento interno del servicio o de alguna de sus dependencias.
• Los picos de latencia observados fueron eventos puntuales y coinciden con los errores de ConsultaContratosCliente, sin afectar de forma generalizada al resto de los servicios.
Recomendaciones:
• Realizar un análisis detallado de los logs y trazas de ConsultaContratosCliente para identificar la causa raíz de los errores HTTP 500 presentados durante ambas pruebas.
• Revisar las dependencias consumidas por el servicio, incluyendo bases de datos, APIs y componentes externos, para identificar intermitencias o excepciones no controladas.
• Ejecutar una nueva ronda de pruebas una vez aplicadas las correcciones, para confirmar la eliminación de la intermitencia bajo carga y estrés.
• Mantener la capacidad actual de infraestructura para el volumen evaluado, dado que los resultados no evidencian restricciones de recursos.

PROHIBIDO ABSOLUTAMENTE copiar de estos ejemplos sus cifras, sus porcentajes, sus
nombres de transacción o sus frases literales. Pertenecen a otra prueba. Usa
ÚNICAMENTE los datos que se te entregan. Si tu texto repite una cifra o un nombre
de los ejemplos que no esté en tus datos, está mal."""


def bloque_estilo(permite_veredicto: bool = False) -> str:
    """El bloque de estilo listo para inyectar. Unica fuente de verdad (D28)."""
    if permite_veredicto:
        return f"{BLOQUE_ESTILO}\n\n{PERMISO_VEREDICTO}"
    return BLOQUE_ESTILO


# ====================================================================
# 4. DETECTOR DE ESTILO (D35)
# ====================================================================

def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def _frases(texto: str) -> List[str]:
    """Parte en frases sin romper los numeros: el punto de '3.515' no separa."""
    return [f for f in re.split(r"(?<!\d)[.!?]+(?!\d)|\n+", texto) if f.strip()]


# --- D29: jerga prohibida ---
_JERGA = [
    (re.compile(r"\btiers?\b", re.I), "tier"),
    (re.compile(r"\bvariabilidad\b", re.I), "variabilidad"),
    (re.compile(r"\bdispersion\b", re.I), "dispersion"),
    (re.compile(r"\blatencia critica\b", re.I), "latencia critica"),
]

# --- D29: percentil sin su frase de usuario ---
_PERCENTIL = re.compile(r"\b(?:P\s?(?:50|90|95|99)|percentil\s+(?:50|90|95|99))\b", re.I)
_TRADUCIDO = re.compile(r"\b\d+\s+de\s+cada\s+\d+|\bmitad\s+de\s+(?:los\s+)?usuarios\b", re.I)

# --- D30: donde SI se permite el veredicto de produccion (v1.2 §4.2) ---
SECCIONES_CON_VEREDICTO = {
    "conclusions", "recommendations",
    "ai_conclusions", "ai_recommendations",
    "consolidated_conclusions", "consolidated_recommendations",
    "consolidated_load", "consolidated_stress",
    "unified_conclusions",
    # BLOQUE 2.2 (137 §5.1): proponen umbrales y acciones; reciben el permiso.
    "monitoring_analysis", "evidence_analysis", "comparison_analysis",
}

_VEREDICTO = [
    (re.compile(r"\b(?:no\s+)?(?:esta|estan|queda|quedan)?\s*listos?\s+para\s+(?:salir\s+a\s+)?produccion\b", re.I), "listo para produccion"),
    (re.compile(r"\bapto\s+(?:para\s+produccion|con\s+reservas)\b", re.I), "apto para produccion"),
    (re.compile(r"\bno\s+apto\b", re.I), "no apto"),
    (re.compile(r"\b(?:no\s+)?(?:debe|deberia|puede|podria|conviene)\s+(?:liberarse|desplegarse|publicarse|promoverse|salir\s+a\s+produccion|pasar\s+a\s+produccion)\b", re.I), "liberar/desplegar"),
    (re.compile(r"\bantes\s+de\s+(?:pasar\s+a\s+|salir\s+a\s+|ir\s+a\s+)?produccion\b", re.I), "antes de produccion"),
    (re.compile(r"\bno\s+se\s+recomienda\s+(?:su\s+)?(?:despliegue|liberacion|paso\s+a\s+produccion)\b", re.I), "no desplegar"),
    (re.compile(r"\b(?:bloquea|impide)\s+(?:la\s+)?(?:salida|liberacion|paso)\s+a\s+produccion\b", re.I), "bloquea produccion"),
    (re.compile(r"\b(?:listo|apto)\s+para\s+(?:el\s+)?despliegue\b", re.I), "listo para despliegue"),
    (re.compile(r"\bviable\s+para\s+produccion\b", re.I), "viable para produccion"),
]

# --- R2 (R-D14): disculpas por el dato que falta ---
# Salian de pedirle al modelo lo que el dato no contenia (reporte 120 §3). Con la
# serie delante no hacen falta; sin ella, la respuesta es arreglar el dato, no
# disculparse. Se comparan sin tildes y en minusculas.
_DISCULPA = [
    (re.compile(r"\bcon\s+(?:la\s+)?informacion\s+(?:agregada|entregada|disponible|suministrada|recibida|proporcionada)", re.I),
     "con la informacion agregada/entregada"),
    (re.compile(r"\bno\s+(?:es|resulta|fue)\s+posible\s+(?:determinar|atribuir|establecer|saber|concluir|identificar|precisar|afirmar|asociar|distinguir)", re.I),
     "no es posible determinar"),
    (re.compile(r"\bno\s+se\s+pueden?\s+(?:determinar|atribuir|establecer|saber|concluir|identificar|precisar|afirmar|asociar|distinguir)", re.I),
     "no se puede determinar"),
    (re.compile(r"\blos\s+datos\s+(?:\w+\s+)?no\s+permiten\b", re.I), "los datos no permiten"),
    (re.compile(r"\bsi\s+(?:existieran|existiera|se\s+contara|se\s+dispusiera|se\s+tuviera)\b", re.I),
     "si existieran..."),
    (re.compile(r"\bcambiar(?:ia|ian)\s+la\s+lectura\b", re.I), "cambiarian la lectura"),
    (re.compile(r"\bno\s+(?:se\s+dispone|se\s+cuenta|hay|tenemos)\s+(?:de\s+|con\s+)?(?:informacion|datos|serie|detalle)\b", re.I),
     "no se dispone de datos"),
    (re.compile(r"\bcon\s+la\s+informacion\s+\w+\s+no\s+hay\b", re.I), "con la informacion ... no hay"),
    (re.compile(r"\bsin\s+(?:la\s+)?serie\s+(?:temporal|de\s+tiempo)\b", re.I), "sin la serie temporal"),
]

# --- D32: formato ingles ---
# Decimal a la inglesa: punto con uno o dos decimales ("179.73", "3.9"). Un
# punto con TRES digitos detras es separador de miles a la espanola
# ("3.515 ms", "10.075 muestras") y NO se marca (decision T2, reporte 30 §6).
_DECIMAL_PUNTO = re.compile(r"(?<![\d.,])\d+\.\d{1,2}(?![\d])")
# Miles a la inglesa: "2,841", "10,075". Se excluye "0,275" (decimal espanol).
_MILES_COMA = re.compile(r"(?<![\d.,])(?!0,)\d{1,3},\d{3}(?![\d])")
# Unidad pegada al numero: "108ms", "300s". El % SI va pegado en espanol.
_UNIDAD_PEGADA = re.compile(r"\b\d+(?:[.,]\d+)?(?:ms|seg|s)\b")
# Ratio a la inglesa: "3.9x", "21x". En espanol va "3,9 veces".
_RATIO_X = re.compile(r"\b\d+(?:[.,]\d+)?\s?x\b", re.I)


def _contexto(texto: str, ini: int, fin: int, radio: int = 45) -> str:
    a, b = max(0, ini - radio), min(len(texto), fin + radio)
    return (("..." if a > 0 else "") + texto[a:b].replace("\n", " ").strip()
            + ("..." if b < len(texto) else ""))


def detectar_estilo(texto: Optional[str], seccion: str = "") -> List[Dict[str, str]]:
    """Avisos de estilo de UN texto. Solo detecta y reporta. Nunca lanza."""
    try:
        if not texto or not str(texto).strip():
            return []
        texto = str(texto)
        plano = _sin_tildes(texto)
        avisos: List[Dict[str, str]] = []

        for rx, termino in _JERGA:
            for m in rx.finditer(plano):
                avisos.append({"tipo": "jerga", "termino": termino,
                               "contexto": _contexto(texto, m.start(), m.end())})

        for frase in _frases(plano):
            if _TRADUCIDO.search(frase):
                continue
            for m in _PERCENTIL.finditer(frase):
                avisos.append({"tipo": "percentil_sin_traducir",
                               "termino": m.group(0).replace(" ", "").upper(),
                               "contexto": frase.strip()[:140]})

        if seccion not in SECCIONES_CON_VEREDICTO:
            for rx, termino in _VEREDICTO:
                for m in rx.finditer(plano):
                    avisos.append({"tipo": "veredicto_fuera_de_conclusiones",
                                   "termino": termino,
                                   "contexto": _contexto(texto, m.start(), m.end())})

        # R2 (R-D14): una sola marca por frase, aunque case con dos patrones.
        for frase in _frases(plano):
            for rx, termino in _DISCULPA:
                if rx.search(frase):
                    avisos.append({"tipo": "disculpa", "termino": termino,
                                   "contexto": frase.strip()[:160]})
                    break

        for rx, termino in ((_DECIMAL_PUNTO, "decimal con punto"),
                            (_MILES_COMA, "miles con coma"),
                            (_UNIDAD_PEGADA, "unidad pegada"),
                            (_RATIO_X, "ratio con x")):
            for m in rx.finditer(plano):
                avisos.append({"tipo": "formato_ingles",
                               "termino": f"{termino}: {m.group(0)}",
                               "contexto": _contexto(texto, m.start(), m.end())})
        return avisos
    except Exception:   # un detector jamas puede tumbar una lectura
        return []


# Columna `ai_*` de `test_executions` -> nombre de seccion que espera el
# detector. El nombre importa: decide si esa seccion puede dictaminar (D30).
SECCIONES_DEL_INFORME = {
    "ai_analysis_summary": "summary_table",
    "ai_analysis_errors": "errors",
    "ai_analysis_response_times": "chart_response_times",
    "ai_analysis_response_time_over_time": "chart_response_time_over_time",
    "ai_analysis_throughput": "chart_throughput",
    "ai_analysis_latency": "chart_latency",
    "ai_analysis_error_rate": "chart_error_rate",
    "ai_analysis_codes_per_second": "chart_codes_per_second",
    "ai_analysis_transactions_per_second": "chart_transactions_per_second",
    "ai_analysis_active_threads": "chart_active_threads",
    "ai_analysis_redirects": "redirects",
    "ai_conclusions": "conclusions",
    "ai_recommendations": "recommendations",
}


def avisos_de_ejecucion(execution) -> Dict[str, List[str]]:
    """D35/D36: los avisos del informe general de UNA ejecucion, al leerla.

    Devuelve {columna: [terminos]} y omite las secciones limpias, asi que un
    informe sin problemas devuelve `{}`. Se calcula en cada lectura: no hay
    columna nueva en base y el aviso desaparece solo al corregir el texto.
    """
    salida: Dict[str, List[str]] = {}
    for columna, seccion in SECCIONES_DEL_INFORME.items():
        terminos = terminos_de(detectar_estilo(getattr(execution, columna, None), seccion))
        if terminos:
            salida[columna] = terminos
    return salida


def terminos_de(avisos: List[Dict[str, str]]) -> List[str]:
    """Lista corta y sin repetir, para el aviso de pantalla (D36)."""
    vistos, salida = set(), []
    for a in avisos or []:
        t = (f"{a['termino']} sin traducir"
             if a.get("tipo") == "percentil_sin_traducir" else a.get("termino", ""))
        if t and t not in vistos:
            vistos.add(t)
            salida.append(t)
    return salida


# ====================================================================
# 5. TRAZABILIDAD DE CIFRAS (D37)
# ====================================================================

_NUMERO = re.compile(r"(?<![\w.,])\d[\d.,]*\d|(?<![\w.,])\d(?![\w.,])")


def _a_float(txt: str) -> Optional[float]:
    """'10.075'->10075 - '0,27'->0.27 - '179.73'->179.73 - '2,841'->2841."""
    t = (txt or "").strip().rstrip(".,")
    if not t:
        return None
    tiene_p, tiene_c = "." in t, "," in t
    try:
        if tiene_p and tiene_c:
            dec = "." if t.rindex(".") > t.rindex(",") else ","
            mil = "," if dec == "." else "."
            return float(t.replace(mil, "").replace(dec, "."))
        if tiene_c:
            ent, _, frac = t.rpartition(",")
            return float(t.replace(",", "")) if len(frac) == 3 and ent else float(t.replace(",", "."))
        if tiene_p:
            ent, _, frac = t.rpartition(".")
            return float(t.replace(".", "")) if len(frac) == 3 and ent else float(t)
        return float(t)
    except ValueError:
        return None


def _numeros(texto: str, saltar_numeracion: bool = False) -> List[tuple]:
    """[(texto_original, valor, posicion)]. Salta el '1.' de una lista numerada."""
    salida = []
    texto = texto or ""
    for m in _NUMERO.finditer(texto):
        if saltar_numeracion:
            ini_linea = texto.rfind("\n", 0, m.start()) + 1
            if (texto[ini_linea:m.start()].strip() == ""
                    and texto[m.end():m.end() + 2] in (". ", ") ", ".\n")):
                continue
        v = _a_float(m.group(0))
        if v is not None:
            salida.append((m.group(0), v, m.start()))
    return salida


def trazar_cifras(texto: Optional[str], datos_prompt: Optional[str]) -> Dict[str, Any]:
    """D37: cada cifra del analisis debe existir en los datos enviados al modelo.

    Tolerancia: 0,5 en absoluto o el 0,5% del valor, lo que sea mayor. Cubre el
    redondeo legitimo ('108,4 ms' contado como '108 ms') sin dejar pasar una
    cifra inventada. Solo reporta; no corrige nada.
    """
    if not texto or not str(texto).strip():
        return {"total": 0, "trazables": 0, "pct": None, "no_trazables": []}
    cifras = _numeros(str(texto), saltar_numeracion=True)
    fuente = [v for _, v, _ in _numeros(str(datos_prompt or ""))]
    no_trazables, trazables = [], 0
    for original, valor, pos in cifras:
        tol = max(0.5, abs(valor) * 0.005)
        if any(abs(valor - p) <= tol for p in fuente):
            trazables += 1
        else:
            no_trazables.append({"cifra": original, "valor": valor,
                                 "contexto": _contexto(str(texto), pos, pos + len(original))})
    total = len(cifras)
    return {"total": total, "trazables": trazables,
            "pct": round(trazables * 100.0 / total, 1) if total else None,
            "no_trazables": no_trazables}
