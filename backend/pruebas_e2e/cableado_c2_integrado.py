"""Prueba de cableado (C2) en el INFORME INTEGRADO.

Lo que demuestra, sobre la pantalla real del integrado:

  1. Editar una caja de analisis dentro de una seccion del integrado guarda en
     `integrated_reports.sections[].overrides.analysis` (JSONB) — el canal de
     overrides, no el de la ejecucion.
  2. La ejecucion original (`test_executions`) NO cambia. Es lo que hace que un
     informe integrado pueda decir algo distinto sin pisar el informe individual.
  3. Al recargar la pagina, el texto editado sigue ahi.

Deja el texto como estaba, pase lo que pase.

Uso (dentro de jmeter_backend, con el rele 5173 arriba):
    python3 /tmp/e2e/cableado_c2_integrado.py [report_id]
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SESION = os.environ.get("KX_SESION", "/tmp/e2e_sesion.json")
REPORTE = sys.argv[1] if len(sys.argv) > 1 else "fa724249-aee1-4b08-b1af-a3aaf58a4eca"

GRAFICA = "Latency Over Time"
CAMPO = "ai_analysis_latency"
ESPERA_MS = 6000            # el debounce del integrado + el PATCH

fallos = []


def comprobar(ok, texto):
    print(f"{'PASA ' if ok else 'FALLA'} | {texto}")
    if not ok:
        fallos.append(texto)


def _login(page):
    page.locator('input[type="text"]').first.fill(USUARIO)
    page.locator('input[type="password"]').first.fill(CLAVE)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard", timeout=30000)


def _entrar(page):
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        _login(page)
        return
    r = page.request.get(f"{API}/auth/me")
    if r.status == 401:
        page.goto(BASE, wait_until="networkidle")
        if not page.locator('input[type="password"]').count():
            raise RuntimeError("401 en /auth/me y no aparece el formulario")
        _login(page)
    elif r.status != 200:
        raise RuntimeError(f"/auth/me devolvio {r.status}; se aborta sin reintentar")


def _informe(page):
    return page.request.get(f"{API}/reports/integrated-reports/{REPORTE}").json()


def _override(rep, exec_id):
    for s in rep.get("sections") or []:
        if s.get("source_id") == exec_id and s.get("type") in ("load_test", "stress_test"):
            return ((s.get("overrides") or {}).get("analysis") or {}).get(CAMPO, "")
    return None


def _campo_ejecucion(page, exec_id):
    return (page.request.get(f"{API}/executions/{exec_id}").json() or {}).get(CAMPO) or ""


def _abrir(page):
    page.goto(f"{BASE}/performance/integrated/{REPORTE}", wait_until="networkidle")
    page.wait_for_selector("svg.recharts-surface", timeout=90000)
    page.wait_for_timeout(5000)


def _caja(page):
    return page.locator("h3", has_text=GRAFICA).first.locator("xpath=following::textarea[1]")


def main():
    marca = f"[c2-integrado {int(time.time())}]"
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1600, "height": 1200},
                              storage_state=SESION if os.path.exists(SESION) else None)
        page = ctx.new_page()
        _entrar(page)
        ctx.storage_state(path=SESION)
        _abrir(page)

        rep = _informe(page)
        secciones = [s for s in (rep.get("sections") or [])
                     if s.get("type") in ("load_test", "stress_test")]
        comprobar(bool(secciones), f"el informe '{rep.get('name')}' trae secciones de ejecucion")
        if not secciones:
            nav.close()
            return 1
        exec_id = secciones[0]["source_id"]
        original_ov = _override(rep, exec_id) or ""
        original_exec = _campo_ejecucion(page, exec_id)
        print(f"seccion de prueba: {exec_id}")
        print(f"  override inicial {len(original_ov)} chars · campo de la ejecucion "
              f"{len(original_exec)} chars")

        caja = _caja(page)
        comprobar(caja.count() == 1, f"la caja de {GRAFICA} existe en el integrado")
        if caja.count() != 1:
            nav.close()
            return 1

        try:
            nuevo = f"{original_ov or original_exec}\n{marca}"
            caja.click()
            caja.fill(nuevo)
            caja.blur()
            page.wait_for_timeout(ESPERA_MS)

            rep2 = _informe(page)
            comprobar(marca in (_override(rep2, exec_id) or ""),
                      "la edicion se guarda en sections[].overrides.analysis del integrado")
            comprobar(marca not in _campo_ejecucion(page, exec_id),
                      "la ejecucion original (test_executions) NO cambia")

            # --- recargar y comprobar que persiste
            _abrir(page)
            comprobar(marca in _caja(page).input_value(),
                      "al recargar la pagina, el texto editado sigue ahi")
        finally:
            caja = _caja(page)
            caja.click()
            caja.fill(original_ov or original_exec)
            caja.blur()
            page.wait_for_timeout(ESPERA_MS)
            fin_ov = _override(_informe(page), exec_id) or ""
            comprobar(marca not in fin_ov, "el texto del integrado queda sin la marca")
            comprobar(_campo_ejecucion(page, exec_id) == original_exec,
                      "la ejecucion original sigue exactamente igual que al empezar")
            nav.close()

    print(f"\n=== {'CABLEADO CORRECTO' if not fallos else f'{len(fallos)} FALLOS'} ===")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
