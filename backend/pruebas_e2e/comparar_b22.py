"""BLOQUE 2.4 — el «despues» del 136 contra la version nueva (2.2 + 2.3).

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/comparar_b22.py <id8> [<id8> ...]

Lee /tmp/r2/corrida_despues_<id8>.json (el 136) y /tmp/r2/corrida_b22_<id8>.json
(la de ahora) y escribe:
  - /tmp/r2/comparacion2.html  los dos textos lado a lado, por seccion. LLEVA
    DATOS DE CLIENTES: se copia a C:\\proyectos\\Kinetix_pruebas\\r2\\, nunca a docs/.
  - /tmp/r2/resumen2.json      solo cifras, sin textos.

Mide, con la misma vara para las dos versiones:
  - tokens (entrada, en cache, salida, razonamiento), llamadas y segundos;
  - palabras y parrafos por seccion (parrafo = linea no vacia);
  - cifras por parrafo (numeros, sin contar los de los nombres de transaccion);
  - vinetas de conclusiones y recomendaciones («•», «-» o «1.» al inicio de linea);
  - disculpas (el detector actual, tipo «disculpa»);
  - momentos citados («min M:SS», «M:SS» de fin de intervalo, «hh:mm:ss») y la
    fase en que caen, con las fases de `services/ai/fases.py`.
No llama a la IA. Lee el JTL con una conexion de solo lectura.
"""
import asyncio
import html
import os
import json
import re
import sys
from datetime import timedelta

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/pruebas_e2e")

from app.services.ai.estilo import detectar_estilo, _NUMERO   # noqa: E402
from app.services.ai import fases as F                        # noqa: E402
from comparar_r2 import GENERAL, CSS, pares, respaldo_de, tokens, es_plantilla   # noqa: E402
from fases_r2 import _ejecucion, MIN, RELOJ, INICIO           # noqa: E402

DIR = "/tmp/r2"
VIEJA, NUEVA = "despues", os.environ.get("KX_NUEVA", "b22")
NOMBRE = {VIEJA: "Después del 136", NUEVA: "Versión nueva (2.2 + 2.3)"}
SINTESIS = {"ai_conclusions", "ai_recommendations"}
VINETA = re.compile(r"^\s*(?:[•\-*]|\d{1,2}[.)])\s+")


def cargar(v, id8):
    return json.load(open(f"{DIR}/corrida_{v}_{id8}.json", encoding="utf-8"))


def parrafos(t):
    return [ln.strip() for ln in (t or "").splitlines() if ln.strip()]


def cifras(t, labels):
    for l in sorted(labels, key=len, reverse=True):
        t = t.replace(l, "TX")
    t = VINETA.sub("", t)
    return len(_NUMERO.findall(t))


def momentos(t, f, inicio):
    """[(citado, fase)] de un texto. Misma lectura que fases_r2.py."""
    out, usados = [], []
    for m in MIN.finditer(t or ""):
        seg = int(m[1]) * 60 + int(m[2] or 0)
        out.append((m[0], f.fase_de(seg)))
        usados.append(m.span())
    for m in RELOJ.finditer(t or ""):
        if any(a <= m.start() < b for a, b in usados):
            continue
        if m[3] is None:
            seg = int(m[1]) * 60 + int(m[2])
        elif inicio is not None:
            hora = timedelta(hours=int(m[1]), minutes=int(m[2]), seconds=int(m[3] or 0))
            seg = (hora - inicio).total_seconds() % 86400
            if seg > f.duracion_s + 1:
                continue   # no es una hora de la prueba
        else:
            continue
        out.append((m[0], f.fase_de(seg)))
    return out


def medir(corrida, f, labels):
    prompts = " ".join(c["prompt"] for c in corrida["detalle"])
    m0 = INICIO.search(prompts)
    inicio = timedelta(hours=int(m0[1]), minutes=int(m0[2]), seconds=int(m0[3])) if m0 else None
    resp = respaldo_de(corrida)
    sec = {"n": 0, "palabras": [], "parrafos": [], "un_parrafo": 0, "en_rango": 0,
           "cifras": 0, "parrafos_total": 0}
    sint = {}
    disc, citados = 0, []
    for tx, col, nombre, interna, texto, _ in pares(corrida, {}):
        if not texto or (tx, interna) in resp or (tx is None and es_plantilla(col, texto)):
            continue
        disc += sum(1 for a in detectar_estilo(texto, interna) if a["tipo"] == "disculpa")
        for c, fase in momentos(texto, f, inicio):
            citados.append({"seccion": interna, "transaccion": bool(tx), "fase": fase,
                            "conclusiones": col == "ai_conclusions"})
        ps = parrafos(texto)
        if tx is None and col in SINTESIS:
            items = [p for p in ps if VINETA.match(p)]
            sint[col] = {"lineas": len(ps), "vinetas": len(items),
                         "marca": sorted({"n." if g[0].isdigit() else g[0]
                                          for g in (VINETA.match(p).group(0).strip() for p in items)}),
                         "palabras": len(texto.split()), "cifras": cifras(texto, labels),
                         "cifras_por_vineta": round(cifras(texto, labels) / max(1, len(items) or len(ps)), 1)}
            continue
        sec["n"] += 1
        pal = len(texto.split())
        sec["palabras"].append(pal)
        sec["parrafos"].append(len(ps))
        sec["parrafos_total"] += len(ps)
        sec["un_parrafo"] += len(ps) == 1
        sec["en_rango"] += 110 <= pal <= 175
        sec["cifras"] += cifras(texto, labels)
    t = tokens(corrida)
    rampa = [c for c in citados if c["fase"] in ("subida", "bajada")]
    return {
        "llamadas": len(corrida["detalle"]), "segundos": corrida["segundos"]["total"],
        "respaldo": len(corrida.get("respaldo") or []),
        "tokens": {**t, "pct_cache": round(100 * t["cached"] / t["prompt"], 1) if t["prompt"] else 0},
        "secciones": {"n": sec["n"], "palabras_media": round(sum(sec["palabras"]) / max(1, sec["n"])),
                      "palabras_min": min(sec["palabras"] or [0]), "palabras_max": max(sec["palabras"] or [0]),
                      "parrafos_media": round(sec["parrafos_total"] / max(1, sec["n"]), 2),
                      "con_un_parrafo": sec["un_parrafo"], "en_120_160": sec["en_rango"],
                      "cifras_por_parrafo": round(sec["cifras"] / max(1, sec["parrafos_total"]), 1),
                      "cifras_por_seccion": round(sec["cifras"] / max(1, sec["n"]), 1)},
        "sintesis": sint,
        "disculpas": disc,
        "momentos": {"total": len(citados), "en_rampa": len(rampa),
                     "en_conclusiones": sum(c["conclusiones"] for c in citados),
                     "en_rampa_en_conclusiones": sum(c["conclusiones"] for c in rampa),
                     "por_fase": {k: sum(1 for c in citados if c["fase"] == k) for k in ("subida", "sostenida", "bajada")}},
    }


def main(ids):
    resumen, bloques, filas = {"ejecuciones": []}, [], []
    for id8 in ids:
        v, n = cargar(VIEJA, id8), cargar(NUEVA, id8)
        f = F.calcular(asyncio.run(_ejecucion(id8)))
        labels = sorted(set(v.get("transacciones") or {}) | set(n.get("transacciones") or {}))
        mv, mn = medir(v, f, labels), medir(n, f, labels)
        resumen["ejecuciones"].append({"id": id8, VIEJA: mv, NUEVA: mn})
        nombre = n.get("ejecucion_nombre") or id8
        filas.append((nombre, mv, mn))

        partes = [f"<h2 id='e{id8}'>{html.escape(nombre)} <small>({id8})</small></h2>",
                  f"<p class='nota'>{html.escape(f.linea().splitlines()[0])}</p>"]
        rv, rn = respaldo_de(v), respaldo_de(n)
        actual = object()
        for tx, col, titulo, interna, a, d in pares(v, n):
            if tx != actual:
                partes.append(f"<h3>{'Informe general' if tx is None else html.escape(tx)}</h3>")
                actual = tx
            cols = []
            for ver, texto, resp in ((VIEJA, a, rv), (NUEVA, d, rn)):
                cae = (tx, interna) in resp
                cuerpo = (html.escape(texto).replace("\n", "<br>") if texto
                          else "<span class='vacio'>sin texto</span>")
                marca = "<span class='marca'>RESPALDO</span>" if cae else ""
                pal = f" · {len(texto.split())} palabras" if texto else ""
                cols.append(f"<div class='col{' respaldo' if cae else ''}'><h4>{NOMBRE[ver]}{pal}{marca}</h4>{cuerpo}</div>")
            partes.append(f"<p><strong>{html.escape(titulo)}</strong></p><div class='par'>{''.join(cols)}</div>")
        bloques.append("\n".join(partes))

    def celda(a, b, dec=False):
        return f"<td>{a}</td><td>{b}</td>"

    tabla = ["<table class='cifras'><tr><th>Ejecución · medida</th><th>Después del 136</th><th>Versión nueva</th></tr>"]
    for nombre, mv, mn in filas:
        tabla.append(f"<tr><th colspan='3' style='text-align:left'>{html.escape(nombre)}</th></tr>")
        for etiqueta, g in (
                ("Llamadas · segundos", lambda m: f"{m['llamadas']} · {m['segundos']}"),
                ("Respaldo", lambda m: m["respaldo"]),
                ("Tokens de entrada", lambda m: f"{m['tokens']['prompt']:,}".replace(",", ".")),
                ("…en caché", lambda m: f"{m['tokens']['cached']:,} ({m['tokens']['pct_cache']}%)".replace(",", ".")),
                ("Tokens de salida (razonamiento)", lambda m: f"{m['tokens']['completion']:,} ({m['tokens']['reasoning']:,})".replace(",", ".")),
                ("Palabras por sección (media, mín–máx)", lambda m: f"{m['secciones']['palabras_media']} ({m['secciones']['palabras_min']}–{m['secciones']['palabras_max']})"),
                ("Párrafos por sección", lambda m: f"{m['secciones']['parrafos_media']} · {m['secciones']['con_un_parrafo']} de {m['secciones']['n']} con uno solo"),
                ("Cifras por párrafo", lambda m: m["secciones"]["cifras_por_parrafo"]),
                ("Cifras por sección", lambda m: m["secciones"]["cifras_por_seccion"]),
                ("Conclusiones: viñetas · cifras", lambda m: f"{m['sintesis'].get('ai_conclusions', {}).get('vinetas', '—')} · {m['sintesis'].get('ai_conclusions', {}).get('cifras', '—')}"),
                ("Recomendaciones: viñetas · cifras", lambda m: f"{m['sintesis'].get('ai_recommendations', {}).get('vinetas', '—')} · {m['sintesis'].get('ai_recommendations', {}).get('cifras', '—')}"),
                ("Disculpas", lambda m: m["disculpas"]),
                ("Momentos citados · en rampa", lambda m: f"{m['momentos']['total']} · {m['momentos']['en_rampa']}"),
        ):
            tabla.append(f"<tr><td>{etiqueta}</td>{celda(g(mv), g(mn))}</tr>")
    tabla.append("</table>")

    nav = " ".join(f"<a href='#e{e['id']}'>{html.escape(nm)}</a>" for e, (nm, _, _) in zip(resumen["ejecuciones"], filas))
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Comparación 2.4</title>
<style>{CSS}</style></head><body><main>
<h1>Bloque 2.4 — después del 136 frente a la versión nueva</h1>
<p class="nota">Izquierda: el «después» del reporte 136. Derecha: la estructura común (2.2) y la guía de estilo (2.3).
Mismo modelo (gpt-5.5, razonamiento medium), mismas ejecuciones, sin escribir en la base.
Una sección que cayó al respaldo sale en rojo y no entra en las cifras de texto.</p>
<nav>{nav}</nav>
<h2>Las cifras</h2>
{''.join(tabla)}
{''.join(bloques)}
</main></body></html>"""
    open(f"{DIR}/comparacion2.html", "w", encoding="utf-8").write(doc)
    json.dump(resumen, open(f"{DIR}/resumen2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
