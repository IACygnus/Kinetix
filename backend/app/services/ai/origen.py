"""
F1 (aviso de respaldo) — de donde salio cada texto de un informe, y por que.

Una sola definicion para todo el producto:
  - `llamar()`            corre una llamada de IA con su buzon de fallo
                          (`gemini.BUZON_FALLO`) y devuelve (texto, fallo).
  - `registro()`          la fila de UNA seccion: ia / respaldo / sin_texto / fijo.
  - `guardar()`           la escribe en `ai_section_origins` (sin commit).
  - `resumen_de()`        lo que se ensena: cuantas, cuales y por que.
  - `detectar_por_texto`  los informes ANTERIORES al registro: el respaldo
                          escribe con plantillas fijas que la IA no produce.
  - `marca()`             la linea que viaja escondida en los exportados.

Los cuatro origenes:
  ia         lo escribio el modelo.
  respaldo   la IA fallo y el texto lo puso `FallbackAnalyzer`, con plantilla.
  sin_texto  la IA fallo y la seccion quedo vacia (informe por transaccion,
             o el pipeline entero cayo antes de empezar).
  fijo       no hacia falta IA (p. ej. «No se detectaron errores»).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select

from app.db.models.ai_origen import AISectionOrigin
from app.services.ai.gemini import BUZON_FALLO

logger = logging.getLogger(__name__)

AFECTADOS = ("respaldo", "sin_texto")   # lo que el aviso cuenta como «no lo escribio la IA»

# Motivo -> como se le dice a una persona. El literal del proveedor va aparte.
MOTIVOS: Dict[str, str] = {
    "clave": "la clave de la IA no sirve (el proveedor la rechaza)",
    "cupo": "se agotó el cupo de la cuenta del proveedor",
    "limite_proveedor": "el proveedor limitó las peticiones y no respondió tras tres intentos",
    "transitorio": "el proveedor no respondió (red, tiempo agotado o error del servidor)",
    "vacio": "el modelo devolvió una respuesta vacía",
    "modelo": "el modelo configurado no existe para esta clave",
    "circuito": "la IA ya había fallado en este informe y no se volvió a intentar",
    "limite_kinetix": "se alcanzó el límite diario o mensual de llamadas configurado en Kinetix",
    "sin_configuracion": "no hay ninguna IA configurada, o su clave no se puede leer",
    "error": "el proveedor devolvió un error",
    "anterior": "informe anterior al registro del origen: se reconoce por el texto de plantilla",
}

# Nombre de cada seccion del informe general, en el orden en que se presenta.
SECCIONES_GENERALES: Dict[str, str] = {
    "ai_analysis_summary": "Resumen",
    "ai_analysis_errors": "Errores",
    "ai_analysis_response_times": "Tiempos de respuesta",
    "ai_analysis_latency": "Latencia",
    "ai_analysis_error_rate": "Tasa de error",
    "ai_analysis_codes_per_second": "Códigos de respuesta",
    "ai_analysis_transactions_per_second": "Transacciones por segundo",
    "ai_analysis_active_threads": "Hilos activos",
    "ai_analysis_redirects": "Redirecciones",
    "ai_conclusions": "Conclusiones",
    "ai_recommendations": "Recomendaciones",
}
SECCIONES_TRANSACCION: Dict[str, str] = {
    "summary": "Resumen", "chart_response_times": "Tiempos de respuesta",
    "chart_latency": "Latencia", "chart_error_rate": "Tasa de error",
    "chart_codes": "Códigos de respuesta", "chart_tps": "Transacciones por segundo",
}

# Frases que SOLO escribe `FallbackAnalyzer` (gemini.py). Con ellas se reconocen
# los informes generados antes de que existiera este registro. Leido en la base
# de Fredy el 29/09/2026: 13 de 72 ejecuciones.
PLANTILLAS: Dict[str, Tuple[str, ...]] = {
    "ai_analysis_summary": ("La prueba proceso ",),
    "ai_analysis_errors": ("Se detectaron ",),   # + " errores (" — ver detectar_por_texto
    "ai_analysis_response_times": ("El grafico de tiempos de respuesta muestra la distribucion de latencias",),
    "ai_analysis_latency": ("La latencia promedio de red fue",),
    "ai_analysis_error_rate": ("Se debe investigar la distribucion temporal de errores",),
    "ai_analysis_codes_per_second": ("La distribucion de codigos HTTP muestra el patron",),
    "ai_analysis_transactions_per_second": ("El grafico de transacciones por segundo muestra la distribucion de carga",),
    "ai_analysis_active_threads": ("El grafico de hilos activos muestra el patron de concurrencia",),
    "ai_analysis_redirects": ("Las redirecciones agregan latencia adicional al flujo del usuario",),
    "ai_conclusions": ("1. VEREDICTO: ",),
    "ai_recommendations": ("PRIORIDAD CRITICA:",),
}


# ====================================================================
# 1. La llamada, con su buzon
# ====================================================================

async def llamar(func, *args, **kwargs) -> Tuple[Any, Dict[str, str]]:
    """`await asyncio.to_thread(func, ...)` + lo que anoto `_generate` si fallo.

    `to_thread` copia el contexto al hilo: el dict que se pone aqui es el MISMO
    objeto que ve `_generate`, sin carreras con otras generaciones en paralelo.
    """
    buzon: Dict[str, str] = {}
    token = BUZON_FALLO.set(buzon)
    try:
        resultado = await asyncio.to_thread(func, *args, **kwargs)
    finally:
        BUZON_FALLO.reset(token)
    return resultado, dict(buzon)


def fallo_global(error: str) -> Dict[str, str]:
    """El fallo de cuando el pipeline cae ANTES de llamar: sin analizador."""
    texto = error or ""
    if "limit reached" in texto:
        tipo = "limite_kinetix"
    elif "API key" in texto or "no configurada" in texto or not texto:
        tipo = "sin_configuracion"
    else:
        tipo = "error"
    return {"tipo": tipo, "detalle": texto[:400]}


def registro(origen: str, fallo: Optional[Dict[str, str]] = None,
             provider: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """La fila de una seccion, antes de saber a que ejecucion pertenece."""
    fallo = fallo or {}
    tipo = fallo.get("tipo") if origen in AFECTADOS else None
    if origen in AFECTADOS and not tipo:
        # La IA devolvio None sin pasar por `_generate` (p. ej. se rompio el
        # armado del prompt): no hay literal, pero no se puede callar.
        tipo = "error"
    return {"origen": origen, "provider": provider, "model": model,
            "motivo_tipo": tipo, "motivo": fallo.get("detalle") if origen in AFECTADOS else None,
            "generated_at": datetime.utcnow()}


# ====================================================================
# 2. La base
# ====================================================================

async def guardar(db, execution_id, label: str, section: str, reg: Dict[str, Any]) -> None:
    """Crea o actualiza la fila. SIN commit: lo hace quien llama, con lo suyo."""
    fila = (await db.execute(select(AISectionOrigin).where(
        AISectionOrigin.execution_id == execution_id,
        AISectionOrigin.label == (label or ""),
        AISectionOrigin.section == section,
    ))).scalar_one_or_none()
    if fila is None:
        fila = AISectionOrigin(execution_id=execution_id, label=label or "", section=section)
        db.add(fila)
    for k in ("origen", "provider", "model", "motivo_tipo", "motivo", "generated_at"):
        setattr(fila, k, reg.get(k))
    fila.edited_at = None   # un texto recien generado no esta editado


async def guardar_general(db, execution_id, origenes: Dict[str, Dict[str, Any]]) -> None:
    for columna, reg in (origenes or {}).items():
        await guardar(db, execution_id, "", columna, reg)


async def marcar_editado(db, execution_id, label: str, secciones: Iterable[str]) -> None:
    """Un texto corregido a mano deja de ser «de plantilla». Sin commit."""
    secciones = list(secciones)
    if not secciones:
        return
    filas = (await db.execute(select(AISectionOrigin).where(
        AISectionOrigin.execution_id == execution_id,
        AISectionOrigin.label == (label or ""),
        AISectionOrigin.section.in_(secciones),
    ))).scalars().all()
    ahora = datetime.utcnow()
    for f in filas:
        f.edited_at = ahora


async def filas_de(db, execution_ids: List[Any]) -> Dict[Any, List[AISectionOrigin]]:
    if not execution_ids:
        return {}
    filas = (await db.execute(select(AISectionOrigin).where(
        AISectionOrigin.execution_id.in_(execution_ids)))).scalars().all()
    out: Dict[Any, List[AISectionOrigin]] = {}
    for f in filas:
        out.setdefault(f.execution_id, []).append(f)
    return out


# ====================================================================
# 3. Los informes de antes del registro
# ====================================================================

def detectar_por_texto(execution) -> Dict[str, bool]:
    """columna -> True si su texto es de plantilla del respaldo."""
    out: Dict[str, bool] = {}
    for columna, frases in PLANTILLAS.items():
        texto = (getattr(execution, columna, None) or "").lstrip()
        if not texto:
            continue
        if columna == "ai_analysis_errors":
            out[columna] = texto.startswith("Se detectaron ") and " errores (" in texto[:80]
        elif columna == "ai_analysis_error_rate":
            out[columna] = frases[0] in texto
        else:
            out[columna] = any(texto.startswith(f) or f in texto[:200] for f in frases)
    return out


# ====================================================================
# 4. Lo que se ensena
# ====================================================================

def fila_a_dict(f: AISectionOrigin, nombres: Dict[str, str]) -> Dict[str, Any]:
    return {
        "section": f.section, "label": f.label or None,
        "nombre": nombres.get(f.section, f.section),
        "origen": f.origen, "provider": f.provider, "model": f.model,
        "motivo_tipo": f.motivo_tipo, "motivo_frase": MOTIVOS.get(f.motivo_tipo or "", None),
        "motivo": f.motivo,
        "generated_at": f.generated_at.isoformat() if f.generated_at else None,
        "edited_at": f.edited_at.isoformat() if f.edited_at else None,
    }


def resumen_de(execution, filas: Optional[List[AISectionOrigin]]) -> Dict[str, Any]:
    """El resumen de una ejecucion: informe general y transacciones.

    Con filas del registro, manda el registro. Sin filas, se mira el texto: si
    lleva plantilla del respaldo, se dice, marcado como `fuente='texto'`.
    """
    filas = filas or []
    if filas:
        general = [fila_a_dict(f, SECCIONES_GENERALES) for f in filas if not f.label]
        orden = list(SECCIONES_GENERALES)
        general.sort(key=lambda d: orden.index(d["section"]) if d["section"] in orden else 99)
        tx: Dict[str, List[Dict[str, Any]]] = {}
        for f in filas:
            if f.label:
                tx.setdefault(f.label, []).append(fila_a_dict(f, SECCIONES_TRANSACCION))
        todas = general + [d for lista in tx.values() for d in lista]
        fuente = "registro"
    else:
        detect = detectar_por_texto(execution)
        general = [{
            "section": col, "label": None, "nombre": SECCIONES_GENERALES.get(col, col),
            "origen": "respaldo" if es else "desconocido", "provider": None, "model": None,
            "motivo_tipo": "anterior" if es else None,
            "motivo_frase": MOTIVOS["anterior"] if es else None, "motivo": None,
            "generated_at": execution.created_at.isoformat() if getattr(execution, "created_at", None) else None,
            "edited_at": None,
        } for col, es in detect.items()]
        tx = {}
        todas = general
        fuente = "texto" if any(detect.values()) else "ninguna"

    afectadas = [d for d in todas if d["origen"] in AFECTADOS]
    sin_editar = [d for d in afectadas if not d["edited_at"]]
    # El motivo que se ensena: el primero que fallo (los demas suelen ser
    # «circuito», que es consecuencia de ese). Si todos son circuito, ese.
    principal = next((d for d in afectadas if d["motivo_tipo"] not in (None, "circuito")),
                     afectadas[0] if afectadas else None)
    fechas = [d["generated_at"] for d in todas if d["generated_at"]]
    ia = next((d for d in todas if d["provider"]), None)
    return {
        "fuente": fuente,
        "total": len([d for d in todas if d["origen"] != "desconocido"]),
        "ia": sum(1 for d in todas if d["origen"] == "ia"),
        "respaldo": sum(1 for d in todas if d["origen"] == "respaldo"),
        "sin_texto": sum(1 for d in todas if d["origen"] == "sin_texto"),
        "afectadas": len(afectadas),
        "afectadas_sin_editar": len(sin_editar),
        "general": {"total": len([d for d in general if d["origen"] != "desconocido"]),
                    "afectadas": sum(1 for d in general if d["origen"] in AFECTADOS)},
        "transacciones": {label: {"total": len(l), "afectadas": sum(1 for d in l if d["origen"] in AFECTADOS)}
                          for label, l in tx.items()},
        "motivo_tipo": principal["motivo_tipo"] if principal else None,
        "motivo_frase": principal["motivo_frase"] if principal else None,
        "motivo": principal["motivo"] if principal else None,
        "provider": ia["provider"] if ia else None,
        "model": ia["model"] if ia else None,
        "fecha": min(fechas) if fechas else None,
        "secciones": general,
        "secciones_transaccion": tx,
    }


def resumen_corto(res: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que necesita una fila del historial, sin la lista de secciones."""
    return {k: res[k] for k in ("fuente", "total", "ia", "afectadas", "afectadas_sin_editar",
                                "motivo_tipo", "motivo_frase", "fecha")}


def marca(res: Dict[str, Any]) -> str:
    """La linea invisible de los exportados (decision de Fredy, 29/09/2026):
    cuantas, cuando y POR QUE. «Este salio el 26 de septiembre con respaldo
    porque la clave estaba revocada»."""
    fecha = (res.get("fecha") or "")[:16].replace("T", " ")
    fecha = f"generado el {fecha} UTC" if fecha else "fecha de generación desconocida"
    if res.get("fuente") == "ninguna" or not res.get("total"):
        return (f"Kinetix · origen del texto: sin registro (informe anterior al 29/09/2026); "
                f"su texto no es de plantilla del respaldo · {fecha}")
    quien = " ".join(x for x in (res.get("provider"), res.get("model")) if x) or "la IA"
    if not res.get("afectadas"):
        return f"Kinetix · origen del texto: las {res['total']} secciones las escribió {quien} · {fecha}"
    partes = [f"{res['afectadas']} de {res['total']} secciones NO las escribió la IA"]
    if res.get("respaldo"):
        partes.append(f"{res['respaldo']} con texto de respaldo")
    if res.get("sin_texto"):
        partes.append(f"{res['sin_texto']} sin texto")
    if res.get("afectadas") != res.get("afectadas_sin_editar"):
        partes.append(f"{res['afectadas'] - res['afectadas_sin_editar']} corregidas a mano después")
    motivo = res.get("motivo_frase") or "motivo desconocido"
    if res.get("motivo"):
        motivo += f" ({res['motivo'][:160]})"
    return f"Kinetix · origen del texto: {', '.join(partes)} · {fecha} · motivo: {motivo}"


# ====================================================================
# 5. La marca de los exportados
# ====================================================================

async def metas_para(db, execution_ids: List[Any]) -> str:
    """Las <meta> que llevan escondida la marca de cada ejecucion.

    - `kinetix:origen`, una por ejecucion: la lee quien abra el HTML.
    - `description` y `keywords`: WeasyPrint las pasa a los metadatos del PDF
      (Asunto y Palabras clave), visibles en Propiedades del documento.
    Nada de esto se pinta en la pagina (decision de Fredy, 29/09/2026).
    """
    import html as _html
    from app.db.models.test import TestExecution

    ids = [i for i in execution_ids if i]
    if not ids:
        return ""
    ejecuciones = (await db.execute(select(TestExecution).where(TestExecution.id.in_(ids)))).scalars().all()
    filas = await filas_de(db, ids)
    lineas = []
    for e in sorted(ejecuciones, key=lambda x: ids.index(x.id)):
        lineas.append(f"{e.name}: {marca(resumen_de(e, filas.get(e.id)))}")
    if not lineas:
        return ""
    esc = lambda t: _html.escape(t, quote=True)
    metas = "".join(f'<meta name="kinetix:origen" content="{esc(l)}">\n' for l in lineas)
    todo = " | ".join(lineas)
    return metas + f'<meta name="description" content="{esc(todo)}">\n<meta name="keywords" content="{esc(todo)}">\n'
