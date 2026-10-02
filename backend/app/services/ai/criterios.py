"""Los criterios de aceptación que ve la IA (ETAPA 5b, D55).

v1.2 §2.2 dejó que cada transacción pueda tener sus propios criterios, y la
tabla de veredictos ya los usaba. Los prompts, no: los seis de cada transacción
no recibían ningún criterio y los del informe general solo veían el global. Un
texto podía así afirmar que una transacción va bien "porque está por debajo de
los 2.000 ms" mientras la tabla la marcaba NO APTO contra su límite propio de
300 ms.

Este módulo es **la única** resolución del umbral efectivo. La misma regla que
usa `compute_per_transaction_verdicts` para calcular los veredictos —de hecho esa
función la llama a ella— para que el texto y la tabla no puedan discrepar.

BLOQUE 5 (reporte 147): los criterios del «Analista IA» son una lista libre y
pueden no traer alguno de los tres del motor. Con ellos (`declarados`), lo que
falta queda SIN límite —None— en vez de rellenarse con 2.000 ms o 99 %. El flujo
de siempre manda siempre los tres y se comporta exactamente igual que antes.

Nada de aquí llama a la IA ni toca la base: son funciones puras que arman texto.
"""
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai.estilo import ms, num, pct

# Los mismos valores por defecto que traía `compute_verdict` desde siempre.
RT_DEFECTO = 2000.0
DISPONIBILIDAD_DEFECTO = 99.0

PROPIO = "límite propio de esta transacción"
GENERAL = "criterio general de la prueba"

# BLOQUE 5: las claves del motor. Un dict de criterios que no trae NINGUNA (solo
# la ficha del analista, o solo las transacciones marcadas) no tiene criterios
# numéricos aunque no esté vacío.
CLAVES_MOTOR = ("concurrency", "response_time", "availability", "per_transaction")


def declarados(criterios: Optional[Dict[str, Any]]) -> bool:
    """¿Los criterios vienen del «Analista IA»? (BLOQUE 5)

    En ese modo una clave que falta NO se rellena con el valor por defecto: el
    analista no la declaró, y el motor no puede juzgar contra un límite inventado.
    """
    return bool(criterios) and isinstance(criterios.get("analista"), dict)


def _numericos(criterios: Optional[Dict[str, Any]]) -> bool:
    """¿Hay criterios con cifras que se puedan comparar?

    `raw_text` son criterios escritos a mano en prosa: no se pueden evaluar y
    todo el cálculo de veredictos ya los ignora. Aquí igual. BLOQUE 5: hace falta
    además al menos una clave del motor (antes bastaba con que el dict no
    estuviera vacío; las 77 ejecuciones con criterios de la base traen las tres).
    """
    return (bool(criterios) and not criterios.get("raw_text")
            and any(criterios.get(k) for k in CLAVES_MOTOR))


tiene_numericos = _numericos


def evaluables(criterios: Optional[Dict[str, Any]]) -> bool:
    """¿Hay un tiempo o una disponibilidad contra los que dar un veredicto?

    En el flujo de siempre es lo mismo que `tiene_numericos` (los defectos cubren
    lo que falte). Con criterios del analista hace falta que haya declarado al
    menos uno de los dos, global o de una transacción: la concurrencia sola no da
    veredicto.
    """
    if not _numericos(criterios):
        return False
    if not declarados(criterios):
        return True
    if criterios.get("response_time") or criterios.get("availability"):
        return True
    return any((p or {}).get("response_time") or (p or {}).get("availability")
               for p in (criterios.get("per_transaction") or {}).values())


def _f(valor, defecto: Optional[float]) -> Optional[float]:
    return float(valor) if valor else defecto


def criterios_efectivos(criterios: Optional[Dict[str, Any]],
                        label: str) -> Tuple[Optional[float], Optional[float], bool]:
    """El umbral que le toca a UNA transacción -> (tiempo, disponibilidad, propios).

    `propios` dice si salieron de `per_transaction` o si son los generales, que es
    lo que el prompt tiene que poder nombrar (D55).

    BLOQUE 5: con criterios del analista, lo no declarado vuelve como None. En el
    flujo de siempre nunca es None.
    """
    criterios = criterios or {}
    sin_defecto = declarados(criterios)
    rt_global = _f(criterios.get("response_time"), None if sin_defecto else RT_DEFECTO)
    disp_global = _f(criterios.get("availability"), None if sin_defecto else DISPONIBILIDAD_DEFECTO)
    propios = (criterios.get("per_transaction") or {}).get(label) or {}
    if not propios:
        return rt_global, disp_global, False
    return (
        _f(propios.get("response_time"), rt_global),
        _f(propios.get("availability"), disp_global),
        True,
    )


def con_criterio_propio(criterios: Optional[Dict[str, Any]]) -> List[Tuple[str, Optional[float], Optional[float]]]:
    """Las transacciones que tienen criterio propio, ordenadas por nombre."""
    if not _numericos(criterios):
        return []
    salida = []
    for label in sorted((criterios.get("per_transaction") or {}).keys()):
        rt, disp, _ = criterios_efectivos(criterios, label)
        salida.append((label, rt, disp))
    return salida


def _lineas_tx(rt: Optional[float], disp: Optional[float], origen: str) -> str:
    lineas = []
    if rt is not None:
        lineas.append(f"- Tiempo de respuesta máximo: {ms(rt)} ({origen})")
    if disp is not None:
        lineas.append(f"- Disponibilidad mínima: {pct(disp, 1)} ({origen})")
    if rt is not None:
        lineas.append(f"- El tiempo se compara contra el P90: 1 de cada 10 usuarios no debería pasar de {ms(rt)}.")
    return "\n".join(lineas)


def bloque_de_transaccion(criterios: Optional[Dict[str, Any]], label: str) -> str:
    """El bloque de criterios para los SEIS prompts de una transacción.

    Sin criterios numéricos devuelve cadena vacía y el prompt queda exactamente
    como el de hoy: una ejecución sin criterios no cambia ni un carácter.
    """
    if not _numericos(criterios):
        return ""
    rt, disp, propios = criterios_efectivos(criterios, label)
    if rt is None and disp is None:
        return ""   # BLOQUE 5: el analista no declaró ninguno de los dos
    origen = PROPIO if propios else GENERAL
    aviso = (
        "Esta transacción tiene un límite PROPIO, distinto del general de la prueba: "
        "júzgala solo contra él."
        if propios else
        "Esta transacción no tiene límite propio, así que se mide con el criterio "
        "general de la prueba."
    )
    return f"""
CRITERIO DE ACEPTACIÓN QUE SE LE APLICA A "{label}":
{_lineas_tx(rt, disp, origen)}
{aviso}
Si la cifra de esta transacción supera ese límite, dilo con el límite delante; si
no lo supera, no lo presentes como si cumpliera otro distinto.
"""


def bloque_general(criterios: Optional[Dict[str, Any]]) -> str:
    """La lista de transacciones con criterio propio, para los prompts generales.

    Va DESPUÉS del bloque de criterios globales que esos prompts ya traían: no lo
    sustituye, lo completa. Sin ninguna transacción con criterio propio devuelve
    cadena vacía y el prompt queda como el de hoy.
    """
    propias = con_criterio_propio(criterios)
    if not propias:
        return ""
    filas = "\n".join(
        f'- "{label}": ' + ", ".join(
            ([f"tiempo de respuesta máximo {ms(rt)}"] if rt is not None else [])
            + ([f"disponibilidad mínima {pct(disp, 1)}"] if disp is not None else []))
        for label, rt, disp in propias
    )
    return f"""
TRANSACCIONES CON CRITERIO PROPIO ({len(propias)}), que NO se miden con el criterio general:
{filas}
Las demás sí se miden con el criterio general de arriba.
IMPORTANTE: al hablar de cualquiera de estas transacciones usa SU límite, no el
general. La tabla de veredictos del informe ya está calculada así, y el texto no
puede contradecirla.
"""


def bloque_completo(criterios: Optional[Dict[str, Any]]) -> str:
    """Criterios globales **y** la lista de excepciones, en un solo bloque.

    Para los prompts generales que hasta ahora no recibían ningún criterio —los
    errores y las seis gráficas—, que necesitan las dos mitades. Los tres que ya
    traían su bloque global (resumen, conclusiones, recomendaciones) usan
    `bloque_general`, que solo añade la lista.

    Sin criterios numéricos devuelve cadena vacía: el prompt queda como el de hoy.
    """
    if not _numericos(criterios):
        return ""
    criterios = criterios or {}
    sin_defecto = declarados(criterios)   # BLOQUE 5: solo lo declarado
    partes = ["\nCRITERIOS DE ACEPTACIÓN DE LA PRUEBA:"]
    if criterios.get("concurrency"):
        partes.append(f"- Concurrencia esperada: {num(criterios['concurrency'])} usuarios")
    if criterios.get("response_time") or not sin_defecto:
        partes.append(f"- Tiempo de respuesta máximo: {ms(criterios.get('response_time') or RT_DEFECTO)}")
    if criterios.get("availability") or not sin_defecto:
        partes.append(
            f"- Disponibilidad mínima: {pct(criterios.get('availability') or DISPONIBILIDAD_DEFECTO, 1)}")
    return "\n".join(partes) + "\n" + bloque_general(criterios)
