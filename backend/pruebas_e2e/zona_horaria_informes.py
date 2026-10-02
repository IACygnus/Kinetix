"""Reporte 146 — la hora de los informes, con un JTL ZZTEST de EPOCA CONOCIDA.

    docker exec jmeter_backend python3 /app/pruebas_e2e/zona_horaria_informes.py

El JTL empieza en 1789769797000 ms = 2026-09-18T22:16:37Z = 17:16:37 en Bogota
y dura 120 s (ultima muestra 17:18:36). Comprueba que las SEIS salidas dicen la
hora de Colombia y que la base sigue en UTC:

  1. cabecera — la API (/executions/{id}) que pinta la pantalla
  2. graficas en pantalla — /charts y /transaction-charts: primer y ultimo punto
  3. PDF — cabecera en el HTML que se le da a WeasyPrint no se ve; se guarda el
     PDF en /tmp/146_zz.pdf y su TEXTO lo lee zona_pdf_texto (fuera del contenedor)
  4. HTML exportado — cabecera y eje X de Plotly
  5. integrado — export-html (cabecera y Plotly) y export-pdf (a /tmp/146_zz_int.pdf)
  6. prompts — linea de tiempo, reloj de fases/concentracion y de la serie de R2

Mas: lo que se GUARDA (a_utc de las metricas del parser) es 22:16:37 UTC, la
duracion no cambia y un instante que cruza la medianoche UTC cae el dia anterior.

Escribe SOLO en `jmeter_analyzer_test` (regla 34), con prefijo ZZTEST- (regla 29).
Contra el backend de PRUEBAS (8002), sin clave de IA: nada llama a la IA.
"""
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")
import httpx
import pandas as pd
import psycopg2
import psycopg2.extras

from app.core.security import create_access_token
from app.services.jtl.jtl_parser import JTLParser
from app.services.zona_informe import a_informe, a_utc, ZONA_INFORMES
from app.services.ai import contexto_prompt, fases as F, resumen_serie as R

API = os.environ.get("KX_API", "http://localhost:8002/api/v1")
DB = os.environ.get("KX_DB", "jmeter_analyzer_test")
if "test" not in DB:
    sys.exit(f"PARADA: '{DB}' no lleva 'test' en el nombre. No se escribe nada.")

EPOCA = 1789769797000                 # 2026-09-18T22:16:37Z
JTL = "ZZTEST-146_zona.jtl"
NOMBRE = "ZZTEST-146 zona horaria"
CLIENTE = "ZZTEST-146"
INICIO, FIN = "17:16:37", "17:18:36"
fallos = []


def ok(cond, que):
    print(("  ok    " if cond else "  FALLA ") + que)
    if not cond:
        fallos.append(que)


def escribir_jtl(ruta):
    filas = ["timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,"
             "failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect"]
    for s in range(120):
        for i, lb in enumerate(("ZZTEST Login", "ZZTEST Consulta")):
            hilos = min(10, 1 + s // 5)
            filas.append(f"{EPOCA + s * 1000 + i * 10},{200 + 5 * i + (s % 7)},{lb},200,OK,G 1-{1 + i},"
                         f"text,true,,512,128,{hilos},{hilos},http://zz/{i},{150 + i},0,3")
    with open(ruta, "w") as f:
        f.write("\n".join(filas) + "\n")


def preparar():
    ruta = f"/app/uploads/{JTL}"
    escribir_jtl(ruta)
    p = JTLParser(ruta)
    _, m = p.parse()
    c = psycopg2.connect(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname=DB)
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("select current_database() db")
    assert "test" in cur.fetchone()["db"]
    cur.execute("select id, username, role from users where username='admin'")
    admin = cur.fetchone()
    cur.execute("select id from clients where name=%s", (CLIENTE,))
    fila = cur.fetchone()
    cliente = fila["id"] if fila else str(uuid.uuid4())
    if not fila:
        cur.execute("insert into clients (id, name, description, is_active, created_at, updated_at) "
                    "values (%s,%s,'ZZTEST: reporte 146',true,now(),now())", (cliente, CLIENTE))
    # Lo que guarda /upload: a_utc de las metricas del parser (upload.py, 146).
    st, et = a_utc(m["start_time"]), a_utc(m["end_time"])
    cur.execute("select id from test_executions where name=%s", (NOMBRE,))
    fila = cur.fetchone()
    if fila:
        eid = str(fila["id"])
        cur.execute("update test_executions set start_time=%s, end_time=%s, duration_seconds=%s, "
                    "p50_response_time=%s, total_redirects=0 where id=%s",
                    (st, et, float(m["duration_seconds"]), float(m["median_response_time"]), eid))
    else:
        eid = str(uuid.uuid4())
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        cur.execute(
            "insert into test_executions (id, user_id, name, description, client, client_id, project, test_type, "
            "jtl_filename, start_time, end_time, duration_seconds, total_requests, total_errors, error_rate, "
            "avg_response_time, median_response_time, min_response_time, max_response_time, p90_response_time, "
            "p95_response_time, p99_response_time, p50_response_time, total_redirects, throughput, metric_unit, execution_date, created_at, updated_at) "
            "values (%s,%s,%s,'ZZTEST: reporte 146',%s,%s,'ZZTEST-146','load',%s,%s,%s,%s,%s,0,0,"
            "%s,%s,%s,%s,%s,%s,%s,%s,0,%s,'TPS',%s,%s,%s)",
            (eid, admin["id"], NOMBRE, CLIENTE, cliente, JTL, st, et, float(m["duration_seconds"]),
             int(m["total_requests"]), float(m["avg_response_time"]), float(m["median_response_time"]),
             float(m["min_response_time"]), float(m["max_response_time"]), float(m["p90_response_time"]),
             float(m["p95_response_time"]), float(m["p99_response_time"]), float(m["median_response_time"]),
             float(m["throughput"]),
             ahora, ahora, ahora))
    # Un informe por transaccion minimo, para que el PDF/HTML pinte su bloque.
    cur.execute("select count(*) n from transaction_chart_analyses where execution_id=%s", (eid,))
    if cur.fetchone()["n"] == 0:
        cur.execute("insert into transaction_chart_analyses (id, execution_id, label, section, ai_analysis, "
                    "generated_at, is_edited, sort_order, created_at) values (%s,%s,'ZZTEST Login','summary',"
                    "'ZZTEST resumen.',now(),false,0,now())", (str(uuid.uuid4()), eid))
    c.commit()
    cur.execute("select start_time, end_time from test_executions where id=%s", (eid,))
    guardado = cur.fetchone()
    c.close()
    return eid, admin, p, m, guardado


def main():
    print(f"zona de los informes: {ZONA_INFORMES}")
    eid, admin, p, m, guardado = preparar()

    print("\n0. lo que se guarda y la conversion")
    ok(str(guardado["start_time"]) == "2026-09-18 22:16:37", f"base: start_time {guardado['start_time']} (UTC)")
    ok(str(guardado["end_time"]) == "2026-09-18 22:18:36.010000", f"base: end_time {guardado['end_time']} (UTC)")
    ok(round(m["duration_seconds"], 2) == 119.01, f"duracion {m['duration_seconds']} s: la conversion no la toca")
    ok(str(a_informe(datetime(2026, 9, 19, 1, 30))) == "2026-09-18 20:30:00",
       "01:30Z del 19 es 20:30 del 18 en Bogota (cruce de medianoche)")
    ok(a_utc(a_informe(datetime(2026, 9, 18, 22, 16, 37))) == datetime(2026, 9, 18, 22, 16, 37), "ida y vuelta exacta")

    tok = create_access_token({"sub": str(admin["id"]), "username": admin["username"], "role": admin["role"]},
                              timedelta(minutes=30))
    ck = {"access_token": tok, "csrf_token": uuid.uuid4().hex}
    hdr = {"X-CSRF-Token": ck["csrf_token"]}
    with httpx.Client(timeout=600, cookies=ck) as cli:
        print("\n1. cabecera (API de la pantalla)")
        e = cli.get(f"{API}/executions/{eid}").json()
        ok(e["start_time"] == "2026-09-18T17:16:37", f"start_time {e['start_time']}")
        ok(e["end_time"].startswith("2026-09-18T17:18:36"), f"end_time {e['end_time']}")
        lista = [x for x in cli.get(f"{API}/executions").json() if x["id"] == eid]
        ok(lista and lista[0]["start_time"] == "2026-09-18T17:16:37", "la lista del historial dice lo mismo")

        print("\n2. graficas en pantalla")
        ch = cli.get(f"{API}/executions/{eid}/charts").json()
        for k in ("timeline", "response_times_by_label", "latency_timeline", "error_rate_timeline",
                  "active_threads_timeline", "tps_by_label", "codes_per_second"):
            s = ch.get(k) or []
            ok(bool(s) and s[0]["timestamp"][11:16] == "17:16" and s[-1]["timestamp"][11:16] == "17:18",
               f"{k}: {s[0]['timestamp'][11:19] if s else '-'} .. {s[-1]['timestamp'][11:19] if s else '-'}")
        tx = cli.get(f"{API}/executions/{eid}/transaction-charts", params={"label": "ZZTEST Login"}).json()
        for k in ("response_times", "latency", "error_rate", "tps"):
            s = tx.get(k) or []
            ok(bool(s) and s[0]["timestamp"][11:19] == INICIO and s[-1]["timestamp"][11:16] == "17:18",
               f"transaccion {k}: {s[0]['timestamp'][11:19] if s else '-'} .. {s[-1]['timestamp'][11:19] if s else '-'}")

        print("\n3-4. HTML y PDF individuales")
        h = cli.get(f"{API}/executions/{eid}/export/html").text
        ok(f"{INICIO} &rarr; {FIN}" in h, "HTML: cabecera 17:16:37 -> 18:36")
        ok(not re.search(r"(?<![\d:])22:1[68]", h) and not re.search(r"T22:\d\d:\d\d", h), "HTML: ninguna hora UTC")
        xs = re.findall(r'"x":\s*\[\s*"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', h)
        ok(bool(xs) and all(x[11:16] == "17:16" for x in xs), f"HTML: {len(xs)} trazas Plotly empiezan a las 17:16")
        pdf = cli.get(f"{API}/executions/{eid}/export/pdf").content
        open("/tmp/146_zz.pdf", "wb").write(pdf)
        ok(pdf[:4] == b"%PDF", "PDF individual -> /tmp/146_zz.pdf (texto: zona_pdf_texto.py)")

        print("\n5. integrado")
        cuerpo = {"sections": [{"order": 0, "type": "load_test", "source_id": eid, "source_name": NOMBRE}],
                  "unified_conclusions": "", "name": "ZZTEST-146 integrado"}
        r = cli.post(f"{API}/reports/integrated/export-html", json=cuerpo, headers=hdr)
        hi = r.text
        ok(r.status_code == 200 and INICIO in hi and FIN in hi, f"integrado HTML ({r.status_code}): {INICIO} y {FIN}")
        ok(not re.search(r"(?<![\d:])22:1[68]", hi) and not re.search(r"T22:\d\d:\d\d", hi), "integrado HTML: ninguna hora UTC")
        xi = re.findall(r'"x":\s*\[\s*"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', hi)
        ok(bool(xi) and all(x[11:16] == "17:16" for x in xi), f"integrado HTML: {len(xi)} trazas Plotly a las 17:16")
        r = cli.post(f"{API}/reports/integrated/export-pdf", json=cuerpo, headers=hdr)
        open("/tmp/146_zz_int.pdf", "wb").write(r.content)
        ok(r.status_code == 200 and r.content[:4] == b"%PDF", "integrado PDF -> /tmp/146_zz_int.pdf")

    print("\n6. prompts (en proceso, sin IA)")
    linea = contexto_prompt.linea_de_tiempo(p.df, con_fecha=True)
    ok(f"de {INICIO} a {FIN} del 18/09/2026" in linea, f"linea de tiempo: «{linea[:70]}»")
    f = F.calcular(p.df)
    ok(F._reloj(f, 0) == INICIO, f"fases/concentracion: reloj del segundo 0 = {F._reloj(f, 0)}")
    ok(R._reloj(p.df["timestamp"].min()) == INICIO, f"serie de R2: reloj del primer punto = {R._reloj(p.df['timestamp'].min())}")
    cab = R.cabecera(p.df, 10, f)
    ok("22:1" not in cab, f"cabecera de la serie sin hora UTC: «{cab[:90]}»")

    print("\nTODO PASA" if not fallos else f"\n{len(fallos)} FALLA(N): {fallos}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
