"""E2E de Kinetix con Playwright — captura y comparacion de informes.

USO (dentro de jmeter_backend, que es donde vive el navegador):
    python3 /tmp/e2e/captura_informe.py capturar <etiqueta> [ids...]
    python3 /tmp/e2e/captura_informe.py comparar <etiqueta_a> <etiqueta_b>

Por que corre en el contenedor y no en el host:
el equipo no tiene node ni python; el contenedor si tiene python y Chromium.
Un rele TCP (rele_5173.py) hace que el frontend se vea como http://localhost:5173,
de modo que el ORIGEN sea el que el backend admite por CORS y que
http://localhost:8001 sea la API en ese mismo contenedor.

Parametrizable a proposito: sirve para la equivalencia de C1 (antes/despues de
un refactor), para la verificacion de 2.11 y como regresion de etapas futuras.
"""
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("KX_WEB", "http://localhost:5173")
API = os.environ.get("KX_API", "http://localhost:8001/api/v1")
USUARIO = os.environ.get("KX_USER", "admin")
CLAVE = os.environ.get("KX_PWD", "")
SALIDA = Path(os.environ.get("KX_OUT", "/tmp/e2e_salida"))

# Ejecuciones a capturar. Se pueden pasar por linea de comandos.
POR_DEFECTO = [
    ("ff186cc7", "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8"),
    ("baseline2", os.environ.get("KX_EID2", "")),
]

# Contenedor del informe. Se prueban varios selectores porque la pantalla puede
# cambiar entre etapas; el primero que exista manda.
SELECTORES_INFORME = ["main", "#root > div", "body"]


def _normalizar_dom(html: str) -> str:
    """Quita lo que cambia entre dos ejecuciones iguales.

    Sin esto, el diff seria ruido: recharts genera ids aleatorios en cada render y
    mete coordenadas con decimales que varian por redondeo.
    """
    s = html
    s = re.sub(r'\bid="[^"]*recharts[^"]*"', 'id="RECHARTS"', s)
    s = re.sub(r'\burl\(#[^)]*\)', 'url(#ID)', s)
    s = re.sub(r'\bclip-?[Pp]ath="[^"]*"', 'clipPath="ID"', s)
    s = re.sub(r'(-?\d+\.\d{2,})', lambda m: str(round(float(m.group(1)), 1)), s)
    s = re.sub(r'\b\d{4}-\d{2}-\d{2}T[\d:.]+Z?', 'FECHA', s)
    s = re.sub(r'\b\d{2}/\d{2}/\d{4},? ?[\d:]*', 'FECHA', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


# Cookies de sesion. Fuera del repo y se borra al cerrar la etapa.
SESION = Path(os.environ.get("KX_SESION", "/tmp/e2e_sesion.json"))
# Conteo de graficas de referencia por ejecucion. Se aprende en la primera captura
# y despues se exige: si una corrida trae menos, la pagina no cargo entera.
REFERENCIA = SALIDA / "referencia_graficas.json"


def _leer_referencia():
    try:
        return json.loads(REFERENCIA.read_text())
    except Exception:
        return {}


def _login_formulario(page):
    """Rellena y envia el formulario. Los inputs NO tienen atributo `name`.

    Se espera a la URL de destino, no a `networkidle`: la primera version esperaba
    networkidle, seguia demasiado pronto y todas las capturas salian de la pantalla
    de login — con el agravante de que eran identicas entre si, asi que la
    comparacion habria dado "equivalente" sobre dos paginas vacias.
    """
    page.locator('input[type="text"]').first.fill(USUARIO)
    page.locator('input[type="password"]').first.fill(CLAVE)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard", timeout=30000)


def _entrar(page):
    """Entra reutilizando la sesion; si esta caducada, UN solo login. Nunca un bucle.

    El limitador de /auth/login cuenta TAMBIEN los logins correctos (auth.py:96), 5
    por cada 15 minutos y por IP. Un bucle de reintentos no solo no ayuda: cada
    intento que SI pasa vuelve a gastar cupo. De ahi la regla: un intento, y si
    falla, error.
    """
    page.goto(BASE, wait_until="networkidle")
    if page.locator('input[type="password"]').count():
        _login_formulario(page)
        return page
    # Sesion reutilizada: comprobar que sigue viva antes de capturar nada.
    resp = page.request.get(f"{API}/auth/me")
    if resp.status == 401:
        print("  sesion guardada caducada: un unico re-login")
        page.goto(BASE, wait_until="networkidle")
        if not page.locator('input[type="password"]').count():
            raise RuntimeError("401 en /auth/me pero no aparece el formulario de login")
        _login_formulario(page)
    elif resp.status != 200:
        raise RuntimeError(f"/auth/me devolvio {resp.status}; se aborta sin reintentar")
    return page


def _esperar_estable(page, nombre, esperadas=None, timeout_s=60):
    """Espera a que la pagina deje de moverse y valida que cargo entera.

    Dos guardias, porque una captura a medias daria un diff falso:
      1. ESTABILIDAD: el numero de graficas y la longitud del DOM normalizado
         tienen que repetirse durante 2 s seguidos (sondeo cada 250 ms).
      2. COMPLETITUD: si se conoce cuantas graficas debe haber, tiene que
         coincidir. Cero graficas es siempre error.
    Agotar el tiempo es un error, no una captura silenciosa.
    """
    import time as _t
    inicio = _t.monotonic()
    previo = None
    estable_desde = None
    while _t.monotonic() - inicio < timeout_s:
        n = page.locator("svg.recharts-surface").count()
        dom = _normalizar_dom(_contenedor(page).inner_html())
        actual = (n, len(dom))
        if actual == previo and n > 0:
            if estable_desde is None:
                estable_desde = _t.monotonic()
            elif _t.monotonic() - estable_desde >= 2.0:
                if esperadas is not None and n != esperadas:
                    raise RuntimeError(
                        f"{nombre}: {n} graficas, se esperaban {esperadas} "
                        f"(url={page.url}) — captura descartada")
                return n, _contenedor(page).inner_html()
        else:
            estable_desde = None
        previo = actual
        page.wait_for_timeout(250)
    raise RuntimeError(
        f"{nombre}: la pagina no se estabilizo en {timeout_s}s "
        f"(ultimo estado: {previo}, url={page.url})")


def _contenedor(page):
    for sel in SELECTORES_INFORME:
        if page.locator(sel).count():
            return page.locator(sel).first
    return page.locator("body")


def capturar(etiqueta, objetivos, esperadas=None):
    destino = SALIDA / etiqueta
    destino.mkdir(parents=True, exist_ok=True)
    esperadas = esperadas or _leer_referencia()
    peticiones = []
    vistas = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        # Reusa la sesion guardada si existe. El login esta limitado a 5 intentos por
        # cada 15 minutos y por IP: entrar en cada corrida agotaba la cuota y las
        # siguientes recibian 429. Con esto se entra una vez y se reutiliza.
        estado = SESION if SESION.exists() else None
        ctx = navegador.new_context(viewport={"width": 1600, "height": 1200},
                                    storage_state=str(estado) if estado else None)
        page = ctx.new_page()
        page.on("request", lambda r: peticiones.append(f"{r.method} {r.url}")
                if "/api/v1/" in r.url else None)
        _entrar(page)
        ctx.storage_state(path=str(SESION))     # para las proximas corridas
        for nombre, eid in objetivos:
            if not eid:
                continue
            page.goto(f"{BASE}/performance/report/{eid}", wait_until="networkidle")
            n_graficas, html = _esperar_estable(page, nombre, esperadas.get(nombre))
            page.screenshot(path=str(destino / f"{nombre}.png"), full_page=True)
            (destino / f"{nombre}.dom.txt").write_text(_normalizar_dom(html), encoding="utf-8")
            vistas[nombre] = n_graficas
            print(f"  capturado {nombre}: {eid} ({n_graficas} graficas, DOM {len(html)} chars)")
        navegador.close()
    # /auth/* queda fuera del cotejo: depende de si la sesion se reutilizo o no, no
    # del render. Incluirlo daria una diferencia falsa entre una corrida que entro y
    # otra que reuso cookies — que es exactamente lo que paso en la calibracion.
    datos = sorted(set(re.sub(r"\?.*$", "", q) for q in peticiones if "/auth/" not in q))
    (destino / "peticiones.txt").write_text("\n".join(datos), encoding="utf-8")
    if not REFERENCIA.exists() and vistas:
        REFERENCIA.parent.mkdir(parents=True, exist_ok=True)
        REFERENCIA.write_text(json.dumps(vistas, indent=2))
        print(f"referencia de graficas fijada: {vistas}")
    print(f"guardado en {destino}")


def _diferencia_pixeles(a: Path, b: Path):
    """Porcentaje de pixeles distintos. Usa PIL, que ya esta en el backend."""
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        w = min(ia.size[0], ib.size[0])
        h = min(ia.size[1], ib.size[1])
        ia, ib = ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h))
        aviso = f" (recortadas a {w}x{h}; tamanos distintos)"
    else:
        aviso = ""
    dif = ImageChops.difference(ia, ib)
    distintos = sum(1 for px in dif.getdata() if px != (0, 0, 0))
    total = ia.size[0] * ia.size[1]
    return 100.0 * distintos / total, aviso


def comparar(a, b):
    da, db = SALIDA / a, SALIDA / b
    fallos = 0
    for dom_a in sorted(da.glob("*.dom.txt")):
        nombre = dom_a.name.replace(".dom.txt", "")
        dom_b = db / dom_a.name
        if not dom_b.exists():
            print(f"FALTA {dom_b}"); fallos += 1; continue
        ta, tb = dom_a.read_text(encoding="utf-8"), dom_b.read_text(encoding="utf-8")
        igual = ta == tb
        print(f"{'PASA ' if igual else 'FALLA'} | DOM normalizado de {nombre}"
              f"{'' if igual else f' | {len(ta)} vs {len(tb)} chars'}")
        fallos += 0 if igual else 1
        pa, pb = da / f"{nombre}.png", db / f"{nombre}.png"
        if pa.exists() and pb.exists():
            pct, aviso = _diferencia_pixeles(pa, pb)
            ok = pct < 1.0
            print(f"{'PASA ' if ok else 'FALLA'} | pixeles de {nombre}: {pct:.3f}% "
                  f"(umbral 1%){aviso}")
            fallos += 0 if ok else 1
    pa, pb = da / "peticiones.txt", db / "peticiones.txt"
    if pa.exists() and pb.exists():
        igual = pa.read_text() == pb.read_text()
        print(f"{'PASA ' if igual else 'FALLA'} | mismas llamadas de datos")
        if not igual:
            sa, sb = set(pa.read_text().split("\n")), set(pb.read_text().split("\n"))
            for x in sorted(sa - sb): print(f"    solo en {a}: {x}")
            for x in sorted(sb - sa): print(f"    solo en {b}: {x}")
        fallos += 0 if igual else 1
    print(f"\n=== {'EQUIVALENTE' if not fallos else f'{fallos} DIFERENCIAS'} ===")
    return fallos


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "capturar"
    if accion == "capturar":
        etiqueta = sys.argv[2] if len(sys.argv) > 2 else "antes"
        objetivos = ([(f"e{i}", x) for i, x in enumerate(sys.argv[3:])]
                     if len(sys.argv) > 3 else POR_DEFECTO)
        capturar(etiqueta, objetivos)
    elif accion == "comparar":
        sys.exit(1 if comparar(sys.argv[2], sys.argv[3]) else 0)
