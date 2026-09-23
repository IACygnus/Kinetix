#!/usr/bin/env python3
"""ETAPA D1 — el diseño del informe de horas. 0 llamadas a la IA.

Comprueba lo que se puede comprobar leyendo: las fuentes viajan DENTRO del
documento, no queda ni una llamada a la red, la paleta vieja no sobrevive en
ningún rincón, y las reglas del PDF siguen en pie (reglas 11 y 17).

Lo que NO comprueba es si se ve bien: eso se mira (D-D10), con
`rasterizar.py` y `pdf_a_png.py`.

    docker exec jmeter_backend python /app/pruebas_e2e/diseno/d1_diseno.py
"""
import re
import sys
from datetime import date, datetime
from decimal import Decimal as D
from uuid import uuid4

sys.path.insert(0, "/app")

fallos = []


def ok(c, t):
    print(f"{'PASA ' if c else 'FALLA'} | {t}")
    if not c:
        fallos.append(t)
    return c


from app.schemas.time_tracking import InformeDatos          # noqa: E402
from app.services.horas import fuentes                      # noqa: E402
from app.services.horas import graficas                     # noqa: E402
from app.services.horas import informe as gen               # noqa: E402


def datos_de_prueba() -> InformeDatos:
    """Un informe fabricado aquí mismo, **sin tocar la base ni la sesión**.

    Esta suite comprueba el DOCUMENTO, no el cálculo: de eso se encargan
    `h52_informe.py` y `h53_h54_documento.py`. Pidiéndole los datos a la API se
    quedaba a merced de lo que hubiera en la base de pruebas —que el día del
    cierre estaba vacía, y entonces no había gráficas que mirar y tres
    comprobaciones pasaban sin comprobar nada—. Fabricándolos, la suite mide
    siempre lo mismo y no depende de nadie.

    Las cifras son inventadas y **no tocan ningún dato real** (reglas 28 a 33):
    no se escribe nada, solo se arma un objeto en memoria.
    """
    dias = [date(2026, 9, d) for d in range(1, 31)]
    uid1, uid2 = uuid4(), uuid4()
    pid, aid, cid = uuid4(), uuid4(), uuid4()
    return InformeDatos(
        filtros={"desde": dias[0], "hasta": dias[-1], "periodo": "septiembre de 2026",
                 "personas": ["Ana Ruiz", "Luis Márquez de la Peña"],
                 "alcance": "Equipo", "dirigido_a": "Quien corresponda · Delivery"},
        dias=dias,
        capacidad={"working_days": 22, "hours_per_analyst": D("185"),
                   "people_count": 2, "total_hours": D("370")},
        resumen={"total_hours": D("312.5"), "ordinary_hours": D("300"),
                 "overtime_hours": D("12.5"), "billable_hours": D("210"),
                 "billable_pct": D("67.2"), "pending_days": 3,
                 "expected_hours": D("330"), "people_count": 2,
                 "projects_count": 2, "entries_count": 48},
        personas=[
            {"user_id": uid1, "user_name": "Ana Ruiz", "expected_hours": D("165"),
             "total_hours": D("170"), "ordinary_hours": D("160"),
             "overtime_hours": D("10"), "billable_hours": D("130"),
             "occupancy_pct": D("103"), "pending_days": 1},
            {"user_id": uid2, "user_name": "Luis Márquez de la Peña",
             "expected_hours": D("165"), "total_hours": D("142.5"),
             "ordinary_hours": D("140"), "overtime_hours": D("2.5"),
             "billable_hours": D("80"), "occupancy_pct": D("86.4"),
             "pending_days": 2},
        ],
        facturacion=[{"client_name": "Cliente A", "billable_hours": D("210"),
                      "non_billable_hours": D("102.5"), "total_hours": D("312.5"),
                      "billable_pct": D("67.2")}],
        por_cliente=[{"name": "Cliente A", "hours": D("312.5"), "pct": D("100")}],
        por_actividad=[
            {"name": "Diseño y generación de script", "hours": D("200"), "pct": D("64")},
            {"name": "Ejecución", "hours": D("62.5"), "pct": D("20")},
            {"name": "Gestión de proyectos", "hours": D("50"), "pct": D("16")},
        ],
        proyectos=[{"project_id": pid, "project_name": "Proyecto de prueba",
                    "client_id": cid, "client_name": "Cliente A",
                    "estimated_hours": D("400"), "consumed_hours": D("312.5"),
                    "remaining_hours": D("87.5"), "consumed_pct": D("78.1"),
                    "overrun_status": "por_agotarse", "overrun_label": "Por agotarse",
                    "hours_in_range": D("312.5")}],
        mapa=[{"user_id": uid1, "user_name": "Ana Ruiz",
               "por_dia": [D("8.5")] * 30, "total_hours": D("170"),
               "estados": (["trabajado"] * 10 + ["incompleto"] * 5 + ["festivo"]
                           + ["ausencia"] + ["finde"] * 6 + ["vacio"] * 7)}],
        detalle=[{"id": uuid4(), "user_id": uid1, "user_name": "Ana Ruiz",
                  "date": dias[0], "project_id": pid, "project_name": "Proyecto de prueba",
                  "client_name": "Cliente A", "activity_id": aid,
                  "activity_name": "Ejecución", "hours": D("8.5"),
                  "billable": True, "overtime": False,
                  "notes": "una observación cualquiera"}],
        detalle_total=48,
        generado=datetime(2026, 9, 23, 10, 0, 0),
    )


datos = datos_de_prueba()
html = gen.documento_html(datos)
himp = gen.documento_pdf_html(datos, [c for c in gen.CLAVES if c != "detalle"])

print("=== 1. Las letras viajan dentro (decisión A) ===")
ok(fuentes.caras_disponibles() == 6,
   f"las seis caras están en assets/fuentes ({fuentes.caras_disponibles()})")
for familia, peso, _ in fuentes.CARAS:
    marca = f"font-family:'{familia}';font-style:normal;font-weight:{peso}"
    ok(marca in html and marca in himp, f"{familia} {peso}, en las DOS ramas")
ok(html.count("data:font/woff2;base64,") == 6,
   f"seis fuentes incrustadas en base64 ({html.count('data:font/woff2;base64,')})")

print("\n--- ni una llamada a la red (H-D54) ---")
for doc, comolla in ((html, "el HTML"), (himp, "el HTML de impresión")):
    sin_datos = re.sub(r"data:[a-z/+-]+;base64,[A-Za-z0-9+/=]+", "", doc)
    urls = re.findall(r"https?://[^\s\"'<>)]+", sin_datos)
    ok(not urls, f"{comolla} no pide nada a la red ({urls[:2] if urls else 'ninguna URL'})")
    ok("fonts.googleapis" not in doc and "@import" not in doc,
       f"{comolla} no enlaza Google Fonts ni importa nada")

print("\n=== 2. Una sola paleta (decisión B) ===")
css = gen._BASE_CSS + gen._PDF_CSS + gen._WEB_CSS
for viejo, donde in (("#0a1628", "el navy provisional de H-D73"),
                     ("#f5a623", "el naranja provisional de H-D73"),
                     ("#4f46e5", "el indigo de la barra"),
                     ("Segoe UI',system-ui,-apple-system,sans-serif;color:#1f2937",
                      "la tipografía de antes")):
    ok(viejo not in css, f"no queda {donde}")
for var in ("--dark:#060B29", "--navy:#03287D", "--azul:#0032A7",
            "--naranja:#FCA311", "--amarillo:#FFC440"):
    ok(var in css, f"la paleta de la referencia declara {var}")

print("\n=== 3. Las reglas del PDF, intactas (reglas 11 y 17) ===")
ok("display:flex" not in gen._PDF_CSS and "display:grid" not in gen._PDF_CSS,
   "la rama de impresión sigue sin flex ni grid")
ok("rem" not in gen._PDF_CSS, "ni rem en la rama de impresión")
ok("display:flex" not in gen._BASE_CSS and "display:grid" not in gen._BASE_CSS,
   "ni en la base, que comparten las dos ramas")
tam = [float(x) for x in re.findall(r"font-size:([\d.]+)pt", gen._BASE_CSS + gen._PDF_CSS)]
ok(min(tam) >= 8.0, f"ningún texto por debajo de 8 pt (el menor: {min(tam)})")

print("\n=== 4. El resumen, como manda D-D3 ===")
ok(html.count('class="ind-num"') == 6, "las seis cifras van en su propio elemento")
ok(html.count('class="ind-pie"') == 6, "y las seis llevan su línea de desglose")
ok('class="ind factura"' in html and 'class="ind pendiente"' in html,
   "los indicadores llevan su color")
ok("<small class=\"ind-uni\">h</small>" in html, "la unidad va aparte de la cifra")
# Los datos de prueba traen una ocupación del 103 %: la barra tiene que avisar.
ok('class="barra pasada"' in html,
   "la ocupación pasada del 100 % pinta su barra en naranja")
ok(html.count('class="barra"') + html.count('class="barra pasada"')
   >= len(datos.personas) + len(datos.por_cliente) + len(datos.por_actividad),
   "hay una barra por cada porcentaje: ocupación, clientes y actividades")

print("\n=== 5. Los párrafos de sección (D-D4) y los títulos (D-D5) ===")
n_intros = html.count('class="sec-intro"')
ok(n_intros == len(gen.CLAVES), f"las ocho secciones llevan su párrafo ({n_intros})")
ok('class="numsec"' not in html and 'class="numsec"' not in himp,
   "fuera el cuadro numerado del título")
ok("numsec" not in gen._BASE_CSS + gen._WEB_CSS, "y su estilo tampoco se quedó")
prohibidas = ("veredicto", "hallazgo", "se evidencia", "se observa que",
              "cabe destacar", "es importante mencionar", "en conclusion")
textos = " ".join(f(datos).lower() for f in gen._INTROS.values())
for p in prohibidas:
    ok(p not in textos, f"ningún párrafo dice «{p}» (regla 15)")
ok("**" not in textos and "##" not in textos, "y ninguno lleva markdown")
largos = {k: len(f(datos)) for k, f in gen._INTROS.items()}
ok(max(largos.values()) <= 420,
   f"ninguno pasa de tres líneas (el mayor: {max(largos.values())} letras)")

print("\n=== 6. Las gráficas (D-D6, decisión C) ===")
ok(html.count('class="svg-barras"') == 2 and himp.count('class="svg-barras"') == 2,
   "las dos gráficas están en las DOS ramas")
ok("<script" not in himp, "la rama de impresión no lleva ni una línea de JavaScript")
ok('class="leyenda-grafica"' in html, "cada gráfica lleva su leyenda")
ok(himp.count("<table") > himp.count('class="svg-barras"'),
   "las tablas siguen ahí: la gráfica va encima, no en su lugar")
# WeasyPrint recorta los descendentes de un <text> anclado a `end`. Que no se
# cuele ninguno, en ninguna rama.
ok("text-anchor" not in html and "text-anchor" not in himp,
   "ningún texto del SVG usa text-anchor (recorta descendentes en WeasyPrint)")
# El SVG se estira al ancho del texto de la página: 186 mm de A4 menos márgenes,
# repartidos en las 1000 unidades del viewBox.
MM_POR_UNIDAD = 186 / graficas.ANCHO
tam_svg = [float(x) for x in re.findall(r'font-size="([\d.]+)"', himp)]
en_pt = [t * MM_POR_UNIDAD / 0.3528 for t in tam_svg]
ok(tam_svg and min(en_pt) >= 8.0,
   f"ningún texto de las gráficas baja de 8 pt en el PDF (el menor: {min(en_pt):.1f} pt)")

print("\n=== 7. El mapa nombra todos sus colores ===")
estados = ("trabajado", "incompleto", "festivo", "ausencia", "finde", "vacio")
for e in estados:
    ok(f'class="mini {e}"' in html, f"la leyenda del mapa nombra «{e}»")

print("\n=== 8. El PDF se imprime de verdad ===")
from weasyprint import HTML as WeasyHTML                    # noqa: E402
doc = WeasyHTML(string=himp).render()
ok(all(p.width < p.height for p in doc.pages),
   f"todas las hojas en vertical ({len(doc.pages)} páginas)")

print("\n" + "=" * 70)
if fallos:
    print(f"{len(fallos)} FALLO(S):")
    for f in fallos:
        print("  -", f)
else:
    print("D1 — EL DISEÑO: TODO PASA")
print("=" * 70)
sys.exit(1 if fallos else 0)
