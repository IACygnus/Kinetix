"""ETAPA 5.3 — El panel de seleccion, sobre la pantalla real de Nuevo Reporte.

NO genera ningun informe: sube el JTL al detector de transacciones y se queda
ahi. CERO llamadas a la IA.

Comprueba:
  1. Las columnas de v1.2 §2.1 (D39): Transaccion, Muestras, Promedio, TPS,
     Errores. Sin p90 ni Max.
  2. El TPS de cada fila es el MISMO que el de la tabla resumen del informe.
  3. Una fila se despliega (D40) y muestra sus tres criterios.
  4. Al subir su tiempo de respuesta, la marca "critica" y su texto cambian al
     instante, sin volver a subir el archivo (D42).
  5. "Usar globales" la devuelve a como estaba (D41).
  6. El bloque "Criterios por Transaccion" ya no existe (D43).

    python3 /tmp/e2e/panel_seleccion.py
"""
import os
import sys

from playwright.sync_api import sync_playwright

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
JTL = os.environ.get(
    "KX_JTL", "/app/uploads/20251222_201217_resultados_general_carga_22-dic-2025-150249.jtl")
EJECUCION = "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"   # el informe del MISMO JTL

COLUMNAS = ["Transacción", "Muestras", "Promedio", "TPS", "Errores"]
FUERA = ["p90", "P90", "Max"]

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1400},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        page.goto(WEB, wait_until="networkidle")
        if page.locator('input[type="password"]').count():
            page.locator('input[type="text"]').first.fill(os.environ.get("KX_USER", "admin"))
            page.locator('input[type="password"]').first.fill(os.environ.get("KX_PWD", ""))
            page.locator('button[type="submit"]').first.click()
            page.wait_for_url("**/dashboard", timeout=30000)
            ctx.storage_state(path=SESION)

        # El TPS de referencia: el de la tabla resumen del informe del mismo JTL.
        r = page.request.get(f"{API}/executions/{EJECUCION}/charts")
        referencia = {x["label"]: round(float(x["throughput"]), 2)
                      for x in r.json().get("by_label", [])}
        print(f"referencia (tabla resumen del informe): {len(referencia)} transacciones")

        page.goto(f"{WEB}/performance/new", wait_until="networkidle")
        page.set_input_files('input[type="file"]', JTL)
        page.wait_for_selector("text=Transacciones del JTL", timeout=120000)
        page.wait_for_timeout(1500)

        # ---------- 1. Las columnas ----------
        # La unica tabla de esta pantalla es la del panel.
        tabla = page.locator("table").first
        comprobar(tabla.count() == 1, "el panel pinta su tabla")
        # El CSS las pinta en mayusculas (`uppercase`), asi que se compara sin caso.
        encabezados = [h.strip().lower() for h in tabla.locator("thead th").all_inner_texts()]
        print(f"columnas: {[h for h in encabezados if h]}")
        for c in COLUMNAS:
            comprobar(c.lower() in encabezados, f"esta la columna '{c}'")
        for c in FUERA:
            comprobar(c.lower() not in encabezados, f"NO esta la columna '{c}'")

        # ---------- 2. El TPS coincide con el informe ----------
        filas = tabla.locator("tbody > tr")
        panel = {}
        for i in range(filas.count()):
            celdas = filas.nth(i).locator("td")
            if celdas.count() < 7:
                continue                      # fila desplegada, no es una transaccion
            # El nombre va en su propio <span>; al lado pueden ir las etiquetas
            # "crítica", que no forma parte del nombre. (El chip "criterios
            # propios" se retiro en el ajuste de la ETAPA 5b: ese estado lo
            # dice ahora el boton de la columna "Criterios".)
            nombre = celdas.nth(1).locator("span").first.inner_text().strip()
            tps = celdas.nth(4).inner_text().strip().replace(".", "").replace(",", ".")
            panel[nombre] = round(float(tps), 2)
        print(f"panel: {len(panel)} transacciones")
        comprobar(len(panel) == len(referencia),
                  f"el panel lista las mismas {len(referencia)} transacciones ({len(panel)})")
        distintos = {k: (v, referencia.get(k)) for k, v in panel.items()
                     if referencia.get(k) is None or abs(v - referencia[k]) > 0.01}
        comprobar(not distintos,
                  f"el TPS de cada fila es el de la tabla resumen del informe"
                  + (f" — difieren {distintos}" if distintos else ""))

        # ---------- 6. El bloque desplegable ya no existe ----------
        comprobar(page.locator("text=Criterios por Transaccion").count() == 0,
                  "el bloque 'Criterios por Transaccion' ya no existe")
        comprobar(page.locator("#bulk-conc").count() == 0,
                  "tampoco su 'aplicar el mismo criterio a todas'")

        # ---------- 3. Desplegar una fila ----------
        # Con los criterios de fabrica, las criticas de este JTL lo son por
        # ERRORES, y relajar el tiempo no las cambiaria. Para probar justo lo que
        # pide el guion —tocar el tiempo de respuesta de UNA fila— se aprieta
        # primero el criterio GLOBAL de tiempo: asi una transaccion sin errores
        # pasa a ser critica por tiempo, y su criterio propio podra devolverla.
        global_rt = page.locator("label:has-text('Tiempo de Respuesta (ms)')").locator(
            "xpath=following::input[1]")
        global_rt.fill("100")
        page.wait_for_timeout(600)

        objetivo, fila_idx = None, None
        for i in range(filas.count()):
            celdas = filas.nth(i).locator("td")
            if celdas.count() < 7:
                continue
            texto = celdas.nth(1).inner_text()
            if ("crítica" in texto and "1 de cada 10 usuarios" in texto
                    and "errores" not in texto and "pico" not in texto):
                objetivo = celdas.nth(1).locator("span").first.inner_text().strip()
                fila_idx = i
                break
        comprobar(objetivo is not None,
                  f"al apretar el tiempo global aparece una critica SOLO por tiempo ({objetivo})")
        if objetivo is None:
            nav.close()
            return 1

        filas.nth(fila_idx).locator("[data-testid='boton-criterios']").click()
        page.wait_for_timeout(400)
        desplegada = filas.nth(fila_idx + 1)
        etiquetas = desplegada.inner_text()
        for campo in ("Concurrencia esperada", "Tiempo de respuesta (ms)", "Disponibilidad (%)"):
            comprobar(campo in etiquetas, f"la fila desplegada muestra '{campo}'")
        comprobar("Usar globales" in etiquetas, "la fila desplegada trae 'Usar globales'")

        entradas = desplegada.locator("input[type=number]")
        comprobar(entradas.count() == 3, f"tres campos editables ({entradas.count()})")
        # D41: sin valores propios, el global se ve como marca de agua.
        marca = entradas.nth(1).get_attribute("placeholder")
        comprobar(marca == "100", f"el tiempo de respuesta muestra el global como marca de agua ({marca})")

        # ---------- 4. Editar y ver el cambio al instante ----------
        antes = filas.nth(fila_idx).locator("td").nth(1).inner_text()
        entradas.nth(1).fill("99999")       # un limite que nadie incumple
        page.wait_for_timeout(500)          # sin resubir el archivo: es en el cliente
        despues = filas.nth(fila_idx).locator("td").nth(1).inner_text()
        print(f"  antes:   {' / '.join(antes.split(chr(10)))[:110]}")
        print(f"  despues: {' / '.join(despues.split(chr(10)))[:110]}")
        comprobar("crítica" in antes, "antes de editar estaba marcada como critica")
        comprobar("crítica" not in despues, "al relajar su tiempo de respuesta deja de ser critica")
        # AJUSTE 5b: el indicador de "tiene criterios propios" es el boton de la
        # columna "Criterios", no un chip junto al nombre.
        comprobar(
            filas.nth(fila_idx).locator("[data-testid='boton-criterios']")
            .get_attribute("data-estado") == "propios",
            "y su boton de Criterios queda en 'Propios'")
        comprobar(antes != despues, "el texto bajo el nombre cambio al instante")

        # ---------- 5. "Usar globales" ----------
        desplegada.locator("button:has-text('Usar globales')").click()
        page.wait_for_timeout(500)
        vuelta = filas.nth(fila_idx).locator("td").nth(1).inner_text()
        comprobar(vuelta == antes, "'Usar globales' la devuelve exactamente a como estaba")

        page.screenshot(path="/tmp/e3/panel_seleccion.png", full_page=False)
        nav.close()

    print("\n" + "=" * 62)
    if fallos:
        print(f"{len(fallos)} FALLOS:")
        for f in fallos:
            print("  -", f)
        return 1
    print("PANEL DE SELECCION: TODO EN VERDE")
    return 0


sys.exit(main())
