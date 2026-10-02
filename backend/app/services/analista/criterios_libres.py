"""Los criterios de aceptación como LISTA LIBRE — BLOQUE 5, parte A.3.

No hay campos fijos: cada criterio es lo que dijo el analista, con su tipo y,
cuando se puede, su forma medible (métrica, operador, valor, unidad, alcance).

**El resultado lo calcula este módulo con el JTL, nunca la IA.** Lo que la IA
devuelva en `resultado` se ignora: aquí se recalcula siempre.

    cumple · no_cumple · no_evaluado (con motivo) · lo_confirma_el_analista

Los que encajan con los tres del motor (tiempo por P90, disponibilidad o tasa
de error, concurrencia) se traducen a las claves de siempre (`a_motor`) y
alimentan la marca «crítica» y el veredicto exactamente como hoy.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.ai.estilo import ms, num, pct

TIPOS = ("tiempo_respuesta", "disponibilidad_o_error", "concurrencia", "caudal", "proceso", "otro")
OPERADORES = ("<", "<=", ">", ">=", "=")
RESULTADOS = ("cumple", "no_cumple", "no_evaluado", "lo_confirma_el_analista")
ESTADOS_LISTA = ("sin_declarar", "declarados", "no_hay_criterios_acordados")

METRICAS = {
    "tiempo_respuesta": ("promedio", "mediana", "p90", "p95", "p99", "max"),
    "disponibilidad_o_error": ("disponibilidad", "tasa_error", "errores"),
    "concurrencia": ("usuarios",),
    "caudal": ("caudal",),
    "proceso": ("registros_en_tiempo", "duracion", "registros"),
    "otro": (),
}
# unidad -> factor a la unidad base del tipo (ms, %, usuarios, por segundo, segundos)
UNIDADES = {
    "tiempo_respuesta": {"ms": 1.0, "s": 1000.0, "min": 60000.0},
    "disponibilidad_o_error": {"%": 1.0, "errores": 1.0},
    "concurrencia": {"usuarios": 1.0},
    "caudal": {"por_segundo": 1.0, "por_minuto": 1 / 60.0, "por_hora": 1 / 3600.0},
    "proceso": {"s": 1.0, "min": 60.0, "h": 3600.0},
    "otro": {},
}
OPERADOR_DEFECTO = {"tiempo_respuesta": "<=", "disponibilidad_o_error": None, "concurrencia": ">=",
                    "caudal": ">=", "proceso": "<=", "otro": None}
MAX_CRITERIOS = 30
MAX_TEXTO = 500

_NOMBRE_METRICA = {"promedio": "promedio", "mediana": "mediana", "p90": "P90", "p95": "P95",
                   "p99": "P99", "max": "máximo"}


class CriterioInvalido(ValueError):
    pass


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def _cmp(medido: float, op: str, valor: float) -> bool:
    m = round(float(medido), 4)
    return {"<": m < valor, "<=": m <= valor, ">": m > valor, ">=": m >= valor,
            "=": math.isclose(m, valor, rel_tol=1e-9, abs_tol=1e-6)}[op]


_OP_TXT = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "=": "="}


def normalizar(entrada: Dict[str, Any], labels: List[str], cid: str, origen: str) -> Dict[str, Any]:
    """Un criterio tal como se guarda, SIN resultado. Lanza `CriterioInvalido` si
    no tiene texto o trae un tipo, operador o unidad que no existen: eso es un
    error de quien lo manda. Lo que falte para medirlo no es error: se guarda y
    sale `no_evaluado` con su motivo."""
    texto = str(entrada.get("texto") or "").strip()
    if not texto:
        raise CriterioInvalido("el criterio no trae el texto del analista")
    if len(texto) > MAX_TEXTO:
        raise CriterioInvalido(f"el texto del criterio pasa de {MAX_TEXTO} caracteres")
    tipo = entrada.get("tipo") or "otro"
    if tipo not in TIPOS:
        raise CriterioInvalido(f"tipo de criterio desconocido: {tipo}")
    metrica = entrada.get("metrica") or None
    if metrica is not None and metrica not in METRICAS[tipo]:
        raise CriterioInvalido(f"la métrica «{metrica}» no corresponde a un criterio de {tipo}")
    if tipo == "tiempo_respuesta" and metrica is None:
        metrica = "p90"   # como el resto del informe: el tiempo se mide por el P90
    if tipo == "concurrencia":
        metrica = "usuarios"
    if tipo == "caudal":
        metrica = "caudal"
    operador = entrada.get("operador") or OPERADOR_DEFECTO.get(tipo)
    if operador is not None and operador not in OPERADORES:
        raise CriterioInvalido(f"operador desconocido: {operador}")
    unidad = entrada.get("unidad") or None
    if unidad is not None and unidad not in UNIDADES[tipo]:
        raise CriterioInvalido(f"la unidad «{unidad}» no corresponde a un criterio de {tipo}")
    if unidad is None:
        unidad = {"tiempo_respuesta": "ms", "concurrencia": "usuarios", "caudal": "por_segundo"}.get(tipo)
        if tipo == "disponibilidad_o_error" and metrica:
            unidad = "errores" if metrica == "errores" else "%"
        if tipo == "proceso" and metrica in ("registros_en_tiempo", "duracion"):
            unidad = "min"
    valor, cantidad = entrada.get("valor"), entrada.get("cantidad")
    for nombre, v in (("valor", valor), ("cantidad", cantidad)):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(float(v)) or float(v) < 0):
            raise CriterioInvalido(f"el {nombre} del criterio no es un número válido")
    transaccion = entrada.get("transaccion") or None
    if transaccion is not None:
        transaccion = str(transaccion).strip()
        exacta = next((l for l in labels if l == transaccion), None) or \
            next((l for l in labels if _norm(l) == _norm(transaccion)), None)
        transaccion = exacta or transaccion
    return {
        "id": cid,
        "texto": texto,
        "tipo": tipo,
        "metrica": metrica,
        "operador": operador,
        "valor": float(valor) if valor is not None else None,
        "unidad": unidad,
        "cantidad": float(cantidad) if cantidad is not None else None,
        "alcance": {"tipo": "transaccion" if transaccion else "global", "transaccion": transaccion},
        "origen": origen,
        "confirmacion": None,
        "en_motor": False,
        "resultado": None,
    }


# ------------------------------------------------------------------ evaluación

class Datos:
    """Lo que hace falta para medir: las cifras de la ficha y, solo para los
    criterios de proceso, el DataFrame (que se carga una vez y solo si hace falta)."""

    def __init__(self, ficha: Dict[str, Any], cargar_df: Optional[Callable[[], Any]] = None):
        self.cifras = ficha.get("cifras") or {}
        self.tx = {t["label"]: t for t in ficha.get("transacciones") or []}
        self.fases = ficha.get("fases") or {}
        self._cargar = cargar_df
        self._df = None

    def df(self):
        if self._df is None and self._cargar is not None:
            self._df = self._cargar()
        return self._df


def _res(estado, medido=None, unidad=None, texto="", motivo=None, nota=None):
    return {"estado": estado, "medido": medido, "unidad": unidad, "texto": texto,
            "motivo": motivo, "nota": nota}


def _fmt(tipo: str, valor: float, unidad: Optional[str]) -> str:
    if tipo == "tiempo_respuesta":
        return {"ms": ms(valor), "s": f"{num(valor, 1)} s", "min": f"{num(valor, 1)} min"}.get(unidad, ms(valor))
    if unidad == "%":
        return pct(valor, 2)
    if unidad == "errores":
        return f"{num(valor)} errores"
    if unidad == "usuarios":
        return f"{num(valor)} usuarios"
    if tipo == "caudal":
        return {"por_segundo": f"{num(valor, 2)} por segundo", "por_minuto": f"{num(valor, 1)} por minuto",
                "por_hora": f"{num(valor)} por hora"}.get(unidad, num(valor, 2))
    if unidad in ("s", "min", "h"):
        return f"{num(valor, 1)} {unidad}"
    return num(valor, 2)


def evaluar(c: Dict[str, Any], d: Datos) -> Dict[str, Any]:
    """El resultado de UN criterio, calculado con el JTL."""
    tipo, metrica, op, valor = c["tipo"], c.get("metrica"), c.get("operador"), c.get("valor")
    label = (c.get("alcance") or {}).get("transaccion")
    if tipo == "otro":
        return _res("lo_confirma_el_analista",
                    motivo="Kinetix no puede medirlo con el JTL: lo confirma el analista.")
    if label is not None and label not in d.tx:
        return _res("no_evaluado", motivo=f"la transacción «{label}» no está en el JTL")
    if tipo == "proceso":
        return _evaluar_proceso(c, d, label)
    if metrica is None:
        return _res("no_evaluado", motivo="falta saber qué se mide (la métrica)")
    if valor is None:
        return _res("no_evaluado", motivo="falta el valor del criterio")
    if op is None:
        return _res("no_evaluado", motivo="falta saber si es un máximo o un mínimo")
    unidad = c.get("unidad")
    factor = UNIDADES[tipo].get(unidad, 1.0)
    limite_base = valor * factor
    fila = d.tx.get(label) if label else None
    donde = f"«{label}»" if label else "toda la prueba"

    if tipo == "tiempo_respuesta":
        clave_g = {"promedio": "promedio_ms", "mediana": "mediana_ms", "p90": "p90_ms", "p95": "p95_ms",
                   "p99": "p99_ms", "max": "max_ms"}[metrica]
        medido = float(fila[metrica]) if fila else d.cifras.get(clave_g)
        if medido is None:
            return _res("no_evaluado", motivo="el JTL no permite calcular esa métrica")
        ok = _cmp(medido, op, limite_base)
        nota = None
        if not label and metrica in ("p90", "p95", "p99", "promedio", "mediana", "max"):
            fuera = [t for t in d.tx.values() if not _cmp(float(t[metrica]), op, limite_base)]
            if fuera:
                nota = (f"{num(len(fuera))} de {num(len(d.tx))} transacciones no lo cumplen por su cuenta "
                        f"({', '.join('«' + t['label'] + '»' for t in fuera[:5])}"
                        f"{'…' if len(fuera) > 5 else ''})")
        return _res("cumple" if ok else "no_cumple", round(medido, 2), "ms",
                    f"{_NOMBRE_METRICA[metrica]} de {donde}: {ms(medido)} frente a "
                    f"{_OP_TXT[op]} {_fmt(tipo, valor, unidad)}", nota=nota)

    if tipo == "disponibilidad_o_error":
        tasa = float(fila["tasa_error"]) if fila else float(d.cifras.get("tasa_error", 0))
        if metrica == "disponibilidad":
            medido, u, txt = 100.0 - tasa, "%", f"disponibilidad de {donde}: {pct(100.0 - tasa, 2)}"
        elif metrica == "tasa_error":
            medido, u, txt = tasa, "%", f"tasa de error de {donde}: {pct(tasa, 2)}"
        else:
            medido = float(fila["errores"]) if fila else float(d.cifras.get("errores", 0))
            u, txt = "errores", f"errores de {donde}: {num(medido)}"
        ok = _cmp(medido, op, limite_base)
        return _res("cumple" if ok else "no_cumple", round(medido, 4), u,
                    f"{txt} frente a {_OP_TXT[op]} {_fmt(tipo, valor, unidad)}")

    if tipo == "concurrencia":
        if label:
            return _res("no_evaluado", motivo="la concurrencia es de toda la prueba, no de una transacción")
        maximo = (d.fases or {}).get("max_usuarios")
        if not maximo:
            return _res("no_evaluado", motivo="el JTL no trae el número de usuarios activos")
        ok = _cmp(maximo, op, limite_base)
        return _res("cumple" if ok else "no_cumple", float(maximo), "usuarios",
                    f"máximo de usuarios activos: {num(maximo)} frente a {_OP_TXT[op]} {num(valor)}")

    if tipo == "caudal":
        medido = float(fila["tps"]) if fila else float(d.cifras.get("caudal", 0))
        ok = _cmp(medido, op, limite_base)
        return _res("cumple" if ok else "no_cumple", round(medido, 4), "por_segundo",
                    f"caudal de {donde} (todas las peticiones): {num(medido, 2)} por segundo frente a "
                    f"{_OP_TXT[op]} {_fmt(tipo, valor, unidad)}")
    return _res("no_evaluado", motivo="tipo sin evaluación")


SUPUESTO = "se cuenta cada petición correcta como un registro"


def _evaluar_proceso(c, d: Datos, label) -> Dict[str, Any]:
    """«procesar 20.000 registros en menos de 30 minutos». Con el JTL se puede si
    una petición correcta es un registro; si las cuentas no llegan, lo confirma
    el analista (puede que un registro no sea una petición)."""
    metrica, op, valor, cantidad = c.get("metrica"), c.get("operador") or "<=", c.get("valor"), c.get("cantidad")
    if metrica is None:
        metrica = "registros_en_tiempo" if (cantidad and valor is not None) else \
            ("registros" if cantidad else ("duracion" if valor is not None else None))
    if metrica is None:
        return _res("lo_confirma_el_analista",
                    motivo="no se pudo leer ni una cantidad ni un tiempo: lo confirma el analista")
    df = d.df()
    if df is None or len(df) == 0:
        return _res("lo_confirma_el_analista", motivo="no se pudo leer el JTL para medirlo")
    from app.services.ai.resumen_serie import _ok
    t0 = df["timestamp"].min()
    sub = df[df["label"] == label] if label else df
    ok = sub[_ok(sub)]
    fin = (ok["timestamp"] - t0).dt.total_seconds() + ok["elapsed"].astype(float) / 1000.0
    fin = fin.sort_values().to_numpy()
    n_ok = len(fin)
    donde = f" de «{label}»" if label else ""
    unidad = c.get("unidad") or "min"
    factor = UNIDADES["proceso"].get(unidad, 60.0)

    if metrica in ("registros_en_tiempo", "registros"):
        if not cantidad:
            return _res("no_evaluado", motivo="falta la cantidad de registros")
        n = int(math.ceil(cantidad))
        if n_ok < n:
            dur = (fin[-1] / factor) if n_ok else 0
            return _res("lo_confirma_el_analista", float(n_ok), "registros",
                        f"el JTL registra {num(n_ok)} peticiones correctas{donde} en "
                        f"{_fmt('proceso', dur, unidad)}, menos que los {num(n)} registros",
                        motivo=("puede que un registro no sea una petición, o que el proceso siguiera "
                                "fuera de la prueba: lo confirma el analista"))
        if metrica == "registros" or valor is None:
            return _res("cumple", float(n_ok), "registros",
                        f"{num(n_ok)} peticiones correctas{donde} frente a {num(n)} registros", nota=SUPUESTO)
        t = fin[n - 1] / factor
        cumple = _cmp(t, op, valor)
        return _res("cumple" if cumple else "no_cumple", round(t, 2), unidad,
                    f"las {num(n)} primeras peticiones correctas{donde} terminaron en "
                    f"{_fmt('proceso', t, unidad)} desde el inicio, frente a {_OP_TXT[op]} "
                    f"{_fmt('proceso', valor, unidad)}", nota=SUPUESTO)

    # duracion: lo que tarda el alcance entero, de su primera petición a la última
    if valor is None:
        return _res("no_evaluado", motivo="falta el tiempo del criterio")
    if not len(sub):
        return _res("no_evaluado", motivo="no hay peticiones en ese alcance")
    ini = (sub["timestamp"].min() - t0).total_seconds()
    ult = ((sub["timestamp"] - t0).dt.total_seconds() + sub["elapsed"].astype(float) / 1000.0).max()
    t = (ult - ini) / factor
    cumple = _cmp(t, op, valor)
    return _res("cumple" if cumple else "no_cumple", round(t, 2), unidad,
                f"duración{donde or ' de la prueba'}: {_fmt('proceso', t, unidad)} frente a "
                f"{_OP_TXT[op]} {_fmt('proceso', valor, unidad)}",
                nota="se mide la duración del JTL: si el proceso siguió fuera de la prueba, lo dice el analista")


# ------------------------------------------------------------------ el motor

def a_motor(lista: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """Las claves de siempre (`response_time`, `availability`, `concurrency`,
    `per_transaction`) a partir de los criterios que encajan, y sus ids.

    Encajan: tiempo medido por el P90 como máximo (es lo que compara el motor),
    disponibilidad mínima o tasa de error máxima, y concurrencia global. Si hay
    varios del mismo, gana el más exigente."""
    motor: Dict[str, Any] = {}
    por_tx: Dict[str, Dict[str, float]] = {}
    ids: List[str] = []
    for c in lista:
        r = c.get("resultado") or {}
        if r.get("estado") == "no_evaluado" or c.get("valor") is None:
            continue
        tipo, metrica, op = c["tipo"], c.get("metrica"), c.get("operador")
        label = (c.get("alcance") or {}).get("transaccion")
        destino = por_tx.setdefault(label, {}) if label else motor
        factor = UNIDADES[tipo].get(c.get("unidad"), 1.0)
        v = c["valor"] * factor
        if tipo == "tiempo_respuesta" and metrica == "p90" and op in ("<", "<="):
            destino["response_time"] = min(v, destino.get("response_time", v))
        elif tipo == "disponibilidad_o_error" and metrica == "disponibilidad" and op in (">", ">="):
            destino["availability"] = max(v, destino.get("availability", v))
        elif tipo == "disponibilidad_o_error" and metrica == "tasa_error" and op in ("<", "<="):
            destino["availability"] = max(100.0 - v, destino.get("availability", 100.0 - v))
        elif tipo == "concurrencia" and not label and op in (">=", ">", "="):
            destino["concurrency"] = int(v)
        else:
            continue
        ids.append(c["id"])
    if por_tx:
        motor["per_transaction"] = por_tx
    return motor, ids


def recalcular(lista: List[Dict[str, Any]], d: Datos, solo: Optional[set] = None) -> None:
    """Pone `resultado` y `en_motor` en cada criterio. `solo` limita el cálculo a
    unos ids (los nuevos o editados): el JTL no cambia, así que los demás ya están."""
    for c in lista:
        if solo is None or c["id"] in solo or c.get("resultado") is None:
            c["resultado"] = evaluar(c, d)
    _, ids = a_motor(lista)
    for c in lista:
        c["en_motor"] = c["id"] in ids


def estado_de_lista(lista: List[Dict[str, Any]], ninguno: bool) -> str:
    if lista:
        return "declarados"
    return "no_hay_criterios_acordados" if ninguno else "sin_declarar"
