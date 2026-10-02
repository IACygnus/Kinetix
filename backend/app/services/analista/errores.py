"""El archivo con el detalle de los errores — BLOQUE 5, parte B.

El analista adjunta lo que JMeter guarda de los fallos:
  - CSV (Simple Data Writer / «Save as CSV»): timeStamp, label, responseCode,
    responseMessage, success, failureMessage, URL…;
  - XML (View Results Tree / «Save as XML» con datos): <httpSample> con sus
    atributos (ts, lb, rc, rm, s) y sus hijos responseData, samplerData,
    assertionResult/failureMessage, java.net.URL, method, queryString.

De ahí sale un RESUMEN DETERMINISTA, sin IA: grupos por transacción + código +
mensaje normalizado, con su recuento, su porcentaje, el primer y el último
momento (en hora de informe) y uno o dos ejemplos recortados. Todo lo que se
guarda del archivo pasa antes por `enmascarar`.

El XML se lee con un lector que NO admite DOCTYPE ni entidades: JMeter no los
escribe nunca, y sin ellos no hay entidades externas ni «billion laughs».
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.ai.estilo import num, pct
from app.services.analista.enmascarar import seguro
from app.services.zona_informe import a_informe

TOPE_BYTES = 20 * 1024 * 1024
MAX_GRUPOS = 20
MAX_EJEMPLOS = 2
TOPE_EJEMPLO = 400
TOPE_MENSAJE = 240


class ArchivoInvalido(ValueError):
    pass


_FORMATO_FECHA = "%d/%m/%Y %H:%M:%S"
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
_NUM = re.compile(r"\d+")


def normalizar_mensaje(m: str) -> str:
    """La clave del grupo: sin ids, sin números y sin espacios de más."""
    t = seguro(m, 1000).lower()
    t = _UUID.sub("<id>", t)
    t = _HEX.sub("<id>", t)
    t = _NUM.sub("#", t)
    return re.sub(r"\s+", " ", t).strip()[:200] or "(sin mensaje)"


def _es_falso(v) -> bool:
    return str(v).strip().lower() in ("false", "0", "no")


def _momento(ts) -> Optional[pd.Timestamp]:
    try:
        return a_informe(pd.Timestamp(int(float(ts)), unit="ms"))
    except Exception:
        return None


# ------------------------------------------------------------------ lectores

def _filas_csv(datos: bytes, avisos: List[str]):
    texto = datos.decode("utf-8-sig", errors="replace")
    lector = csv.DictReader(io.StringIO(texto))
    campos = {c.strip() for c in (lector.fieldnames or [])}
    if "label" not in campos or not ({"responseCode", "success", "responseMessage"} & campos):
        raise ArchivoInvalido("no parece un CSV de JMeter: le faltan las columnas label y responseCode/success")
    if "success" not in campos:
        avisos.append("el CSV no trae la columna success: se cuentan todas sus filas como error")
    for f in lector:
        f = {(k or "").strip(): v for k, v in f.items()}
        yield {
            "ts": f.get("timeStamp"),
            "label": f.get("label") or "",
            "codigo": (f.get("responseCode") or "").strip(),
            "mensaje": f.get("failureMessage") or f.get("responseMessage") or "",
            "ok": None if "success" not in campos else not _es_falso(f.get("success")),
            "peticion": " ".join(x for x in (f.get("URL") or "",) if x),
            "respuesta": f.get("responseData") or "",
        }


def _rechazar_dtd(datos: bytes) -> None:
    """Recorre el PRÓLOGO entero (declaración, comentarios, instrucciones) hasta
    el primer elemento: un DOCTYPE solo puede ir ahí, y un comentario enorme
    delante no lo esconde. Dentro de los elementos, JMeter escapa el texto."""
    i, n = 0, len(datos)
    while i < n:
        j = datos.find(b"<", i)
        if j < 0:
            break
        if datos.startswith(b"<?", j):
            k = datos.find(b"?>", j)
        elif datos.startswith(b"<!--", j):
            k = datos.find(b"-->", j)
        elif datos[j + 1:j + 2] == b"!":
            raise ArchivoInvalido("el XML trae DOCTYPE o entidades, y no se admiten: "
                                  "JMeter no los escribe nunca")
        else:
            return   # primer elemento: se acabó el prólogo
        if k < 0:
            raise ArchivoInvalido("el XML no se puede leer: el prólogo no se cierra")
        i = k + 2


def _filas_xml(datos: bytes, avisos: List[str]):
    _rechazar_dtd(datos)
    pila = 0
    try:
        for ev, el in ET.iterparse(io.BytesIO(datos), events=("start", "end")):
            if ev == "start":
                pila += 1
                continue
            pila -= 1
            if pila != 1 or el.tag not in ("httpSample", "sample"):
                continue
            fallo = " · ".join(t for t in (
                (a.findtext("failureMessage") or "").strip() for a in el.findall("assertionResult")) if t)
            metodo = el.findtext("method") or ""
            url = el.findtext("java.net.URL") or ""
            peticion = el.findtext("samplerData") or " ".join(x for x in (metodo, url) if x)
            q = el.findtext("queryString") or ""
            if q and q not in peticion:
                peticion += "\n" + q
            yield {
                "ts": el.get("ts"),
                "label": el.get("lb") or "",
                "codigo": (el.get("rc") or "").strip(),
                "mensaje": fallo or el.get("rm") or "",
                "ok": None if el.get("s") is None else not _es_falso(el.get("s")),
                "peticion": peticion,
                "respuesta": el.findtext("responseData") or "",
            }
            el.clear()
    except ET.ParseError as e:
        raise ArchivoInvalido(f"el XML no se puede leer: {e}")


# ------------------------------------------------------------------ resumen

def resumir(datos: bytes, formato: str, fallos_jtl: Dict[str, int]) -> Dict[str, Any]:
    """El resumen del archivo, ya enmascarado. `fallos_jtl` = {label: fallos} del JTL."""
    if len(datos) > TOPE_BYTES:
        raise ArchivoInvalido("el archivo pasa del tope")
    avisos: List[str] = []
    filas = _filas_csv(datos, avisos) if formato == "csv" else _filas_xml(datos, avisos)
    grupos: "OrderedDict[tuple, Dict[str, Any]]" = OrderedDict()
    leidas = errores = 0
    por_label: Dict[str, int] = {}
    for f in filas:
        leidas += 1
        if f["ok"] is True:
            continue
        errores += 1
        por_label[f["label"]] = por_label.get(f["label"], 0) + 1
        clave = (f["label"], f["codigo"], normalizar_mensaje(f["mensaje"]))
        g = grupos.get(clave)
        t = _momento(f["ts"])
        if g is None:
            g = grupos[clave] = {"transaccion": f["label"], "codigo": f["codigo"] or None,
                                 "mensaje": seguro(f["mensaje"], TOPE_MENSAJE) or "(sin mensaje)",
                                 "recuento": 0, "primero": t, "ultimo": t, "ejemplos": []}
        g["recuento"] += 1
        if t is not None:
            g["primero"] = t if g["primero"] is None else min(g["primero"], t)
            g["ultimo"] = t if g["ultimo"] is None else max(g["ultimo"], t)
        if len(g["ejemplos"]) < MAX_EJEMPLOS:
            g["ejemplos"].append({
                "momento": t.strftime(_FORMATO_FECHA) if t is not None else None,
                "mensaje": seguro(f["mensaje"], TOPE_MENSAJE),
                "peticion": seguro(f["peticion"], TOPE_EJEMPLO),
                "respuesta": seguro(f["respuesta"], TOPE_EJEMPLO),
            })
    if leidas == 0:
        raise ArchivoInvalido("el archivo no trae ninguna muestra de JMeter")
    orden = sorted(grupos.values(), key=lambda g: -g["recuento"])
    salida = []
    for g in orden[:MAX_GRUPOS]:
        salida.append({**g, "porcentaje": round(100 * g["recuento"] / errores, 2) if errores else 0,
                       "primero": g["primero"].strftime(_FORMATO_FECHA) if g["primero"] is not None else None,
                       "ultimo": g["ultimo"].strftime(_FORMATO_FECHA) if g["ultimo"] is not None else None})
    resto = sum(g["recuento"] for g in orden[MAX_GRUPOS:])
    return {
        "formato": formato,
        "filas": leidas,
        "errores": errores,
        "grupos_total": len(grupos),
        "grupos": salida,
        "otros": {"grupos": max(0, len(orden) - MAX_GRUPOS), "recuento": resto} if resto else None,
        "cruce": cruzar(por_label, fallos_jtl),
        "avisos": avisos,
    }


def cruzar(archivo: Dict[str, int], jtl: Dict[str, int]) -> Dict[str, Any]:
    """¿Cuadran los recuentos del archivo con los fallos del JTL?"""
    ta, tj = sum(archivo.values()), sum(jtl.values())
    dif = [{"transaccion": l, "jtl": jtl.get(l, 0), "archivo": archivo.get(l, 0)}
           for l in sorted(set(archivo) | set(jtl)) if jtl.get(l, 0) != archivo.get(l, 0)]
    cuadra = not dif
    if cuadra:
        texto = f"Cuadra con el JTL: {num(ta)} errores en los dos."
    else:
        partes = "; ".join(f"«{d['transaccion']}»: JTL {num(d['jtl'])}, archivo {num(d['archivo'])}"
                           for d in dif[:6])
        texto = (f"No cuadra con el JTL: el archivo trae {num(ta)} errores y el JTL {num(tj)}. "
                 f"Diferencias: {partes}{'…' if len(dif) > 6 else ''}.")
    return {"cuadra": cuadra, "archivo_total": ta, "jtl_total": tj, "diferencias": dif, "texto": texto}


def resumen_corto(adjunto_id: str, nombre: str, r: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que la ficha lleva de cada adjunto: lo justo para el contador y la pantalla."""
    return {"id": adjunto_id, "nombre": nombre, "errores": r["errores"], "grupos": r["grupos_total"],
            "cuadra": r["cruce"]["cuadra"], "cruce": r["cruce"]["texto"]}


def texto_para_prompt(resumenes: List[Dict[str, Any]], tope: int) -> str:
    """«DETALLE DE LOS ERRORES»: los grupos, ya enmascarados, en texto llano."""
    lineas: List[str] = []
    for r in resumenes:
        lineas.append(f"Archivo de errores ({r['formato'].upper()}): {num(r['errores'])} errores en "
                      f"{num(r['grupos_total'])} grupos. {r['cruce']['texto']}")
        for g in r["grupos"]:
            lineas.append(f"- «{g['transaccion']}» · código {g['codigo'] or 'sin código'} · "
                          f"{num(g['recuento'])} ({pct(g['porcentaje'], 1)} de los errores del archivo) · "
                          f"de {g['primero'] or '?'} a {g['ultimo'] or '?'} · mensaje: {g['mensaje']}")
            for e in g["ejemplos"][:1]:
                if e.get("respuesta"):
                    lineas.append(f"  respuesta de ejemplo: {e['respuesta'][:200]}")
        if r.get("otros"):
            lineas.append(f"- y {num(r['otros']['grupos'])} grupos más con {num(r['otros']['recuento'])} errores")
    texto = "\n".join(lineas)
    return texto if len(texto) <= tope else texto[:tope - 1].rstrip() + "…"
