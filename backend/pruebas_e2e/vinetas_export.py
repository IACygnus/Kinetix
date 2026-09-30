"""BLOQUE 2.3 — las vinetas de conclusiones y recomendaciones, en el HTML y en el PDF.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py
    docker exec jmeter_backend python3 /app/pruebas_e2e/vinetas_export.py

Contra la base de PRUEBAS y el 8002 (regla 34). Sobre «ZZTEST-R1 carga»:
  1. guarda sus conclusiones y recomendaciones;
  2. pone unas en vinetas «• » (textos ZZTEST, sin IA) y exporta HTML y PDF;
  3. devuelve los textos originales, pase lo que pase.
Comprueba que cada vineta sale en su propia linea en las dos salidas, y deja la
pagina del PDF con las conclusiones en /tmp/vinetas_pdf.png para mirarla.
Sin tocar los exportadores: son archivos protegidos y la rama web no se toca.
"""
import os
import re
import sys
import uuid
from datetime import timedelta

import httpx
import psycopg2

sys.path.insert(0, "/app")
from app.core.security import create_access_token  # noqa: E402
from app.services.ai.gemini import sanitize_ai_text  # noqa: E402

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
DB = os.environ.get("KX_DB", "jmeter_analyzer_test")
if "test" not in DB:
    sys.exit("PARADA: la base no es de pruebas")
PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB)
FALLOS = []

CONC = ("- ZZTEST conclusion uno: la plataforma sostuvo la carga sin degradarse.\n"
        "- ZZTEST conclusion dos: una transaccion concentro los fallos.\n"
        "- ZZTEST conclusion tres: la infraestructura no explica los errores.\n"
        "- ZZTEST conclusion cuatro: no es viable hasta corregir los fallos, porque incumple la disponibilidad.")
RECO = ("• ZZTEST recomendacion uno: revisar las trazas de la transaccion con fallos.\n"
        "• ZZTEST recomendacion dos: revisar sus dependencias.\n"
        "• ZZTEST recomendacion tres: repetir la prueba tras corregir.\n"
        "• ZZTEST recomendacion cuatro: mantener la capacidad actual.")


def ok(c, m):
    print(("  ok   " if c else "  FALLA ") + m)
    if not c:
        FALLOS.append(m)


def sql(q, a=()):
    c = psycopg2.connect(**PG)
    cur = c.cursor()
    cur.execute(q, a)
    f = cur.fetchall()
    c.close()
    return f


def main():
    eid = str(sql("select id from test_executions where name='ZZTEST-R1 carga'")[0][0])
    uid, un, role = sql("select id, username, role from users where username='admin'")[0]
    tok = create_access_token({"sub": str(uid), "username": un, "role": role}, timedelta(minutes=30))
    csrf = uuid.uuid4().hex
    cli = httpx.Client(cookies={"access_token": tok, "csrf_token": csrf},
                       headers={"X-CSRF-Token": csrf}, timeout=600)
    antes = cli.get(f"{API}/executions/{eid}").json()
    orig = {"ai_conclusions": antes.get("ai_conclusions") or "",
            "ai_recommendations": antes.get("ai_recommendations") or ""}

    conc = sanitize_ai_text(CONC)
    ok(conc.count("\n• ") == 3 and conc.startswith("• "), "el saneado convierte «- » en «• » y no la borra")
    try:
        r = cli.put(f"{API}/executions/{eid}/analysis", json={"ai_conclusions": conc, "ai_recommendations": RECO})
        ok(r.status_code == 200, f"PUT analisis -> {r.status_code}")

        html = cli.get(f"{API}/executions/{eid}/export/html").text
        for nombre, n in (("conclusion", 4), ("recomendacion", 4)):
            lineas = re.findall(rf"(?:<p>|<br>)• ZZTEST {nombre} \w+", html)
            ok(len(lineas) == n, f"HTML: {len(lineas)} vinetas de {nombre}, cada una al principio de su linea")

        pdf = cli.get(f"{API}/executions/{eid}/export/pdf").content
        open("/tmp/vinetas.pdf", "wb").write(pdf)
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument("/tmp/vinetas.pdf")
        pagina = None
        for i in range(len(doc)):
            txt = doc[i].get_textpage().get_text_range()
            if "ZZTEST conclusion uno" in txt:
                pagina = i
                lineas = [ln.strip() for ln in txt.splitlines()]
                for nombre in ("conclusion", "recomendacion"):
                    con = [ln for ln in lineas if re.match(rf"^• ZZTEST {nombre} \w+", ln)]
                    ok(len(con) == 4, f"PDF: {len(con)} lineas que empiezan por «• ZZTEST {nombre}»")
                break
        ok(pagina is not None, f"PDF: las conclusiones estan en la pagina {None if pagina is None else pagina + 1}")
        if pagina is not None:
            doc[pagina].render(scale=1.6).to_pil().save("/tmp/vinetas_pdf.png")
            print("    pagina guardada en /tmp/vinetas_pdf.png")
    finally:
        r = cli.put(f"{API}/executions/{eid}/analysis", json=orig)
        despues = cli.get(f"{API}/executions/{eid}").json()
        ok(r.status_code == 200 and (despues.get("ai_conclusions") or "") == orig["ai_conclusions"]
           and (despues.get("ai_recommendations") or "") == orig["ai_recommendations"],
           "los textos originales, devueltos")
    print()
    print("VINETAS: TODO PASA" if not FALLOS else f"VINETAS: {len(FALLOS)} FALLOS")
    return 0 if not FALLOS else 1


if __name__ == "__main__":
    sys.exit(main())
