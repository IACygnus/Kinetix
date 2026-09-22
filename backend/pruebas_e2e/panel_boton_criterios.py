"""ETAPA 5b.2 — la columna "Criterios" y su boton (D54).

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/panel_boton_criterios.py

Sobre la pantalla real de Nuevo Reporte. **NO genera ningun informe**: sube el JTL
al detector de transacciones y se queda ahi. CERO llamadas a la IA.

Comprueba:
  1. La columna "Criterios" existe y es la ultima.
  2. La flecha de la izquierda ya no existe.
  3. Todas las filas abren con el boton en "Globales" (gris).
  4. El boton despliega los criterios de SU fila, y pueden quedar varias abiertas.
  5. Editar un criterio -> ese boton pasa a "Propios" y ningun otro se mueve.
  6. "Usar globales" lo devuelve a "Globales".
  7. La criticidad se sigue recalculando al instante.
"""
import os
import sys

from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
JTL = os.environ.get(
    "KX_JTL", "/app/uploads/20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl")

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None,
                              locale="es-CO")
        page = ctx.new_page()
        page.goto(WEB, wait_until="networkidle")
        if page.locator('input[type="password"]').count():
            page.locator('input[type="text"]').first.fill(os.environ.get("KX_USER", "admin"))
            page.locator('input[type="password"]').first.fill(os.environ.get("KX_PWD", ""))
            page.locator('button[type="submit"]').first.click()
            page.wait_for_url("**/dashboard", timeout=30000)
            ctx.storage_state(path=SESION)

        page.goto(f"{WEB}/performance/new", wait_until="networkidle")
        page.set_input_files('input[type="file"]', JTL)
        page.wait_for_selector("text=Transacciones del JTL", timeout=120000)
        page.wait_for_timeout(1500)

        tabla = page.locator("table").first
        cabeceras = [h.strip().lower() for h in tabla.locator("thead th").all_inner_texts()]
        print(f"columnas: {[h for h in cabeceras if h]}")

        print("\n--- 1. La columna 'Criterios' es la ultima ---")
        ok("criterios" in cabeceras, "existe la columna 'Criterios'")
        ok(cabeceras[-1] == "criterios", f"y es la ultima ({cabeceras[-1]!r})")
        for c in ("transacción", "muestras", "promedio", "tps", "errores"):
            ok(c in cabeceras, f"sigue la columna '{c}'")

        print("\n--- 2. La flecha de la izquierda ya no existe ---")
        # Antes habia una columna vacia de ancho w-6 entre el checkbox y el nombre.
        ok(len([h for h in cabeceras if not h]) == 1,
           f"solo queda una columna sin titulo, la del checkbox ({len([h for h in cabeceras if not h])})")
        primera = tabla.locator("tbody > tr").first
        ok(primera.locator("td").nth(1).locator("span").count() >= 1,
           "el nombre de la transaccion va ya en la segunda celda")

        print("\n--- 2b. El chip 'criterios propios' ya no existe (ajuste 5b) ---")
        ok(page.get_by_text("criterios propios").count() == 0,
           "ningun chip 'criterios propios' junto al nombre")

        print("\n--- 3. Todas abren en 'Globales' ---")
        botones = page.locator("[data-testid='boton-criterios']")
        n = botones.count()
        estados = [botones.nth(i).get_attribute("data-estado") for i in range(n)]
        textos = [botones.nth(i).inner_text().strip() for i in range(n)]
        ok(n > 0, f"hay {n} botones, uno por transaccion")
        ok(all(e == "globales" for e in estados), f"todos en estado 'globales': {set(estados)}")
        ok(all(t.startswith("Globales") for t in textos), f"y todos dicen 'Globales'")
        etiquetas = [botones.nth(i).get_attribute("data-tx") for i in range(n)]
        print(f"    transacciones: {etiquetas}")

        print("\n--- 4. El boton despliega SU fila ---")
        filas = tabla.locator("tbody > tr")
        antes_filas = filas.count()
        botones.nth(0).click()
        page.wait_for_timeout(400)
        ok(filas.count() == antes_filas + 1, "se abrio una fila")
        ok(botones.nth(0).get_attribute("aria-expanded") == "true", "el boton queda marcado como abierto")
        desplegada = filas.nth(1)
        txt = desplegada.inner_text()
        for campo in ("Concurrencia esperada", "Tiempo de respuesta (ms)", "Disponibilidad (%)"):
            ok(campo in txt, f"la fila desplegada muestra '{campo}'")
        ok("Usar globales" in txt, "y trae 'Usar globales'")
        # D40: varias a la vez.
        botones.nth(2).click()
        page.wait_for_timeout(400)
        ok(filas.count() == antes_filas + 2, "una segunda fila se abre sin cerrar la primera")
        botones.nth(2).click()
        page.wait_for_timeout(300)

        print("\n--- 5. Editar un criterio -> 'Propios' ---")
        entradas = filas.nth(1).locator("input[type=number]")
        ok(entradas.count() == 3, f"tres campos editables ({entradas.count()})")
        critico_antes = tabla.locator("tbody > tr").nth(0).locator("td").nth(1).inner_text()
        entradas.nth(1).fill("250")
        page.wait_for_timeout(600)
        ok(botones.nth(0).get_attribute("data-estado") == "propios",
           f"el boton de esa fila pasa a 'propios' ({botones.nth(0).get_attribute('data-estado')})")
        ok(botones.nth(0).inner_text().strip().startswith("Propios"),
           f"y dice 'Propios' ({botones.nth(0).inner_text().strip()})")
        otros = [botones.nth(i).get_attribute("data-estado") for i in range(1, n)]
        ok(all(e == "globales" for e in otros), f"ningun otro boton se movio: {set(otros)}")

        print("\n--- 7. 'Usar globales' lo devuelve ---")
        filas.nth(1).locator("button:has-text('Usar globales')").click()
        page.wait_for_timeout(600)
        ok(botones.nth(0).get_attribute("data-estado") == "globales",
           "el boton vuelve a 'Globales'")
        vuelta = tabla.locator("tbody > tr").nth(0).locator("td").nth(1).inner_text()
        ok(vuelta == critico_antes, "y la fila vuelve exactamente a como estaba")
        botones.nth(0).click()          # se cierra para no estorbar al paso 8
        page.wait_for_timeout(300)

        print("\n--- 8. La criticidad se sigue recalculando (D42) ---")
        # Con los criterios de fabrica las criticas de este JTL lo son por ERRORES,
        # y relajar el tiempo no las cambiaria. Se aprieta primero
        # el tiempo GLOBAL para tener una critica SOLO por tiempo, y se la devuelve
        # con su criterio propio — que es justo lo que hay que demostrar.
        page.locator("label:has-text('Tiempo de Respuesta (ms)')").locator(
            "xpath=following::input[1]").fill("100")
        page.wait_for_timeout(700)

        objetivo = None
        for i in range(tabla.locator("tbody > tr").count()):
            celdas = tabla.locator("tbody > tr").nth(i).locator("td")
            if celdas.count() < 7:
                continue
            texto = celdas.nth(1).inner_text()
            if ("crítica" in texto and "1 de cada 10 usuarios" in texto
                    and "errores" not in texto and "pico" not in texto):
                objetivo = i
                break
        if not ok(objetivo is not None, "al apretar el tiempo global aparece una critica SOLO por tiempo"):
            nav.close()
            return 1

        boton_obj = tabla.locator("tbody > tr").nth(objetivo).locator("[data-testid='boton-criterios']")
        nombre = boton_obj.get_attribute("data-tx")
        antes = tabla.locator("tbody > tr").nth(objetivo).locator("td").nth(1).inner_text()
        boton_obj.click()
        page.wait_for_timeout(400)
        tabla.locator("tbody > tr").nth(objetivo + 1).locator(
            "input[type=number]").nth(1).fill("99999")     # un limite que nadie incumple
        page.wait_for_timeout(700)
        despues = tabla.locator("tbody > tr").nth(objetivo).locator("td").nth(1).inner_text()
        print(f"    {nombre}")
        print(f"    antes:   {' / '.join(antes.split(chr(10)))[:110]}")
        print(f"    despues: {' / '.join(despues.split(chr(10)))[:110]}")
        ok("crítica" in antes, "antes de editar estaba marcada como critica")
        ok("crítica" not in despues,
           "al subir SU tiempo de respuesta deja de ser critica, sin volver a subir el archivo")
        ok(boton_obj.get_attribute("data-estado") == "propios", "y su boton quedo en 'Propios'")

        page.screenshot(path="/tmp/e2e_salida/etapa5b_panel.png", full_page=False)
        nav.close()

    print("\n" + "=" * 68)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("5b.2 — COLUMNA Y BOTON DE CRITERIOS: TODO PASA")
    print("=" * 68)
    return 1 if fallos else 0


sys.exit(main())
