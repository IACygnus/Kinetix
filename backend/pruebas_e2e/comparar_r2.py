"""ETAPA R2 — compara las corridas «antes» y «despues» de `corrida_r2.py`.

    docker exec -w /app jmeter_backend python3 /app/pruebas_e2e/comparar_r2.py <id8> [<id8> ...]

Lee /tmp/r2/corrida_antes_<id8>.json y corrida_despues_<id8>.json y escribe:
  - /tmp/r2/comparacion.html  el texto de antes y el de despues, uno al lado del
    otro, por ejecucion y por seccion. LLEVA DATOS DE CLIENTES: se copia fuera
    del repositorio (C:\\proyectos\\Kinetix_pruebas\\r2\\), nunca a docs/.
  - /tmp/r2/resumen.json      las cifras, sin textos: tokens, tiempo, llamadas,
    disculpas (R-D14) y lo que citan las conclusiones.

Una seccion que salio del RESPALDO en cualquiera de las dos versiones se marca en
rojo y NO entra en las cifras de texto (decision de Fredy, R2): esa comparacion
no vale. Los tokens y el tiempo si se cuentan: se gastaron igual.

Mide con el detector ACTUAL (`estilo.detectar_estilo`) las dos versiones: la
misma vara para las dos. No llama a la IA ni abre la base.
"""
import html
import json
import re
import sys
import unicodedata

sys.path.insert(0, "/app")   # el detector ACTUAL, se lance desde donde se lance

from app.services.ai.estilo import detectar_estilo
from app.services.ai.origen import PLANTILLAS, SECCIONES_TRANSACCION

DIR = "/tmp/r2"

GENERAL = {
    "ai_analysis_summary": ("Resumen", "summary_table"),
    "ai_analysis_errors": ("Errores", "errors"),
    "ai_analysis_response_times": ("Tiempos de respuesta", "chart_response_times"),
    "ai_analysis_latency": ("Latencia", "chart_latency"),
    "ai_analysis_error_rate": ("Tasa de error", "chart_error_rate"),
    "ai_analysis_codes_per_second": ("Códigos de respuesta", "chart_codes_per_second"),
    "ai_analysis_transactions_per_second": ("Transacciones por segundo", "chart_transactions_per_second"),
    "ai_analysis_active_threads": ("Hilos activos", "chart_active_threads"),
    "ai_analysis_redirects": ("Redirecciones", "redirects"),
    "ai_conclusions": ("Conclusiones", "conclusions"),
    "ai_recommendations": ("Recomendaciones", "recommendations"),
}

# Lo que se busca en las conclusiones (lo que faltaba en el diagnostico 120).
CUANDO = re.compile(r"\bmin(?:uto)?s?\.?\s*\d{1,3}(?::\d{2})?\b|\b\d{1,2}:\d{2}(?::\d{2})?\b", re.I)
CUANTO = re.compile(r"\d[\d.,]*\s*(?:ms\b|s\b|seg|segundos?\b|%|peticiones|respuestas|muestras|usuarios|hilos|errores|fallos|por\s+segundo)", re.I)


def plano(t):
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def frases(t):
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", t or "") if f.strip()]


def es_plantilla(col, texto):
    frs = PLANTILLAS.get(col)
    if not frs or not texto:
        return False
    t = texto.lstrip()
    if col == "ai_analysis_errors":
        return t.startswith("Se detectaron ") and " errores (" in t[:80]
    return any(t.startswith(f) or f in t[:200] for f in frs)


def cargar(v, id8):
    return json.load(open(f"{DIR}/corrida_{v}_{id8}.json", encoding="utf-8"))


def respaldo_de(corrida):
    """{(transaccion|None, seccion_interna)} de las llamadas que devolvieron None."""
    return {(r.get("transaccion"), r["seccion"]) for r in corrida.get("respaldo") or []}


def tokens(corrida):
    s = {"prompt": 0, "cached": 0, "completion": 0, "reasoning": 0, "intentos": 0, "sin_usage": 0}
    for t in corrida.get("tokens") or []:
        s["intentos"] += 1
        if t.get("prompt_tokens") is None:
            s["sin_usage"] += 1
            continue
        s["prompt"] += t["prompt_tokens"] or 0
        s["cached"] += t.get("cached_tokens") or 0
        s["completion"] += t["completion_tokens"] or 0
        s["reasoning"] += t.get("reasoning_tokens") or 0
    return s


def etiquetas_cortas(labels):
    out = {}
    for l in labels:
        corto = re.sub(r"^\s*\d+\.\s*", "", l)
        out[l] = [plano(l), plano(corto)]
    return out


def citas(texto, labels):
    fr = frases(texto)
    cortas = etiquetas_cortas(labels)
    completas = 0
    detalle = {"frases": len(fr), "con_cuando": 0, "con_cuanto": 0, "con_transaccion": 0, "las_tres": 0}
    for f in fr:
        p = plano(f)
        a = bool(CUANDO.search(f))
        b = bool(CUANTO.search(f))
        c = any(any(x and x in p for x in v) for v in cortas.values())
        detalle["con_cuando"] += a
        detalle["con_cuanto"] += b
        detalle["con_transaccion"] += c
        completas += a and b and c
    detalle["las_tres"] = completas
    detalle["transacciones_citadas"] = sorted(l for l, v in cortas.items() if any(x and x in plano(texto) for x in v))
    return detalle


def frases_cuando(texto):
    """Las frases que dicen CUANDO, con el momento resaltado. HTML ya escapado."""
    out = []
    for f in frases(texto):
        if CUANDO.search(f):
            out.append(CUANDO.sub(lambda m: f"<mark class='cuando'>{m.group(0)}</mark>", html.escape(f)))
    return out


def disculpas(texto, seccion):
    return [a for a in detectar_estilo(texto or "", seccion) if a["tipo"] == "disculpa"]


def pares(antes, despues):
    """[(transaccion|None, clave, nombre, seccion_interna, texto_antes, texto_despues)]"""
    out = []
    for col, (nombre, interna) in GENERAL.items():
        a, d = (antes.get("general") or {}).get(col), (despues.get("general") or {}).get(col)
        if a is None and d is None:
            continue
        out.append((None, col, nombre, interna, a, d))
    labels = sorted(set(antes.get("transacciones") or {}) | set(despues.get("transacciones") or {}))
    for l in labels:
        for sec, nombre in SECCIONES_TRANSACCION.items():
            a = (antes.get("transacciones") or {}).get(l, {}).get(sec)
            d = (despues.get("transacciones") or {}).get(l, {}).get(sec)
            if a is None and d is None:
                continue
            out.append((l, sec, nombre, f"txreport_{sec}", a, d))
    return out


def resaltar(texto, avisos):
    t = html.escape(texto or "")
    for a in avisos:
        frag = html.escape(a["contexto"][:60])
        if frag and frag in t:
            t = t.replace(frag, f'<mark>{frag}</mark>', 1)
    return t.replace("\n", "<br>")


CSS = """
:root{--fondo:#f6f7fb;--papel:#fff;--tinta:#1d2433;--suave:#5b6477;--borde:#dfe3ec;--acento:#4f46e5;
--rojo:#b42318;--rojo-f:#fdecea;--ambar:#fff4d6;--verde:#0f7b4f}
@media (prefers-color-scheme:dark){:root{--fondo:#12151c;--papel:#1b2029;--tinta:#e6e9f0;--suave:#9aa3b5;
--borde:#2c3340;--acento:#8b85ff;--rojo:#ff8a80;--rojo-f:#3a1d1b;--ambar:#3a3218;--verde:#5fd49c}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1400px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:21px;margin:40px 0 8px;padding-top:12px;border-top:3px solid var(--acento)}
h3{font-size:16px;margin:24px 0 8px;color:var(--acento)}
.nota{color:var(--suave);margin:0 0 16px}
table.cifras{border-collapse:collapse;width:100%;background:var(--papel);margin:8px 0 16px;font-variant-numeric:tabular-nums}
table.cifras th,table.cifras td{border:1px solid var(--borde);padding:6px 10px;text-align:right}
table.cifras th:first-child,table.cifras td:first-child{text-align:left}
.par{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 14px}
.col{background:var(--papel);border:1px solid var(--borde);border-radius:10px;padding:12px 14px;min-width:0;overflow-wrap:anywhere}
.col h4{margin:0 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.respaldo{background:var(--rojo-f);border-color:var(--rojo)}
.marca{display:inline-block;background:var(--rojo);color:#fff;border-radius:6px;padding:1px 8px;font-size:12px;font-weight:600;margin-left:8px}
mark{background:var(--ambar);color:inherit;border-bottom:2px solid #d99a00}
mark.cuando{background:#dcfce7;border-bottom-color:var(--verde)}
@media (prefers-color-scheme:dark){mark.cuando{background:#123c29}}
.vacio{color:var(--suave);font-style:italic}
nav a{color:var(--acento);margin-right:14px}
@media (max-width:760px){.par{grid-template-columns:1fr}}
"""


def main(ids):
    resumen = {"ejecuciones": []}
    cuerpo = []
    indice = []
    for id8 in ids:
        antes, despues = cargar("antes", id8), cargar("despues", id8)
        nombre = despues.get("ejecucion_nombre") or antes.get("ejecucion_nombre") or id8
        r_a, r_d = respaldo_de(antes), respaldo_de(despues)
        labels = sorted(set(despues.get("transacciones") or {}) | set(antes.get("transacciones") or {}))
        fila = {"id": id8, "nombre": nombre,
                "parcial": {"antes": antes.get("parcial"), "despues": despues.get("parcial")},
                "tokens": {"antes": tokens(antes), "despues": tokens(despues)},
                "segundos": {"antes": antes.get("segundos"), "despues": despues.get("segundos")},
                "llamadas": {"antes": antes.get("llamadas"), "despues": despues.get("llamadas")},
                "respaldo": {"antes": antes.get("respaldo") or [], "despues": despues.get("respaldo") or []},
                "secciones": 0, "excluidas": [], "disculpas": {"antes": 0, "despues": 0},
                "caracteres": {"antes": 0, "despues": 0}}
        indice.append(f'<a href="#e{id8}">{html.escape(nombre)} ({id8})</a>')
        cuerpo.append(f'<h2 id="e{id8}">{html.escape(nombre)} <small>({id8})</small></h2>')
        actual = object()
        for tx, clave, nombre_sec, interna, a, d in pares(antes, despues):
            if tx != actual:
                actual = tx
                cuerpo.append(f"<h3>{'Informe general' if tx is None else html.escape(tx)}</h3>")
            if not a and not d and (tx, interna) not in r_a and (tx, interna) not in r_d:
                # Ninguna de las dos la genero ni la intento: no aplica (p. ej. sin
                # redirecciones). No es respaldo y no se pinta.
                fila.setdefault("no_aplica", []).append({"transaccion": tx, "seccion": clave})
                continue
            malo_a = (tx, interna) in r_a or not a or (tx is None and es_plantilla(clave, a))
            malo_d = (tx, interna) in r_d or not d or (tx is None and es_plantilla(clave, d))
            av_a, av_d = disculpas(a, clave), disculpas(d, clave)
            if malo_a or malo_d:
                fila["excluidas"].append({"transaccion": tx, "seccion": clave,
                                          "antes": malo_a, "despues": malo_d})
            else:
                fila["secciones"] += 1
                fila["disculpas"]["antes"] += len(av_a)
                fila["disculpas"]["despues"] += len(av_d)
                fila["caracteres"]["antes"] += len(a)
                fila["caracteres"]["despues"] += len(d)
            titulo = html.escape(nombre_sec) + ('<span class="marca">RESPALDO: no cuenta</span>' if (malo_a or malo_d) else "")
            cuerpo.append(f"<p><strong>{titulo}</strong></p><div class='par'>")
            for et, txt, malo, av in (("Antes (41cf237)", a, malo_a, av_a), ("Después (R2)", d, malo_d, av_d)):
                extra = f" · {len(av)} disculpa(s)" if av else ""
                contenido = resaltar(txt, av) if txt else '<span class="vacio">sin texto</span>'
                if txt and clave == "ai_conclusions":
                    contenido = CUANDO.sub(lambda m: f"<mark class='cuando'>{m.group(0)}</mark>", contenido)
                cuerpo.append(f"<div class='col{' respaldo' if malo else ''}'><h4>{et}{' · RESPALDO' if malo else ''}{extra}</h4>{contenido}</div>")
            cuerpo.append("</div>")
        conc_ok = not any(e["seccion"] == "ai_conclusions" for e in fila["excluidas"])
        # Lo que faltaba en el diagnostico 120: ¿las conclusiones dicen CUANDO?
        bloque = [f"<h3>Conclusiones: las frases que dicen cuándo{'' if conc_ok else ' <span class=marca>RESPALDO: no cuenta</span>'}</h3><div class='par'>"]
        for et, v in (("Antes (41cf237)", antes), ("Después (R2)", despues)):
            fc = frases_cuando((v.get("general") or {}).get("ai_conclusions"))
            lista = "".join(f"<li>{x}</li>" for x in fc) or "<li class='vacio'>ninguna</li>"
            bloque.append(f"<div class='col'><h4>{et} · {len(fc)} frase(s)</h4><ul>{lista}</ul></div>")
        bloque.append("</div>")
        cuerpo.insert(cuerpo.index(f'<h2 id="e{id8}">{html.escape(nombre)} <small>({id8})</small></h2>') + 1, "".join(bloque))
        fila["conclusiones"] = {
            "valida": conc_ok,
            "antes": citas((antes.get("general") or {}).get("ai_conclusions"), labels),
            "despues": citas((despues.get("general") or {}).get("ai_conclusions"), labels),
        }
        resumen["ejecuciones"].append(fila)

    def es(n):
        if n is None or n == "—":
            return "—"
        if isinstance(n, float):
            return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{n:,}".replace(",", ".")

    filas = []
    for f in resumen["ejecuciones"]:
        for v in ("antes", "despues"):
            t, s, c = f["tokens"][v], f["segundos"][v] or {}, f["conclusiones"][v]
            filas.append(
                f"<tr><td>{html.escape(f['nombre'])} · {v}</td><td>{es((f['llamadas'][v] or {}).get('total'))}</td>"
                f"<td>{es(t['prompt'])}</td><td>{es(t['cached'])}</td><td>{es(t['completion'])}</td><td>{es(t['reasoning'])}</td>"
                f"<td>{es(s.get('total'))}</td><td>{f['disculpas'][v]}</td>"
                f"<td>{c['las_tres']} de {c['frases']}</td><td>{len(f['excluidas'])}</td></tr>")
    tabla = ("<table class='cifras'><tr><th>Ejecución · versión</th><th>Llamadas</th><th>Tokens entrada</th>"
             "<th>de ellos en caché</th><th>Tokens salida</th><th>de ellos razonamiento</th><th>Segundos</th>"
             "<th>Disculpas</th><th>Frases de conclusiones con cuándo + cuánto + transacción</th>"
             "<th>Secciones excluidas (respaldo)</th></tr>" + "".join(filas) + "</table>")
    doc = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>R2 antes y después</title><style>{CSS}</style></head><body><main>"
           f"<h1>R2 — antes y después</h1><p class='nota'>Mismo modelo (gpt-5.5), mismas ejecuciones, sin escribir en la base. "
           f"Antes = copia de 41cf237; después = código con R2 (243900c). Las disculpas (R-D14) se miden con el detector actual en las dos versiones "
           f"y se resaltan en ámbar. Una sección que salió del respaldo en cualquiera de las dos se marca en rojo y no cuenta. "
           f"<strong>Lleva datos de clientes: no sale de esta carpeta.</strong></p>"
           f"<nav>{''.join(indice)}</nav>{tabla}{''.join(cuerpo)}</main></body></html>")
    open(f"{DIR}/comparacion.html", "w", encoding="utf-8").write(doc)
    json.dump(resumen, open(f"{DIR}/resumen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
