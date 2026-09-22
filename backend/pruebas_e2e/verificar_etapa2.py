"""ETAPA 2.11 — verificacion de punta a punta de las CUATRO salidas.

Encadena las comprobaciones de los sub-pasos anteriores en una sola corrida, para
que la etapa se pueda re-verificar entera con un comando y para que sirva de
regresion en etapas futuras.

    docker exec -e KX_PWD=... jmeter_backend python3 /tmp/e2e/verificar_etapa2.py

No hace NINGUNA llamada a la IA: solo lee lo que ya esta guardado y vuelve a
generar informes con ello.
"""
import os
import subprocess
import sys

EJECUCION = os.environ.get("KX_EID", "ff186cc7-5be0-4a59-957c-e6b6b0fa00f8")
# ETAPA 5: 11 del general + 5 por transaccion. Se deriva del propio informe en
# vez de fijarlo: E5-panel tiene 2 transacciones y E3-estilo-pruebakinetix, 3.
GRAFICAS_POR_TRANSACCION = 5
GRAFICAS_GENERALES = 11

PASOS = [
    ("1. PANTALLA — el informe carga entero y con el orden de v1.2",
     ["python3", "/tmp/e2e/captura_informe.py", "capturar", "verificacion_2_11", EJECUCION]),
    ("2. PANTALLA — cada analisis guarda en su canal (C2)",
     ["python3", "/tmp/e2e/cableado_c2.py", EJECUCION]),
    ("2b. PANTALLA — la tabla resumen de cada transaccion (D15)",
     ["python3", "/tmp/e2e/tabla_por_transaccion.py", EJECUCION]),
    ("3. PDF individual",
     ["python3", "/tmp/e2e/pdf_real_html.py", EJECUCION]),
    ("4. HTML individual — contenido",
     ["python3", "/tmp/e2e/html_real.py", "/tmp/html_verificacion.txt"]),
    ("5. HTML individual — comprobaciones",
     ["python3", "/tmp/e2e/html_check.py", "/tmp/html_verificacion.txt"]),
    ("6. HTML individual — se abre y pinta en un navegador",
     ["python3", "/tmp/e2e/html_render.py"]),
    ("7. INTEGRADO — PDF y HTML por HTTP",
     ["python3", "/tmp/e2e/integrado_check.py"]),
    ("8. INTEGRADO — el recorte de conclusiones respeta los bloques por transaccion",
     ["python3", "/tmp/e2e/integrado_pdf_html.py", EJECUCION]),
    ("9. INTEGRADO — cada edicion guarda en overrides y no toca la ejecucion (C2)",
     ["python3", "/tmp/e2e/cableado_c2_integrado.py"]),
    # HF-4 (D38): el bloque retirado no puede reaparecer por ninguna salida, y la
    # tabla de cada bloque por transaccion es la misma del informe general.
    ("10. HF-4 — sin el bloque por transaccion critica, y la misma tabla del general",
     ["python3", "/tmp/e2e/hf4_check.py", EJECUCION]),
]


def _bloques_por_transaccion(execution_id):
    """Cuantos bloques por transaccion tiene ESTE informe, leidos de la base.

    Es el numero de etiquetas con mini-informe guardado, que es exactamente lo
    que la pantalla pinta.
    """
    sql = ("select count(distinct label) from transaction_chart_analyses "
           f"where execution_id = '{execution_id}'")
    r = subprocess.run(
        ["psql", "-U", "jmeter_user", "-d", "jmeter_analyzer_db", "-t", "-A", "-c", sql],
        capture_output=True, text=True,
        env={**os.environ, "PGHOST": "postgres", "PGPASSWORD": "jmeter_secure_2024"})
    try:
        return int((r.stdout or "0").strip())
    except ValueError:
        return 0


def main():
    fallos = []
    for titulo, cmd in PASOS:
        print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        salida = (r.stdout or "") + (r.stderr or "")
        print(salida.strip()[-2500:])
        # La captura no devuelve codigo de error propio: se valida el recuento.
        if cmd[1].endswith("captura_informe.py"):
            # ETAPA 5: el numero de graficas depende de cuantas transacciones
            # tenga ESTE informe, asi que se lee del propio DOM en vez de fijarlo.
            bloques = _bloques_por_transaccion(EJECUCION)
            esperadas = GRAFICAS_GENERALES + GRAFICAS_POR_TRANSACCION * bloques
            ok = f"({esperadas} graficas" in salida
            print(f"{'PASA ' if ok else 'FALLA'} | la pagina trae {esperadas} graficas "
                  f"({GRAFICAS_GENERALES} del general + {GRAFICAS_POR_TRANSACCION} x {bloques})")
        else:
            ok = r.returncode == 0
        if not ok:
            fallos.append(titulo)

    print(f"\n{'=' * 78}")
    if fallos:
        print(f"{len(fallos)} PASO(S) CON FALLOS:")
        for f in fallos:
            print("  -", f)
    else:
        print("ETAPA 2 — LAS CUATRO SALIDAS PASAN")
    print("=" * 78)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
