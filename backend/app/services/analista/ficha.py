"""La FICHA DEL INFORME del «Analista IA» — BLOQUE 5, parte A.

La ficha es lo que se ve a la derecha del chat y lo que viaja al generar. Tiene
dos mitades que no se mezclan:

- **lo que sale del JTL** (cifras, fases, hechos, fallos, transacciones con sus
  métricas, y el resultado de cada criterio): lo calcula el servidor y no se
  cambia por PATCH ni desde el chat;
- **lo que aporta el analista** (criterios, relato, ambiente y versión, qué
  transacciones llevan informe propio, pendientes descartados): se toca a mano
  por PATCH o lo propone la IA desde el chat, y el servidor lo valida.

`recalcular` deja la ficha coherente después de cualquier cambio: resultados de
los criterios, marca crítica, transacciones con informe, pendientes y contador.
Nada de aquí toca la base ni llama a la IA.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.services.ai import fases as F
from app.services.ai import resumen_serie
from app.services.ai.panel_transacciones import filas_del_panel
from app.services.ai.transaction_analysis import MAX_TRANSACTIONS
from app.services.analista import criterios_libres as CL

VERSION = 1
MAX_RELATO = 30
MAX_LINEA = 500
MAX_CONTEXTO = 200

# Los pendientes posibles: (id, obligatorio, pregunta). Solo se ponen los que
# tienen sentido para ESTA prueba (los de fallos, si hay fallos; etc.).
P_CRITERIOS = "criterios"
P_AMBIENTE = "ambiente"
P_VERSION = "version"
P_ERRORES = "detalle_errores"
P_FIN = "fin_de_la_prueba"
P_CONCENTRACION = "concentracion_fallos"


def hora_informe(dt) -> Optional[str]:
    """Las horas que salen por la API, en hora de informe (146), sin zona."""
    from app.services.zona_informe import a_informe
    return a_informe(dt).isoformat(timespec="seconds") if dt is not None else None


def _fmt_hora(t) -> Optional[str]:
    return t.strftime("%d/%m/%Y %H:%M:%S") if t is not None else None


def construir(parser, metrics: Dict[str, Any], *, cliente: Optional[str], cliente_id: Optional[str],
              proyecto: str, tipo: str, unidad: str, jtl: List[str]) -> Dict[str, Any]:
    """La ficha inicial, con lo que el motor ya sabe calcular. Sin criterios."""
    df_main = parser.df_main if getattr(parser, "df_main", None) is not None and len(parser.df_main) else parser.df
    intervalo = parser._calculate_adaptive_interval() if hasattr(parser, "_calculate_adaptive_interval") else 1
    fases = F.calcular(df_main)
    hechos = resumen_serie.hechos_de_la_prueba(df_main, intervalo, fases)
    summary = parser.get_summary_table_data()

    ok = resumen_serie._ok(df_main)
    total_err = int((~ok).sum())
    por_tx = []
    if total_err:
        g = (~ok).groupby(df_main["label"]).agg(["sum", "count"])
        g = g[g["sum"] > 0].sort_values("sum", ascending=False)
        por_tx = [{"label": str(l), "fallos": int(f["sum"]), "peticiones": int(f["count"]),
                   "pct_propio": round(100 * f["sum"] / f["count"], 4),
                   "pct_del_total": round(100 * f["sum"] / total_err, 4)} for l, f in g.iterrows()]
    concentracion = F.concentracion(df_main[~ok]["timestamp"], fases, "fallos") if total_err else ""

    extra = {str(r["label"]): r for _, r in summary.iterrows()}
    # 150: los usuarios del grupo de hilos de cada transacción (grpThreads): la
    # concurrencia «de un servicio» se mide con su grupo, no con la prueba entera.
    grupo = {}
    if "grpThreads" in df_main.columns:
        import pandas as pd
        grupo = pd.to_numeric(df_main["grpThreads"], errors="coerce").groupby(df_main["label"]).max().to_dict()
    transacciones = []
    for t in filas_del_panel(summary, None):
        r = extra[t["label"]]
        # Sin criterios, la marca crítica es solo la del pico (señales b y c):
        # se guarda aparte para volver a ella si se quitan los criterios.
        t["pico"], t["motivo_pico"] = t.pop("is_critical_suggested"), t["motivo"]
        g = grupo.get(t["label"])
        t.update(mediana=round(float(r["mediana"]), 2), p99=round(float(r["p99"]), 2),
                 min=round(float(r["min"]), 2), critica=t["pico"],
                 correctas=int(t["muestras"]) - int(t["errores"]),
                 usuarios_grupo=None if g is None or g != g else int(g),
                 informe=t["errores"] > 0, informe_origen="auto")
        transacciones.append(t)

    ficha = {
        "version": VERSION,
        "prueba": {"cliente": cliente, "cliente_id": cliente_id, "proyecto": proyecto, "tipo": tipo,
                   "unidad": unidad, "jtl": jtl},
        "cifras": {
            "peticiones": int(metrics.get("total_requests", 0)),
            "errores": int(metrics.get("total_errors", 0)),
            "tasa_error": round(float(metrics.get("error_rate", 0)), 4),
            "promedio_ms": round(float(metrics.get("avg_response_time", 0)), 2),
            "mediana_ms": round(float(metrics.get("median_response_time", 0)), 2),
            "p90_ms": round(float(metrics.get("p90_response_time", 0)), 2),
            "p95_ms": round(float(metrics.get("p95_response_time", 0)), 2),
            "p99_ms": round(float(metrics.get("p99_response_time", 0)), 2),
            "max_ms": round(float(metrics.get("max_response_time", 0)), 2),
            "caudal": round(float(metrics.get("throughput", 0)), 4),
            "duracion_s": round(float(metrics.get("duration_seconds", 0)), 2),
            "inicio": _fmt_hora(metrics.get("start_time")),
            "fin": _fmt_hora(metrics.get("end_time")),
            "redirecciones": int(metrics.get("total_redirects", 0) or 0),
        },
        "fases": {
            "disponible": fases.disponible,
            "max_usuarios": fases.max_hilos,
            "subida_hasta_s": fases.subida_hasta_s,
            "bajada_desde_s": fases.bajada_desde_s,
            "duracion_s": round(fases.duracion_s, 2),
            "sin_subida": bool(fases.disponible and fases.sin_subida),
            "sin_bajada": bool(fases.disponible and fases.sin_bajada),
            "motivo": fases.motivo or None,
            "texto": fases.linea().split("\n")[0],
        },
        "hechos": hechos,
        "serie": serie_compacta(df_main, ok),
        "fallos": {"total": total_err, "por_transaccion": por_tx, "concentracion": concentracion or None,
                   "concentrados": concentracion.find("concentrados en") >= 0},
        "transacciones": transacciones,
        "transacciones_tope": MAX_TRANSACTIONS,
        "criterios": {"estado": "sin_declarar", "lista": [], "ninguno_acordado": False},
        "relato": [],
        "contexto": {"ambiente": None, "version": None},
        "errores_detalle": {"adjuntos": []},
        "pendientes": _pendientes_iniciales(fases, total_err, concentracion),
        "listo": {},
    }
    return ficha


PUNTOS_SERIE = 120


def serie_compacta(df, ok) -> Dict[str, Any]:
    """Bloque 5 (pantalla): el mini gráfico de la tarjeta «La prueba». Como mucho
    120 puntos: por tramo, el máximo de usuarios activos y los fallos. Segundos
    desde el inicio, igual que las fases, para poder sombrearlas encima."""
    import math
    if df is None or len(df) == 0:
        return {"paso_s": 1, "puntos": []}
    seg = (df["timestamp"] - df["timestamp"].min()).dt.total_seconds()
    paso = max(1, math.ceil((float(seg.max()) + 1) / PUNTOS_SERIE))
    tramo = (seg // paso).astype(int)
    col = next((c for c in ("allThreads", "grpThreads") if c in df.columns), None)
    import pandas as pd
    hilos = pd.to_numeric(df[col], errors="coerce").groupby(tramo).max() if col else None
    fallos = (~ok).groupby(tramo).sum()
    puntos = []
    for i in range(int(tramo.max()) + 1):
        u = None if hilos is None or i not in hilos.index or pd.isna(hilos[i]) else int(hilos[i])
        puntos.append([i * paso, u, int(fallos.get(i, 0))])
    return {"paso_s": paso, "puntos": puntos}


def _pendientes_iniciales(fases: F.Fases, total_err: int, concentracion: str) -> List[Dict[str, Any]]:
    p = [
        (P_CRITERIOS, True, "¿Qué criterios de aceptación se acordaron? Si no se acordó ninguno, también vale."),
        (P_AMBIENTE, False, "¿En qué ambiente se corrió la prueba (producción, QA, preproducción)?"),
        (P_VERSION, False, "¿Qué versión de la aplicación estaba desplegada?"),
    ]
    if total_err:
        p.append((P_ERRORES, False, "¿Tienes el archivo de JMeter con el detalle de los errores (CSV o XML)?"))
    if fases.disponible and fases.sin_bajada:
        p.append((P_FIN, False, "La prueba termina a plena carga, sin bajada: ¿se cortó o era lo previsto?"))
    if total_err and "concentrados en" in (concentracion or ""):
        p.append((P_CONCENTRACION, False,
                  "Los fallos se concentran en un momento de la carga sostenida: ¿pasó algo en el ambiente "
                  "entonces (despliegue, otra carga, reinicio)?"))
    return [{"id": i, "obligatorio": o, "pregunta": q, "estado": "pendiente", "respuesta": None} for i, o, q in p]


# ------------------------------------------------------------------ recalcular

def motor(ficha: Dict[str, Any]) -> Dict[str, Any]:
    """Las claves de criterios del motor, con la marca del analista: es lo que
    reciben la marca crítica, el veredicto y `acceptance_criteria_json`."""
    m, _ = CL.a_motor(ficha["criterios"]["lista"])
    m["analista"] = {"estado_criterios": ficha["criterios"]["estado"]}
    return m


def recalcular(ficha: Dict[str, Any], cargar_df: Optional[Callable[[], Any]] = None,
               solo: Optional[set] = None) -> Dict[str, Any]:
    crit = ficha["criterios"]
    CL.recalcular(crit["lista"], CL.Datos(ficha, cargar_df), solo)
    crit["estado"] = CL.estado_de_lista(crit["lista"], crit.get("ninguno_acordado", False))

    # La marca crítica y las transacciones con informe propio (A.2): sin criterios,
    # las que tienen errores; con criterios, las críticas. Las que el analista
    # tocó a mano se quedan como él las dejó.
    con_criterios = crit["estado"] == "declarados"
    todas = [t["label"] for t in ficha["transacciones"]]
    # 150: el veredicto y la marca crítica salen de los criterios declarados, no
    # de los tres fijos del motor: una transacción es crítica si algún criterio
    # que la toca no se cumple (o si tiene un pico, como siempre).
    ver = CL.veredicto(crit["lista"], todas) if con_criterios else None
    crit["veredicto"] = ver
    crit["grupos"] = CL.agrupar(crit["lista"], todas) if con_criterios else []
    for t in ficha["transacciones"]:
        if con_criterios:
            fallos = [CL.describir(c) for c in crit["lista"]
                      if t["label"] in ((c.get("resultado") or {}).get("fallan") or [])]
            vt = (ver or {}).get("verdicts_per_transaction", {}).get(t["label"])
            t["critica"] = bool(fallos) or bool(t.get("pico"))
            t["motivo"] = " · ".join((["no cumple: " + "; ".join(fallos)] if fallos else [])
                                     + ([t.get("motivo_pico")] if t.get("pico") and t.get("motivo_pico") else []))
            t["verdict"] = vt
        else:
            t["critica"], t["motivo"], t["verdict"] = bool(t.get("pico")), t.get("motivo_pico", ""), None
        if t.get("informe_origen") != "analista":
            t["informe"] = t["critica"] if con_criterios else t["errores"] > 0

    # Pendientes que se resuelven solos.
    for p in ficha["pendientes"]:
        if p["id"] == P_CRITERIOS:
            p["estado"] = "pendiente" if crit["estado"] == "sin_declarar" else "resuelto"
        elif p["id"] in (P_AMBIENTE, P_VERSION) and ficha["contexto"].get(p["id"]):
            p["estado"], p["respuesta"] = "resuelto", ficha["contexto"][p["id"]]
        elif p["id"] == P_ERRORES and ficha["errores_detalle"]["adjuntos"]:
            p["estado"] = "resuelto"

    obl = [p for p in ficha["pendientes"] if p["obligatorio"]]
    opc = [p for p in ficha["pendientes"] if not p["obligatorio"]]
    hecho = lambda ps: sum(1 for p in ps if p["estado"] != "pendiente")
    ficha["listo"] = {
        "n": hecho(obl) + hecho(opc), "m": len(obl) + len(opc),
        "obligatorios": {"listos": hecho(obl), "total": len(obl)},
        "opcionales": {"listos": hecho(opc), "total": len(opc)},
        "puede_generar": hecho(obl) == len(obl),
        "faltan": [p["id"] for p in obl if p["estado"] == "pendiente"],
    }
    return ficha


# ------------------------------------------------------------------ cambios

class CambioInvalido(ValueError):
    """Un PATCH (o una propuesta de la IA) que no se puede aplicar. Mensaje legible."""


def _nuevo_id(prefijo: str, existentes: List[Dict[str, Any]]) -> str:
    usados = {e["id"] for e in existentes}
    n = len(existentes) + 1
    while f"{prefijo}{n}" in usados:
        n += 1
    return f"{prefijo}{n}"


def _texto(t: Any, tope: int, que: str) -> str:
    t = str(t or "").strip()
    if not t:
        raise CambioInvalido(f"{que}: el texto está vacío")
    if len(t) > tope:
        raise CambioInvalido(f"{que}: pasa de {tope} caracteres")
    return t


def agregar_relato(ficha, textos: List[str], origen: str) -> None:
    for t in textos:
        if len(ficha["relato"]) >= MAX_RELATO:
            raise CambioInvalido(f"«Lo que contaste» admite como máximo {MAX_RELATO} líneas")
        ficha["relato"].append({"id": _nuevo_id("r", ficha["relato"]), "texto": _texto(t, MAX_LINEA, "relato"),
                                "origen": origen, "creado": hora_informe(datetime.utcnow())})


def agregar_criterios(ficha, entradas: List[Dict[str, Any]], origen: str) -> set:
    """Añade (o, si ya hay uno del mismo tipo, métrica y alcance, sustituye) y
    devuelve los ids que hay que evaluar."""
    lista = ficha["criterios"]["lista"]
    labels = [t["label"] for t in ficha["transacciones"]]
    tocados = set()
    for e in entradas:
        if len(lista) >= CL.MAX_CRITERIOS:
            raise CambioInvalido(f"como máximo {CL.MAX_CRITERIOS} criterios")
        try:
            c = CL.normalizar(e, labels, _nuevo_id("c", lista), origen)
        except CL.CriterioInvalido as err:
            raise CambioInvalido(str(err))
        # Solo se reemplazan criterios de ANTES: una misma tanda no se corrige a sí misma.
        sustituye = [x for x in lista if x["id"] not in tocados and cubre(c, x, labels)]
        if sustituye:
            c["id"] = sustituye[0]["id"]
            lista[lista.index(sustituye[0])] = c
            for x in sustituye[1:]:
                lista.remove(x)
        else:
            lista.append(c)
        tocados.add(c["id"])
    if lista:
        ficha["criterios"]["ninguno_acordado"] = False
    return tocados


def cubre(nuevo: Dict[str, Any], viejo: Dict[str, Any], labels: List[str]) -> bool:
    """¿El criterio nuevo REEMPLAZA al viejo? (150: una corrección no añade
    duplicados.) Mismo tipo —y misma medida si es de tiempo o de errores—, y o
    bien el MISMO alcance, o bien el viejo era una suma que toca las mismas
    transacciones («es por servicio, no el total»). Un criterio más general no
    se traga a uno más concreto: para eso la IA manda `reemplaza`."""
    if nuevo["tipo"] == "otro" or viejo["tipo"] != nuevo["tipo"]:
        return False
    if nuevo["tipo"] in ("tiempo_respuesta", "disponibilidad_o_error") and viejo.get("metrica") != nuevo.get("metrica"):
        return False
    a_n, a_v = nuevo.get("alcance") or {}, viejo.get("alcance") or {}
    if a_n.get("tipo") == "global" or a_v.get("tipo") == "global":
        return a_n.get("tipo") == a_v.get("tipo")
    tn, tv = set(CL.transacciones_de(nuevo, labels)), set(CL.transacciones_de(viejo, labels))
    if not tn and not tv:
        return True
    if not tn or not tv or not (tn & tv):
        return False
    if a_v.get("tipo") == "suma":
        return True
    return tv == tn and (a_v.get("tipo") == "cada_transaccion") == (a_n.get("tipo") == "cada_transaccion")


def reemplazar(ficha, ids: List[str]) -> None:
    """Quita los criterios que la IA dice que reemplaza (los que no existen se ignoran)."""
    lista = ficha["criterios"]["lista"]
    for x in [x for x in lista if x["id"] in set(ids or [])]:
        lista.remove(x)


def _buscar(lista, cid, que):
    x = next((e for e in lista if e["id"] == cid), None)
    if x is None:
        raise CambioInvalido(f"{que} «{cid}» no existe")
    return x


CAMPOS_CRITERIO = ("texto", "tipo", "metrica", "operador", "valor", "unidad", "cantidad", "transaccion",
                   "transacciones", "suma", "cada_transaccion", "toda_la_prueba", "metrica_supuesta",
                   "ventana_valor", "ventana_unidad")
_ALCANCE = ("transaccion", "transacciones", "suma", "cada_transaccion", "toda_la_prueba")


def aplicar_patch(ficha: Dict[str, Any], cambios: Dict[str, Any]) -> set:
    """Lo que el analista toca a mano. `cambios` ya viene validado en su forma
    (esquema Pydantic con `extra=forbid`); aquí se valida el contenido.
    Devuelve los ids de criterio que hay que volver a evaluar."""
    tocados: set = set()
    labels = {t["label"] for t in ficha["transacciones"]}
    for label, valor in (cambios.get("transacciones") or {}).items():
        if label not in labels:
            raise CambioInvalido(f"la transacción «{label}» no está en el JTL")
        t = next(t for t in ficha["transacciones"] if t["label"] == label)
        t["informe"], t["informe_origen"] = bool(valor), "analista"

    rel = cambios.get("relato") or {}
    for cid in rel.get("quitar") or []:
        ficha["relato"].remove(_buscar(ficha["relato"], cid, "la línea"))
    for e in rel.get("editar") or []:
        _buscar(ficha["relato"], e["id"], "la línea")["texto"] = _texto(e["texto"], MAX_LINEA, "relato")
    if rel.get("agregar"):
        agregar_relato(ficha, rel["agregar"], "manual")

    cri = cambios.get("criterios") or {}
    lista = ficha["criterios"]["lista"]
    for cid in cri.get("quitar") or []:
        lista.remove(_buscar(lista, cid, "el criterio"))
    for e in cri.get("editar") or []:
        viejo = _buscar(lista, e["id"], "el criterio")
        if "confirmacion" in e:
            if (viejo.get("resultado") or {}).get("estado") != "lo_confirma_el_analista" and e["confirmacion"]:
                raise CambioInvalido("solo se confirma a mano un criterio que Kinetix no puede medir")
            viejo["confirmacion"] = e["confirmacion"]
        a = viejo.get("alcance") or {}
        base = {k: viejo.get(k) for k in CAMPOS_CRITERIO if k not in _ALCANCE and k not in ("ventana_valor",
                                                                                          "ventana_unidad")}
        base.update(transacciones=CL.transacciones_de(viejo, sorted(labels)) if a.get("tipo") != "cada_transaccion"
                    else [], suma=a.get("tipo") == "suma", cada_transaccion=a.get("tipo") == "cada_transaccion",
                    toda_la_prueba=a.get("tipo") == "global")
        if viejo.get("ventana"):
            base.update(ventana_valor=viejo["ventana"]["valor"], ventana_unidad=viejo["ventana"]["unidad"])
        campos = {k: v for k, v in e.items() if k in CAMPOS_CRITERIO}
        if any(k in campos for k in _ALCANCE):   # un alcance nuevo sustituye entero al viejo
            for k in _ALCANCE:
                base.pop(k, None)
        if not campos:
            continue
        base.update(campos)
        try:
            nuevo = CL.normalizar(base, sorted(labels), viejo["id"], "manual")
        except CL.CriterioInvalido as err:
            raise CambioInvalido(str(err))
        nuevo["confirmacion"] = None
        lista[lista.index(viejo)] = nuevo
        tocados.add(nuevo["id"])
    if cri.get("agregar"):
        tocados |= agregar_criterios(ficha, cri["agregar"], "manual")
    if "ninguno_acordado" in cri and cri["ninguno_acordado"] is not None:
        if cri["ninguno_acordado"] and lista:
            raise CambioInvalido("hay criterios en la lista: quítalos antes de decir que no se acordó ninguno")
        ficha["criterios"]["ninguno_acordado"] = bool(cri["ninguno_acordado"])

    ctx = cambios.get("contexto") or {}
    for k in ("ambiente", "version"):
        if k in ctx:
            v = ctx[k]
            ficha["contexto"][k] = _texto(v, MAX_CONTEXTO, k) if v not in (None, "") else None
            if not ficha["contexto"][k]:
                p = next((p for p in ficha["pendientes"] if p["id"] == k), None)
                if p and p["estado"] == "resuelto":
                    p["estado"], p["respuesta"] = "pendiente", None

    pen = cambios.get("pendientes") or {}
    for pid in pen.get("descartar") or []:
        p = _buscar(ficha["pendientes"], pid, "el pendiente")
        if p["obligatorio"]:
            raise CambioInvalido("los criterios no se pueden descartar: o se dicen, o se dice que no se acordó ninguno")
        p["estado"] = "descartado"
    for pid in pen.get("reabrir") or []:
        p = _buscar(ficha["pendientes"], pid, "el pendiente")
        if not p["obligatorio"]:
            p["estado"], p["respuesta"] = "pendiente", None
    return tocados


def criticas_para_generar(ficha: Dict[str, Any]) -> List[str]:
    """Las transacciones con informe propio, en el orden de la ficha (primero las
    críticas) y con el tope de siempre."""
    return [t["label"] for t in ficha["transacciones"] if t.get("informe")][:MAX_TRANSACTIONS]


def nuevo_id() -> str:
    return uuid.uuid4().hex[:12]
