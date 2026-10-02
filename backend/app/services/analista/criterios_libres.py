"""Los criterios de aceptación como LISTA LIBRE — BLOQUE 5 (147), rehecho en el 150.

No hay campos fijos: cada criterio es lo que dijo el analista, con su tipo y,
cuando se puede, su forma medible (métrica, operador, valor, unidad, alcance).

**El resultado lo calcula este módulo con el JTL, nunca la IA.** Lo que la IA
devuelva en `resultado` se ignora: aquí se recalcula siempre.

    cumple · no_cumple · no_evaluado (con motivo) · lo_confirma_el_analista

REPORTE 150 (la primera prueba real de Fredy):
  - ALCANCE. Si el analista nombra servicios, el criterio se evalúa sobre ESAS
    transacciones: cada una por separado («transacciones») o sumadas («suma»,
    «N entre A y B»). Sin servicios, los tiempos, errores y caudal valen para
    CADA transacción; el volumen, el proceso y la concurrencia necesitan saber a
    cuál se refieren. **Nunca se evalúa contra el total de la prueba salvo que
    el analista lo diga** (`toda_la_prueba`).
  - TIEMPO por transacción y con su medida. Sin medida, P90 y la ficha lo dice
    (`metrica_supuesta`). Si alguna transacción del alcance no cumple, el
    criterio es no_cumple y se nombra cuál. Nada de «cumple» con una nota debajo.
  - VOLUMEN: peticiones correctas de una transacción en la duración (o en la
    ventana que dijo el analista), calculado. «Lo confirma el analista» queda
    solo para lo que el JTL no puede medir.
  - Cada resultado lleva el detalle por transacción (`por_transaccion`) y las
    que fallan (`fallan`): la ficha los agrupa por servicio y el veredicto sale
    de ahí (`veredicto`).
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.ai.estilo import ms, num, pct

TIPOS = ("tiempo_respuesta", "disponibilidad_o_error", "concurrencia", "caudal", "volumen", "proceso", "otro")
OPERADORES = ("<", "<=", ">", ">=", "=")
RESULTADOS = ("cumple", "no_cumple", "no_evaluado", "lo_confirma_el_analista")
ESTADOS_LISTA = ("sin_declarar", "declarados", "no_hay_criterios_acordados")
ALCANCES = ("global", "transacciones", "suma", "cada_transaccion")

METRICAS = {
    "tiempo_respuesta": ("promedio", "mediana", "p90", "p95", "p99", "max"),
    "disponibilidad_o_error": ("disponibilidad", "tasa_error", "errores"),
    "concurrencia": ("usuarios",),
    "caudal": ("caudal",),
    "volumen": ("peticiones_correctas", "peticiones"),
    "proceso": ("registros_en_tiempo", "duracion", "registros"),
    "otro": (),
}
# unidad -> factor a la unidad base del tipo (ms, %, usuarios, por segundo, peticiones, segundos)
UNIDADES = {
    "tiempo_respuesta": {"ms": 1.0, "s": 1000.0, "min": 60000.0},
    "disponibilidad_o_error": {"%": 1.0, "errores": 1.0},
    "concurrencia": {"usuarios": 1.0},
    "caudal": {"por_segundo": 1.0, "por_minuto": 1 / 60.0, "por_hora": 1 / 3600.0},
    "volumen": {"peticiones": 1.0},
    "proceso": {"s": 1.0, "min": 60.0, "h": 3600.0},
    "otro": {},
}
VENTANA = {"s": 1.0, "min": 60.0, "h": 3600.0}
OPERADOR_DEFECTO = {"tiempo_respuesta": "<=", "disponibilidad_o_error": None, "concurrencia": ">=",
                    "caudal": ">=", "volumen": ">=", "proceso": "<=", "otro": None}
# Sin servicios nombrados: estos valen para cada transacción; los demás piden alcance.
POR_DEFECTO_CADA = ("tiempo_respuesta", "disponibilidad_o_error", "caudal")
MAX_CRITERIOS = 30
MAX_TEXTO = 500

NOMBRE_METRICA = {"promedio": "promedio", "mediana": "mediana", "p90": "P90", "p95": "P95",
                  "p99": "P99", "max": "máximo"}
_CLAVE_GLOBAL = {"promedio": "promedio_ms", "mediana": "mediana_ms", "p90": "p90_ms", "p95": "p95_ms",
                 "p99": "p99_ms", "max": "max_ms"}


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


def _resolver(nombre: str, labels: List[str]) -> str:
    """El nombre del JTL que corresponde a lo que escribió el analista: exacto,
    sin tildes ni mayúsculas, o sin el número de orden («Receptor» →
    «1. Webhook_Receptor»), si solo hay uno que encaje."""
    nombre = str(nombre).strip()
    exacta = next((l for l in labels if l == nombre), None) or \
        next((l for l in labels if _norm(l) == _norm(nombre)), None)
    if exacta:
        return exacta
    n = _norm(nombre)
    sin_orden = [l for l in labels if _norm(re.sub(r"^\s*\d+[.)]\s*", "", l)) == n]
    if len(sin_orden) == 1:
        return sin_orden[0]
    # Sin separadores: «asegurar fondos» está en «1. SaveFunds_AsegurarFondos».
    compacto = lambda t: re.sub(r"[^a-z0-9]", "", _norm(t))
    nc = compacto(nombre)
    contiene = [l for l in labels if nc and nc in compacto(l)]
    if len(contiene) == 1:
        return contiene[0]
    # Por parecido de palabras: «originador» ~ «Webhook_Originator».
    import difflib
    piezas = {l: [p for p in re.split(r"[^a-z0-9]+", _norm(re.sub(r"([a-z])([A-Z])", r"\1 \2", l))) if p]
              for l in labels}
    mejor = sorted(((max((difflib.SequenceMatcher(None, nc, p).ratio() for p in ps), default=0), l)
                    for l, ps in piezas.items()), reverse=True)
    if mejor and mejor[0][0] >= 0.8 and (len(mejor) == 1 or mejor[1][0] < mejor[0][0]):
        return mejor[0][1]
    return nombre


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
    supuesta = False
    if tipo == "tiempo_respuesta" and metrica is None:
        # 150: la IA pregunta la medida una vez; si no se sabe, P90 y la ficha lo dice.
        metrica, supuesta = "p90", True
    supuesta = supuesta or bool(entrada.get("metrica_supuesta"))
    if tipo == "concurrencia":
        metrica = "usuarios"
    if tipo == "caudal":
        metrica = "caudal"
    if tipo == "volumen" and metrica is None:
        metrica = "peticiones_correctas"
    operador = entrada.get("operador") or OPERADOR_DEFECTO.get(tipo)
    if operador is None and tipo == "disponibilidad_o_error" and metrica:
        # la disponibilidad es un mínimo; la tasa de error y los errores, un máximo
        operador = ">=" if metrica == "disponibilidad" else "<="
    if operador is not None and operador not in OPERADORES:
        raise CriterioInvalido(f"operador desconocido: {operador}")
    unidad = entrada.get("unidad") or None
    if unidad is not None and unidad not in UNIDADES[tipo]:
        raise CriterioInvalido(f"la unidad «{unidad}» no corresponde a un criterio de {tipo}")
    if unidad is None:
        unidad = {"tiempo_respuesta": "ms", "concurrencia": "usuarios", "caudal": "por_segundo",
                  "volumen": "peticiones"}.get(tipo)
        if tipo == "disponibilidad_o_error" and metrica:
            unidad = "errores" if metrica == "errores" else "%"
        if tipo == "proceso" and metrica in ("registros_en_tiempo", "duracion"):
            unidad = "min"
    valor, cantidad = entrada.get("valor"), entrada.get("cantidad")
    ventana_valor, ventana_unidad = entrada.get("ventana_valor"), entrada.get("ventana_unidad") or None
    for nombre, v in (("valor", valor), ("cantidad", cantidad), ("ventana", ventana_valor)):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not math.isfinite(float(v)) or float(v) < 0):
            raise CriterioInvalido(f"el {nombre} del criterio no es un número válido")
    if ventana_valor is not None:
        ventana_unidad = ventana_unidad or "min"
        if ventana_unidad not in VENTANA:
            raise CriterioInvalido(f"la unidad de la ventana «{ventana_unidad}» no es s, min ni h")

    # El alcance: las transacciones que nombró el analista, o lo que dijo.
    nombres = list(entrada.get("transacciones") or [])
    if entrada.get("transaccion"):
        nombres.insert(0, entrada["transaccion"])
    txs = list(dict.fromkeys(_resolver(n, labels) for n in nombres if str(n).strip()))
    if entrada.get("toda_la_prueba"):
        alcance = "global"
        txs = []
    elif txs:
        alcance = "suma" if entrada.get("suma") and len(txs) > 1 else "transacciones"
    elif entrada.get("cada_transaccion") or tipo in POR_DEFECTO_CADA:
        alcance = "cada_transaccion"
    else:
        alcance = "transacciones"   # sin servicios: se evalúa como «falta a cuál»
    if alcance == "cada_transaccion" and tipo not in ("tiempo_respuesta", "disponibilidad_o_error", "caudal",
                                                       "volumen", "concurrencia"):
        raise CriterioInvalido("«cada transacción» no vale para un criterio de proceso")
    return {
        "id": cid,
        "texto": texto,
        "tipo": tipo,
        "metrica": metrica,
        "metrica_supuesta": supuesta,
        "operador": operador,
        "valor": float(valor) if valor is not None else None,
        "unidad": unidad,
        "cantidad": float(cantidad) if cantidad is not None else None,
        "ventana": ({"valor": float(ventana_valor), "unidad": ventana_unidad}
                    if ventana_valor is not None else None),
        "alcance": {"tipo": alcance, "transacciones": txs, "transaccion": txs[0] if txs else None},
        "origen": origen,
        "confirmacion": None,
        "en_motor": False,
        "resultado": None,
    }


def transacciones_de(c: Dict[str, Any], todas: List[str]) -> List[str]:
    """Las transacciones a las que afecta un criterio (para agrupar y para el veredicto)."""
    a = c.get("alcance") or {}
    if a.get("tipo") == "cada_transaccion":
        return list(todas)
    txs = a.get("transacciones")
    if txs is None:   # criterios guardados antes del 150
        txs = [a["transaccion"]] if a.get("transaccion") else []
    return list(txs)


def alcance_txt(c: Dict[str, Any]) -> str:
    a = c.get("alcance") or {}
    txs = a.get("transacciones") or ([a["transaccion"]] if a.get("transaccion") else [])
    if a.get("tipo") == "global":
        return "toda la prueba"
    if a.get("tipo") == "cada_transaccion":
        return "cada transacción"
    if a.get("tipo") == "suma":
        return "la suma de " + " + ".join(f"«{t}»" for t in txs)
    if not txs:
        return "sin servicio"
    return ", ".join(f"«{t}»" for t in txs) + (" (cada una)" if len(txs) > 1 else "")


def describir(c: Dict[str, Any]) -> str:
    """Qué, cuánto y sobre qué medida: «tiempo máximo ≤ 5,0 s»."""
    tipo, op, v, u = c["tipo"], c.get("operador"), c.get("valor"), c.get("unidad")
    o = _OP_TXT.get(op or "", "?")
    if v is None and tipo not in ("otro", "proceso"):
        return f"{tipo.replace('_', ' ')} (falta el valor)"
    if tipo == "tiempo_respuesta":
        sup = " (medida supuesta: no se indicó)" if c.get("metrica_supuesta") else ""
        return f"tiempo {NOMBRE_METRICA.get(c.get('metrica'), '?')} {o} {_fmt(tipo, v, u)}{sup}"
    if tipo == "disponibilidad_o_error":
        que = {"disponibilidad": "disponibilidad", "tasa_error": "tasa de error", "errores": "errores"}.get(
            c.get("metrica"), "errores")
        return f"{que} {o} {_fmt(tipo, v, u)}"
    if tipo == "concurrencia":
        return f"concurrencia {o} {num(v)} usuarios"
    if tipo == "caudal":
        return f"caudal {o} {_fmt(tipo, v, u)}"
    if tipo == "volumen":
        que = "peticiones correctas" if c.get("metrica") != "peticiones" else "peticiones"
        w = c.get("ventana")
        en = f" en {num(w['valor'], 1 if w['valor'] % 1 else 0)} {w['unidad']}" if w else " en la prueba"
        return f"volumen {o} {num(v)} {que}{en}"
    if tipo == "proceso":
        partes = []
        if c.get("cantidad"):
            partes.append(f"{num(c['cantidad'])} registros")
        if v is not None:
            partes.append(f"en {o} {_fmt('proceso', v, u)}")
        return "proceso: " + " ".join(partes)
    return c.get("texto") or "otro"


# ------------------------------------------------------------------ evaluación

class Datos:
    """Lo que hace falta para medir: las cifras de la ficha y, solo cuando hace
    falta (proceso, ventanas, sesiones viejas), el DataFrame, que se carga una vez."""

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

    def correctas(self, label: str, ventana_s: Optional[float] = None, todas: bool = False) -> Optional[int]:
        t = self.tx.get(label) or {}
        if ventana_s is None:
            if todas:
                return int(t.get("muestras", 0))
            if "correctas" in t:
                return int(t["correctas"])
            return int(t.get("muestras", 0)) - int(t.get("errores", 0))
        df = self.df()
        if df is None or not len(df):
            return None
        from app.services.ai.resumen_serie import _ok
        t0 = df["timestamp"].min()
        sub = df[(df["label"] == label) & ((df["timestamp"] - t0).dt.total_seconds() <= ventana_s)]
        return int(len(sub)) if todas else int(_ok(sub).sum())

    def usuarios(self, label: str) -> Optional[int]:
        t = self.tx.get(label) or {}
        if t.get("usuarios_grupo") is not None:
            return int(t["usuarios_grupo"])
        df = self.df()
        if df is None or "grpThreads" not in df.columns:
            return None
        import pandas as pd
        v = pd.to_numeric(df[df["label"] == label]["grpThreads"], errors="coerce").max()
        return None if pd.isna(v) else int(v)


def _res(estado, medido=None, unidad=None, texto="", motivo=None, nota=None, por_tx=None, fallan=None):
    return {"estado": estado, "medido": medido, "unidad": unidad, "texto": texto,
            "motivo": motivo, "nota": nota, "por_transaccion": por_tx or [], "fallan": fallan or []}


def _fmt(tipo: str, valor: float, unidad: Optional[str]) -> str:
    if tipo == "tiempo_respuesta":
        return {"ms": ms(valor), "s": f"{num(valor, 1)} s", "min": f"{num(valor, 1)} min"}.get(unidad, ms(valor))
    if unidad == "%":
        return pct(valor, 2)
    if unidad == "errores":
        return f"{num(valor)} errores"
    if unidad == "usuarios":
        return f"{num(valor)} usuarios"
    if unidad == "peticiones":
        return f"{num(valor)} peticiones"
    if tipo == "caudal":
        return {"por_segundo": f"{num(valor, 2)} por segundo", "por_minuto": f"{num(valor, 1)} por minuto",
                "por_hora": f"{num(valor)} por hora"}.get(unidad, num(valor, 2))
    if unidad in ("s", "min", "h"):
        return f"{num(valor, 1)} {unidad}"
    return num(valor, 2)


def _medida(c: Dict[str, Any], d: Datos, label: Optional[str]) -> Tuple[Optional[float], str]:
    """Lo que se mide de UNA transacción (o de toda la prueba si label es None)."""
    tipo, metrica = c["tipo"], c.get("metrica")
    t = d.tx.get(label) if label else None
    if tipo == "tiempo_respuesta":
        v = t.get(metrica) if t else d.cifras.get(_CLAVE_GLOBAL[metrica])
        return (None if v is None else float(v)), "ms"
    if tipo == "disponibilidad_o_error":
        tasa = float(t["tasa_error"]) if t else float(d.cifras.get("tasa_error", 0))
        if metrica == "disponibilidad":
            return 100.0 - tasa, "%"
        if metrica == "tasa_error":
            return tasa, "%"
        return (float(t["errores"]) if t else float(d.cifras.get("errores", 0))), "errores"
    if tipo == "caudal":
        return (float(t["tps"]) if t else float(d.cifras.get("caudal", 0))), "por_segundo"
    if tipo == "concurrencia":
        if label is None:
            v = (d.fases or {}).get("max_usuarios")
        else:
            v = d.usuarios(label)
        return (None if v is None else float(v)), "usuarios"
    if tipo == "volumen":
        w = c.get("ventana")
        ventana_s = w["valor"] * VENTANA[w["unidad"]] if w else None
        todas = c.get("metrica") == "peticiones"
        if label is None:
            if ventana_s is None:
                return float(d.cifras.get("peticiones", 0) - (0 if todas else d.cifras.get("errores", 0))), "peticiones"
            vals = [d.correctas(l, ventana_s, todas) for l in d.tx]
            return (None if any(v is None for v in vals) else float(sum(vals))), "peticiones"
        v = d.correctas(label, ventana_s, todas)
        return (None if v is None else float(v)), "peticiones"
    return None, ""


def _valor_txt(tipo: str, v: float, u: str) -> str:
    return {"ms": ms(v), "%": pct(v, 2), "errores": f"{num(v)} errores", "usuarios": f"{num(v)} usuarios",
            "por_segundo": f"{num(v, 2)} por segundo", "peticiones": f"{num(v)}"}.get(u, num(v, 2))


def evaluar(c: Dict[str, Any], d: Datos) -> Dict[str, Any]:
    """El resultado de UN criterio, calculado con el JTL."""
    tipo, op, valor = c["tipo"], c.get("operador"), c.get("valor")
    if tipo == "otro":
        return _res("lo_confirma_el_analista",
                    motivo="Kinetix no puede medirlo con el JTL: lo confirma el analista.")
    alc = (c.get("alcance") or {}).get("tipo")
    txs = transacciones_de(c, list(d.tx))
    faltan = [t for t in txs if t not in d.tx]
    if faltan:
        return _res("no_evaluado", motivo=f"la transacción «{faltan[0]}» no está en el JTL")
    if alc in ("transacciones", "suma") and not txs:
        return _res("no_evaluado", motivo="falta saber a qué servicio se refiere (o si es de toda la prueba)")
    if tipo == "proceso":
        return _evaluar_proceso(c, d, txs, alc)
    if c.get("metrica") is None:
        return _res("no_evaluado", motivo="falta saber qué se mide (la métrica)")
    if valor is None:
        return _res("no_evaluado", motivo="falta el valor del criterio")
    if op is None:
        return _res("no_evaluado", motivo="falta saber si es un máximo o un mínimo")
    limite = valor * UNIDADES[tipo].get(c.get("unidad"), 1.0)
    frente = f"{_OP_TXT[op]} {_fmt(tipo, valor, c.get('unidad'))}"
    que = describir(c).split(" ≤")[0].split(" ≥")[0].split(" <")[0].split(" >")[0].split(" =")[0]

    if alc == "global":
        v, u = _medida(c, d, None)
        if v is None:
            return _res("no_evaluado", motivo="el JTL no permite calcular esa medida")
        okk = _cmp(v, op, limite)
        return _res("cumple" if okk else "no_cumple", round(v, 4), u,
                    f"{que} de toda la prueba: {_valor_txt(tipo, v, u)} frente a {frente}")

    if alc == "suma":
        partes, total = [], 0.0
        for t in txs:
            v, u = _medida(c, d, t)
            if v is None:
                return _res("no_evaluado", motivo=f"el JTL no permite calcularlo para «{t}»")
            partes.append({"transaccion": t, "medido": round(v, 4), "unidad": u, "cumple": None})
            total += v
        if tipo not in ("volumen", "disponibilidad_o_error", "caudal") or (
                tipo == "disponibilidad_o_error" and c.get("metrica") != "errores"):
            return _res("no_evaluado", motivo="una suma solo tiene sentido para volúmenes, errores o caudal")
        okk = _cmp(total, op, limite)
        detalle = " + ".join(f"«{p['transaccion']}» {_valor_txt(tipo, p['medido'], p['unidad'])}" for p in partes)
        return _res("cumple" if okk else "no_cumple", round(total, 4), partes[0]["unidad"],
                    f"{que}, sumando {detalle} = {_valor_txt(tipo, total, partes[0]['unidad'])} frente a {frente}",
                    por_tx=partes, fallan=[] if okk else list(txs))

    # cada transacción por separado (las nombradas, o todas)
    partes = []
    for t in txs:
        v, u = _medida(c, d, t)
        if v is None:
            return _res("no_evaluado", motivo=f"el JTL no permite calcularlo para «{t}»"
                        + (" (no trae el número de usuarios del grupo)" if tipo == "concurrencia" else ""))
        partes.append({"transaccion": t, "medido": round(v, 4), "unidad": u, "cumple": _cmp(v, op, limite)})
    fallan = [p["transaccion"] for p in partes if not p["cumple"]]
    detalle = ", ".join(f"«{p['transaccion']}» {_valor_txt(tipo, p['medido'], p['unidad'])}"
                        + ("" if p["cumple"] else " (no cumple)") for p in partes)
    texto = f"{que} por transacción frente a {frente}: {detalle}"
    if fallan:
        texto += f". No cumple{'n' if len(fallan) > 1 else ''}: " + ", ".join(f"«{f}»" for f in fallan)
    peor = (max if op in ("<", "<=") else min)(partes, key=lambda p: p["medido"])
    return _res("no_cumple" if fallan else "cumple", peor["medido"], peor["unidad"], texto,
                por_tx=partes, fallan=fallan)


SUPUESTO = "se cuenta cada petición correcta como un registro"


def _evaluar_proceso(c, d: Datos, txs: List[str], alc: str) -> Dict[str, Any]:
    """«procesar 20.000 registros en menos de 30 minutos», con el JTL: cada
    petición correcta es un registro. Si no llegan, NO cumple (150): es un
    conteo que el JTL sí puede medir."""
    metrica, op, valor, cantidad = c.get("metrica"), c.get("operador") or "<=", c.get("valor"), c.get("cantidad")
    if metrica is None:
        metrica = "registros_en_tiempo" if (cantidad and valor is not None) else \
            ("registros" if cantidad else ("duracion" if valor is not None else None))
    if metrica is None:
        return _res("lo_confirma_el_analista",
                    motivo="no se pudo leer ni una cantidad ni un tiempo: lo confirma el analista")
    df = d.df()
    if df is None or len(df) == 0:
        return _res("no_evaluado", motivo="no se pudo leer el JTL para medirlo")
    from app.services.ai.resumen_serie import _ok
    t0 = df["timestamp"].min()
    sub = df[df["label"].isin(txs)] if alc != "global" else df
    okdf = sub[_ok(sub)]
    fin = ((okdf["timestamp"] - t0).dt.total_seconds() + okdf["elapsed"].astype(float) / 1000.0).sort_values().to_numpy()
    n_ok = len(fin)
    donde = "" if alc == "global" else " de " + " + ".join(f"«{t}»" for t in txs)
    unidad = c.get("unidad") or "min"
    factor = UNIDADES["proceso"].get(unidad, 60.0)
    fallan = [] if alc == "global" else list(txs)

    if metrica in ("registros_en_tiempo", "registros"):
        if not cantidad:
            return _res("no_evaluado", motivo="falta la cantidad de registros")
        n = int(math.ceil(cantidad))
        if n_ok < n:
            dur = (fin[-1] / factor) if n_ok else 0
            return _res("no_cumple", float(n_ok), "registros",
                        f"el JTL registra {num(n_ok)} peticiones correctas{donde} en "
                        f"{_fmt('proceso', dur, unidad)}, menos que los {num(n)} registros", nota=SUPUESTO,
                        fallan=fallan)
        if metrica == "registros" or valor is None:
            return _res("cumple", float(n_ok), "registros",
                        f"{num(n_ok)} peticiones correctas{donde} frente a {num(n)} registros", nota=SUPUESTO)
        t = fin[n - 1] / factor
        cumple = _cmp(t, op, valor)
        return _res("cumple" if cumple else "no_cumple", round(t, 2), unidad,
                    f"las {num(n)} primeras peticiones correctas{donde} terminaron en "
                    f"{_fmt('proceso', t, unidad)} desde el inicio, frente a {_OP_TXT[op]} "
                    f"{_fmt('proceso', valor, unidad)}", nota=SUPUESTO, fallan=[] if cumple else fallan)

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
                f"{_OP_TXT[op]} {_fmt('proceso', valor, unidad)}", fallan=[] if cumple else fallan)


# ------------------------------------------------------------------ el veredicto

def veredicto(lista: List[Dict[str, Any]], todas: List[str]) -> Optional[Dict[str, Any]]:
    """El veredicto de la ejecución SALIDO DE LOS CRITERIOS DECLARADOS (150):
    NO APTO si alguno no se cumple (también los que el analista confirmó como
    no cumplidos); APTO CON RESERVAS si quedan sin poder comprobarse; APTO si
    todos se cumplen. Y el de cada transacción, por los criterios que la tocan.
    None si no hay ninguno."""
    if not lista:
        return None
    estados = []
    por_tx: Dict[str, str] = {}
    for c in lista:
        r = c.get("resultado") or {}
        e = r.get("estado")
        if e == "lo_confirma_el_analista" and c.get("confirmacion"):
            e = c["confirmacion"]
        estados.append(e)
        afectadas = transacciones_de(c, todas) if (c.get("alcance") or {}).get("tipo") != "global" else []
        for t in afectadas:
            if e == "no_cumple" and (t in (r.get("fallan") or []) or not r.get("por_transaccion")):
                por_tx[t] = "NO APTO"
            elif e in ("no_evaluado", "lo_confirma_el_analista"):
                por_tx.setdefault(t, "APTO CON RESERVAS")
            else:
                por_tx.setdefault(t, "APTO")
    if "no_cumple" in estados:
        global_ = "NO APTO"
    elif any(e in ("no_evaluado", "lo_confirma_el_analista") for e in estados):
        global_ = "APTO CON RESERVAS"
    else:
        global_ = "APTO"
    return {"verdict": global_, "verdicts_per_transaction": por_tx}


# ------------------------------------------------------------------ el motor

def a_motor(lista: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """Las claves de siempre (`response_time`, `availability`, `concurrency`,
    `per_transaction`) a partir de los criterios que encajan, y sus ids.

    Encajan: tiempo medido por el P90 como máximo (es lo que compara el motor),
    disponibilidad mínima o tasa de error máxima (de cada transacción, o de las
    nombradas una a una) y concurrencia de toda la prueba. Gana el más exigente.
    Las sumas no encajan: el motor no sabe sumar transacciones."""
    motor: Dict[str, Any] = {}
    por_tx: Dict[str, Dict[str, float]] = {}
    ids: List[str] = []
    for c in lista:
        r = c.get("resultado") or {}
        if r.get("estado") == "no_evaluado" or c.get("valor") is None:
            continue
        tipo, metrica, op = c["tipo"], c.get("metrica"), c.get("operador")
        a = c.get("alcance") or {}
        if a.get("tipo") == "suma":
            continue
        txs = a.get("transacciones") or ([a["transaccion"]] if a.get("transaccion") else [])
        factor = UNIDADES[tipo].get(c.get("unidad"), 1.0)
        v = c["valor"] * factor
        if tipo == "tiempo_respuesta" and metrica == "p90" and op in ("<", "<="):
            clave, val, mejor = "response_time", v, min
        elif tipo == "disponibilidad_o_error" and metrica == "disponibilidad" and op in (">", ">="):
            clave, val, mejor = "availability", v, max
        elif tipo == "disponibilidad_o_error" and metrica == "tasa_error" and op in ("<", "<="):
            clave, val, mejor = "availability", 100.0 - v, max
        elif tipo == "concurrencia" and a.get("tipo") == "global" and op in (">=", ">", "="):
            motor["concurrency"] = int(v)
            ids.append(c["id"])
            continue
        else:
            continue
        # el destino se crea SOLO si el criterio encaja (antes quedaba un {} suelto)
        destinos = [por_tx.setdefault(t, {}) for t in txs] if a.get("tipo") == "transacciones" and txs else [motor]
        for dst in destinos:
            dst[clave] = mejor(val, dst.get(clave, val))
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


def agrupar(lista: List[Dict[str, Any]], todas: List[str]) -> List[Dict[str, Any]]:
    """Los criterios agrupados por transacción, para la ficha y para «Así los
    entendí»: [{"grupo": label | "Toda la prueba" | "A + B (suma)", "criterios": [...]}]."""
    grupos: Dict[str, List[Dict[str, Any]]] = {}
    orden: List[str] = []

    def poner(g, item):
        if g not in grupos:
            grupos[g] = []
            orden.append(g)
        grupos[g].append(item)

    for c in lista:
        r = c.get("resultado") or {}
        a = c.get("alcance") or {}
        if a.get("tipo") == "global":
            poner("Toda la prueba", {"id": c["id"], "describe": describir(c), "estado": r.get("estado"),
                                     "medido": r.get("medido"), "unidad": r.get("unidad")})
        elif a.get("tipo") == "suma":
            g = " + ".join(transacciones_de(c, todas)) + " (en suma)"
            poner(g, {"id": c["id"], "describe": describir(c), "estado": r.get("estado"),
                      "medido": r.get("medido"), "unidad": r.get("unidad")})
        else:
            detalle = {p["transaccion"]: p for p in r.get("por_transaccion") or []}
            txs = transacciones_de(c, todas) or ["Sin servicio"]
            for t in txs:
                p = detalle.get(t)
                estado = r.get("estado") if p is None else ("cumple" if p["cumple"] else "no_cumple")
                poner(t, {"id": c["id"], "describe": describir(c), "estado": estado,
                          "medido": p["medido"] if p else r.get("medido"),
                          "unidad": p["unidad"] if p else r.get("unidad")})
    return [{"grupo": g, "criterios": grupos[g]} for g in orden]


_ESTADO_TXT = {"cumple": "cumple", "no_cumple": "no cumple", "no_evaluado": "sin evaluar",
               "lo_confirma_el_analista": "lo confirmas tú", None: "sin evaluar"}


def asi_los_entendi(lista: List[Dict[str, Any]], todas: List[str]) -> str:
    """El mensaje «Así los entendí» del chat: por servicio, qué, cuánto y sobre
    qué medida, con el resultado. Lo arma el servidor, no la IA: es la lista real."""
    lineas = ["Así los entendí:"]
    for g in agrupar(lista, todas):
        partes = []
        for it in g["criterios"]:
            med = ""
            if it.get("medido") is not None and it.get("unidad"):
                med = f": {_valor_txt('', float(it['medido']), it['unidad'])}"
            partes.append(f"{it['describe']} ({_ESTADO_TXT.get(it['estado'], 'sin evaluar')}{med})")
        lineas.append(f"• {g['grupo']}: " + "; ".join(partes))
    return "\n".join(lineas)
