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

    >>> percentil_frase(90, 3515)
    '1 de cada 10 usuarios espera mas de 3,5 segundos (P90: 3.515 ms)'
    """
    cifra = f"(P{p}: {ms(valor_ms)})"
    if p == 50:
        return f"la mitad de los usuarios espera mas de {tiempo(valor_ms)} {cifra}"
    cada = _PERSONAS.get(p)
    if cada is None:
        return f"{tiempo(valor_ms)} {cifra}"
    return f"1 de cada {cada} usuarios espera mas de {tiempo(valor_ms)} {cifra}"


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

BLOQUE_ESTILO = """REGLAS DE ESTILO (obligatorias, se revisan antes de publicar)

QUIEN TE LEE: gerentes de TI y responsables de negocio. No son especialistas en
performance. Toda cifra tecnica tiene que llegarles traducida a lo que le pasa a
una persona usando la aplicacion.

1. VOCABULARIO PROHIBIDO. No escribas NUNCA estas palabras, ni siquiera dentro
   de una frase util: tier (ni "tier excelente", "tier aceptable", "tier
   degradado", "tier critico" ni ninguna variante), variabilidad, alta
   variabilidad, dispersion, latencia critica, veredicto, hallazgo, se
   evidencia, se observa que, cabe destacar, es importante mencionar, en
   conclusion. Si los datos que recibes usan alguna de esas palabras, tu texto
   NO la repite. En su lugar: "tiempos bajos" o "tiempos altos" o la cifra
   directamente; "unos usuarios esperan mucho mas que otros"; y para la
   latencia, el efecto concreto que produce.

2. PERCENTILES EN PERSONAS. Un percentil suelto no dice nada a quien te lee.
   P50 es la mitad de los usuarios, P90 es 1 de cada 10, P95 es 1 de cada 20 y
   P99 es 1 de cada 100. Esta es la forma exacta, copiala:
   "1 de cada 10 usuarios espera mas de 3,5 segundos (P90: 3.515 ms)"
   Primero las personas y el tiempo, la cifra tecnica despues entre parentesis.
   Los datos que recibes ya traen esa frase escrita: reutilizala tal cual.
   PROHIBIDO escribir "P90 de 3.515 ms" a secas.

3. FORMATO ESPANOL. Miles con punto y decimales con coma: 8.600 muestras,
   21.060 ms, 0,27%. La unidad va separada del numero (125 ms, 33,59 TPS,
   259,85 KB/s) y el simbolo de porcentaje va pegado (0,27%). Por encima de
   1.000 ms expresa el tiempo en segundos con un decimal (1,1 segundos); por
   debajo deja los milisegundos. Las cifras que recibes YA vienen en ese
   formato: copialas tal cual. PROHIBIDO el formato ingles (8,600 muestras,
   1.1 segundos, 179.73ms) y PROHIBIDO mezclar los dos estilos.

4. CIFRAS EXACTAS. Usa los valores reales tal como se te entregan. PROHIBIDO
   "cercano a", "aproximadamente", "alrededor de", "unos" o "valores estables
   en torno a" cuando el dato exacto esta en los datos entregados. PROHIBIDO
   inventar una cifra que no este en los datos.

5. RATIOS EN PALABRAS. Cada comparacion entre transacciones y cada pico va con
   su relacion numerica escrita en espanol: "3,9 veces mas lenta", "47,6 veces
   sobre su promedio". Los ratios ya vienen calculados en los datos: usalos tal
   cual. PROHIBIDO la forma inglesa "3.9x" o "21x".

6. SIN MARKDOWN. Nada de **, ##, *, -, ni vinetas con asteriscos o guiones.
   Nada de encerrar palabras entre asteriscos o comillas para dar enfasis. Los
   nombres de transaccion van en el texto tal cual, sin resaltar.

7. APERTURA CON DATO. La primera frase contiene una cifra concreta. PROHIBIDO
   abrir con "El grafico...", "El analisis muestra...", "Se observa...", "En el
   presente analisis...", "A continuacion se detalla...", "Como se puede
   apreciar...".

8. RAZONAR, NO DESCRIBIR. Cada dato relevante va con su lectura probable,
   marcada como hipotesis: "apunta a", "sugiere", "es coherente con".
   PROHIBIDO afirmar causas como hechos demostrados.

9. NARRA EL FLUJO DE NEGOCIO. Cuenta que hace el usuario paso a paso y agrupa
   las transacciones que se comportan igual en vez de listarlas una a una.
   Explica que significa funcionalmente lo que paso, no solo que numero salio.

10. EL VEREDICTO DE PRODUCCION NO VA AQUI. PROHIBIDO decir si el sistema esta
    listo, apto o no apto para produccion, si debe o no liberarse, o que hay
    que hacer antes de salir a produccion. Eso pertenece solo a las
    conclusiones y recomendaciones finales del informe. Un analisis describe,
    interpreta y senala el impacto; no dictamina. PROHIBIDO tambien convertir
    el analisis en lista de tareas ("se recomienda revisar...", "se sugiere
    optimizar...", "como oportunidad de mejora..."): eso son Recomendaciones.

11. CIERRE CON IMPACTO. Termina SIEMPRE con UNA frase sobre lo que percibira
    el usuario final en produccion, en lenguaje de negocio y sin tecnicismos
    (nada de percentiles, throughput o pool de conexiones en esa frase). Esa
    frase describe la experiencia de una persona; no es un dictamen sobre el
    sistema.

12. DENSIDAD. Si una frase no aporta dato, lectura o impacto, se borra. Fuera
    adverbios de adorno y frases que no cambian la decision de nadie.
    PROHIBIDO cerrar repitiendo lo ya dicho.

13. PICOS. Cuando el maximo se dispare frente al promedio (10 veces o mas) o
    supere los 10 segundos, dilo con su cifra y su causa probable. Esos picos
    no se omiten nunca, aunque el promedio se vea sano.

14. Escribe en parrafos narrativos fluidos de 2 a 4 oraciones. El texto debe
    leerse como si lo hubiera escrito una persona, no una maquina."""


PERMISO_VEREDICTO = """ESTA SECCION SI ES EL LUGAR DEL DICTAMEN (excepcion a la regla 10 del estilo).
Aqui SI debes decir si el sistema esta listo para produccion y que criterios se
cumplen o se incumplen, con sus cifras. Es la unica parte del informe donde eso
esta permitido. El resto de las reglas de estilo siguen vigentes sin cambios."""


# D31: la referencia §4.3 va como guia de TONO. La prohibicion de copiar es
# obligatoria porque su ejemplo aprobado usa el mismo dataset que una de las
# pruebas reales (reporte 30 §4.3): sin esta advertencia no habria forma de
# distinguir un texto bien hecho de una copia del ejemplo.
REFERENCIA_ESTILO = """EJEMPLO DE TONO (de OTRA prueba, solo por su forma de redactar):

"La prueba ejecuto un total de 10.075 transacciones, obteniendo un 28,20% de
errores globales (2.841 errores). El comportamiento de la aplicacion fue estable
durante los tres primeros pasos del flujo (Auth, Get Booking y Post Create
Booking), los cuales registraron 0% de errores y tiempos de respuesta adecuados
para una carga de 10 usuarios concurrentes. Sin embargo, a partir de las
operaciones que interactuan con el identificador de la reserva se presento una
degradacion funcional significativa, evidenciada por porcentajes de error de
41,26%, 56,77% y 71,42%, respectivamente. Estos resultados indican que la
aplicacion logra crear las reservas correctamente, pero presenta problemas al
consultarlas, actualizarlas o eliminarlas posteriormente."

Fijate en lo que hace: narra el flujo de negocio en orden, agrupa lo que se
comporta igual, explica que significa funcionalmente y no usa ni una palabra de
jerga.

PROHIBIDO ABSOLUTAMENTE copiar de ese ejemplo sus cifras, sus porcentajes, sus
nombres de transaccion o sus frases literales. Pertenecen a otra prueba. Usa
UNICAMENTE los datos que se te entregan mas abajo. Si tu texto repite una cifra
o un nombre del ejemplo que no este en tus datos, esta mal."""


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
