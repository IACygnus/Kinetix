"""ETAPA H1.4 y H1.5 — las pantallas de Actividades y Proyectos.

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/h15_pantallas.py

Crea SUS PROPIOS datos y los borra al final (regla del reporte 38).
0 llamadas a la IA.

  1. El menú "Horas" con Proyectos y Actividades.
  2. Actividades: las cinco sembradas, crear una, desactivar y reactivar,
     y que el borrado se bloquee con su motivo cuando está en uso.
  3. Proyectos: crear con dos actividades, ampliar una estimación y ver el
     historial con el valor anterior y el nuevo, quitar una actividad sin horas,
     e intentar un nombre duplicado y ver el error.
"""
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

# CARGA REAL §3: el catálogo son OCHO y la lista está en el producto, no aquí.
sys.path.insert(0, "/app")
from app.services.horas.sinonimos_actividad import CANONICAS  # noqa: E402

WEB = os.environ.get("KX_WEB", "http://localhost:5173")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion_test.json")
# H-D76: la pantalla es la de siempre (el frontend apunta al 8001), pero el
# navegador desvía sus llamadas al backend de pruebas. Lo que se escribe cae en
# la base de pruebas y la de Fredy no se toca.
BASE = os.environ.get("KX_DB", "jmeter_analyzer_test")
PUERTO_API = os.environ.get("KX_API_PUERTO", "8002")
# Regla 29: todo dato de prueba lleva la marca.
ACT_NUEVA = "ZZTEST-Actividad H1.5"
PROYECTO = "ZZTEST-Proyecto H1.5"

fallos = []


def ok(cond, texto):
    print(f"{'PASA ' if cond else 'FALLA'} | {texto}")
    if not cond:
        fallos.append(texto)
    return cond


def desviar_al_backend_de_pruebas(page):
    """El navegador pide al 8001; se reescribe al puerto de pruebas (H-D76)."""
    if PUERTO_API == "8001":
        return
    page.route(
        "http://localhost:8001/**",
        lambda ruta: ruta.continue_(
            url=ruta.request.url.replace("localhost:8001", f"localhost:{PUERTO_API}")))


def limpiar():
    """Borra SOLO lo que esta prueba marcó con ZZTEST- (reglas 29 y 30).

    Y solo en una base de pruebas: si el nombre no lleva 'test', se para.
    """
    if "test" not in BASE:
        sys.exit(f"PARADA: '{BASE}' no es una base de pruebas. No se borra nada.")
    sql = (
        "delete from project_activity_changes where project_id in "
        f"  (select id from projects where name = '{PROYECTO}');"
        "delete from project_activities where project_id in "
        f"  (select id from projects where name = '{PROYECTO}');"
        f"delete from projects where name = '{PROYECTO}';"
        f"delete from activities where name = '{ACT_NUEVA}';"
    )
    subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", BASE, "-q", "-c", sql],
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"},
        capture_output=True)


def main():
    limpiar()   # por si una corrida anterior se quedó a medias
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1700, "height": 1300},
                              storage_state=SESION if os.path.exists(SESION) else None,
                              locale="es-CO")
        page = ctx.new_page()
        desviar_al_backend_de_pruebas(page)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))

        page.goto(WEB, wait_until="networkidle")
        if page.locator('input[type="password"]').count():
            page.locator('input[type="text"]').first.fill(os.environ.get("KX_USER", "admin"))
            page.locator('input[type="password"]').first.fill(os.environ.get("KX_PWD", ""))
            page.locator('button[type="submit"]').first.click()
            page.wait_for_url("**/dashboard", timeout=30000)
            ctx.storage_state(path=SESION)

        # ---------- 1. El menú ----------
        print("--- 1. El menú Horas ---")
        menu = page.get_by_text("Horas", exact=True)
        ok(menu.count() >= 1, "existe la sección «Horas» en el menú")
        menu.first.click()
        page.wait_for_timeout(600)
        ok(page.get_by_role("link", name="Proyectos").count() >= 1, "entrada «Proyectos»")
        ok(page.get_by_role("link", name="Actividades").count() >= 1, "entrada «Actividades»")

        # ---------- 2. Actividades ----------
        print("\n--- 2. Actividades ---")
        page.goto(f"{WEB}/horas/actividades", wait_until="networkidle")
        page.wait_for_selector("[data-testid='tabla-actividades'] tr", timeout=20000)
        filas = page.locator("[data-testid='tabla-actividades'] tr")
        # CARGA REAL §3: la siembra son OCHO, no cinco, y la lista vive en
        # `sinonimos_actividad.CANONICAS`. Se comprueba que **estén las ocho**,
        # no que la tabla tenga ocho filas: una base de pruebas acumula
        # actividades de pasadas anteriores y contar filas haría fallar esta
        # prueba por algo que no es el catálogo.
        nombres = set(filas.locator("td:first-child").all_inner_texts())
        faltan = sorted(set(CANONICAS) - {n.strip() for n in nombres})
        ok(not faltan, f"están las ocho actividades sembradas (faltan: {faltan or 'ninguna'})")
        nombres = [filas.nth(i).get_attribute("data-actividad") for i in range(filas.count())]
        print(f"    {nombres}")
        ok("Planeación" in nombres, "con sus tildes: «Planeación»")

        page.locator("[data-testid='nueva-actividad']").fill(ACT_NUEVA)
        page.locator("[data-testid='crear-actividad']").click()
        page.wait_for_timeout(1200)
        fila = page.locator(f"[data-actividad='{ACT_NUEVA}']")
        ok(fila.count() == 1, f"se creó «{ACT_NUEVA}»")
        ok(fila.locator("[data-estado='activa']").count() == 1, "nace activa")

        # Sin proyectos ni horas: el admin SÍ puede borrarla.
        ok(not fila.locator("[data-testid='borrar-actividad']").first.is_disabled(),
           "recién creada y sin uso, se puede borrar")

        fila.locator("[data-testid='alternar-actividad']").click()
        page.wait_for_timeout(1000)
        fila = page.locator(f"[data-actividad='{ACT_NUEVA}']")
        ok(fila.locator("[data-estado='inactiva']").count() == 1, "desactivar la marca inactiva")
        fila.locator("[data-testid='alternar-actividad']").click()
        page.wait_for_timeout(1000)
        ok(page.locator(f"[data-actividad='{ACT_NUEVA}'] [data-estado='activa']").count() == 1,
           "volver a activarla")

        # ---------- 3. Proyectos: crear ----------
        print("\n--- 3. Crear un proyecto con dos actividades ---")
        page.goto(f"{WEB}/horas/proyectos", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.locator("[data-testid='nuevo-proyecto']").click()
        page.wait_for_selector("[data-testid='nuevo-cliente']", timeout=15000)

        page.locator("[data-testid='nuevo-cliente']").select_option(index=1)
        page.locator("[data-testid='nuevo-nombre']").fill(PROYECTO)
        lineas = page.locator("[data-testid='lineas-nuevas'] > div")
        lineas.nth(0).locator("select").select_option(index=1)
        lineas.nth(0).locator("input").fill("40")
        page.locator("[data-testid='anadir-linea']").click()
        page.wait_for_timeout(400)
        lineas = page.locator("[data-testid='lineas-nuevas'] > div")
        lineas.nth(1).locator("select").select_option(index=1)
        lineas.nth(1).locator("input").fill("10.5")

        ok(not page.locator("[data-testid='guardar-proyecto']").is_disabled(),
           "con cliente, nombre y dos actividades, el botón se habilita")
        page.locator("[data-testid='guardar-proyecto']").click()
        page.wait_for_selector("[data-testid='nombre-proyecto']", timeout=20000)
        ok(page.locator("[data-testid='nombre-proyecto']").inner_text().strip() == PROYECTO,
           "se creó y abrió su detalle")
        total = page.locator("[data-testid='total-estimado']").inner_text().strip()
        ok(total == "50,5", f"el total estimado sale en formato español: {total}")

        # ---------- 4. Ampliar una estimación y ver el historial ----------
        print("\n--- 4. Ampliar la estimación y el historial (H-D11) ---")
        est = page.locator("[data-testid='estimacion']").first
        est.fill("60")
        est.blur()
        page.wait_for_timeout(1500)
        total = page.locator("[data-testid='total-estimado']").inner_text().strip()
        ok(total == "70,5", f"el total se actualiza a 70,5 ({total})")

        page.locator("[data-testid='ver-historial']").click()
        page.wait_for_selector("[data-testid='tabla-historial'] tr", timeout=15000)
        filas_h = page.locator("[data-testid='tabla-historial'] tr")
        ok(filas_h.count() == 3, f"el historial tiene 3 filas: dos altas y un cambio ({filas_h.count()})")
        primera = filas_h.nth(0).inner_text().replace("\n", " · ")
        print(f"    {primera}")
        ok("cambio" in primera, "la más reciente es el cambio")
        ok("40" in primera and "60" in primera, "muestra el valor anterior y el nuevo")
        # H-D65: el historial nombra a la persona por su nombre completo, no por
        # el usuario. Se pregunta al propio producto cuál es, para que la prueba
        # valga igual en la base de pruebas que en la de Fredy.
        nombre = page.evaluate(
            "async () => (await (await fetch('http://localhost:8001/api/v1/auth/me',"
            " {credentials: 'include'})).json()).full_name")
        ok(bool(nombre) and nombre in primera, f"y quién lo hizo («{nombre}»)")

        # ---------- 5. Quitar una actividad sin horas ----------
        print("\n--- 5. Quitar una actividad sin horas (H-D12) ---")
        page.on("dialog", lambda d: d.accept())
        antes = page.locator("[data-testid='tabla-actividades-proyecto'] tr").count()
        page.locator("[data-testid='quitar-actividad']").nth(1).click()
        page.wait_for_timeout(1500)
        despues = page.locator("[data-testid='tabla-actividades-proyecto'] tr").count()
        ok(despues == antes - 1, f"queda una actividad menos ({antes} -> {despues})")

        # ---------- 6. Nombre duplicado ----------
        print("\n--- 6. Un nombre duplicado da error ---")
        page.goto(f"{WEB}/horas/proyectos", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.locator("[data-testid='nuevo-proyecto']").click()
        page.wait_for_selector("[data-testid='nuevo-cliente']", timeout=15000)
        page.locator("[data-testid='nuevo-cliente']").select_option(index=1)
        # Mismo nombre en minúsculas y con espacios: tiene que chocar igual.
        page.locator("[data-testid='nuevo-nombre']").fill(f"  {PROYECTO.lower()}  ")
        lineas = page.locator("[data-testid='lineas-nuevas'] > div")
        lineas.nth(0).locator("select").select_option(index=1)
        lineas.nth(0).locator("input").fill("8")
        page.locator("[data-testid='guardar-proyecto']").click()
        page.wait_for_timeout(2000)
        err = page.locator("[data-testid='error-proyectos']")
        ok(err.count() == 1, "se muestra el error")
        if err.count():
            texto = err.inner_text()
            print(f"    «{texto}»")
            ok("ya tiene un proyecto" in texto,
               "el mensaje explica que ese cliente ya tiene ese proyecto")

        # ---------- 7. Consola ----------
        print("\n--- 7. Sin errores de página ---")
        ok(not errores, f"cero errores de JavaScript ({errores[:2]})")

        page.screenshot(path="/tmp/e2e_salida/h15_proyectos.png", full_page=False)
        nav.close()

    limpiar()
    print("\n    datos de prueba borrados")
    print("\n" + "=" * 68)
    if fallos:
        print(f"{len(fallos)} FALLO(S):")
        for f in fallos:
            print("  -", f)
    else:
        print("H1.4 y H1.5 — LAS DOS PANTALLAS: TODO PASA")
    print("=" * 68)
    return 1 if fallos else 0


sys.exit(main())
