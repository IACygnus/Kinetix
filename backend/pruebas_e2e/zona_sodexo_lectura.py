"""146 — la hora de los informes contra la ejecucion REAL de Sodexo, en SOLO LECTURA.

Solo GET (pantalla, series, PDF, HTML). Token generado en proceso: no gasta
cupo de login (regla 26). No escribe nada en la base de Fredy.

    docker exec jmeter_backend python3 /app/pruebas_e2e/zona_sodexo_lectura.py
"""
import io, re, sys, uuid
from datetime import timedelta
sys.path.insert(0, "/app")
import httpx, psycopg2
from app.core.security import create_access_token

API = "http://localhost:8001/api/v1"
NOMBRE, INICIO, FIN = "Dispersion_2_1000C_1809", "17:16:37", "18:03:51"
c = psycopg2.connect(host="postgres", user="jmeter_user", password="jmeter_secure_2024", dbname="jmeter_analyzer_db")
cur = c.cursor()
cur.execute("select id, username, role from users where username='admin'"); uid, un, ro = cur.fetchone()
cur.execute("select id, start_time, duration_seconds from test_executions where name=%s and jtl_filename like %s",
            (NOMBRE, "%18-sept.-2026-171637%"))
eid, st_db, dur = cur.fetchone()
tok = create_access_token({"sub": str(uid), "username": un, "role": ro}, timedelta(minutes=30))
ck = {"access_token": tok, "csrf_token": uuid.uuid4().hex}
fallos = []
def ok(cond, que):
    print(("  ok    " if cond else "  FALLA ") + que)
    if not cond: fallos.append(que)

print(f"ejecucion {eid}  base: start_time={st_db} (UTC, no se toca)  duracion={dur}s")
ok(str(st_db).startswith("2026-09-18 22:16:37"), "la base sigue en UTC: 22:16:37")
with httpx.Client(timeout=600, cookies=ck) as cli:
    e = cli.get(f"{API}/executions/{eid}").json()
    ok(e["start_time"].startswith("2026-09-18T17:16:37"), f"API start_time {e['start_time']}")
    ok(e["end_time"].startswith("2026-09-18T18:03:51"), f"API end_time {e['end_time']}")
    ok(int(e["duration_seconds"]) // 60 == 47 and int(e["duration_seconds"]) % 60 == 13, "duracion 47m 13s")
    ch = cli.get(f"{API}/executions/{eid}/charts").json()
    tl = ch["timeline"]
    ok(tl[0]["timestamp"][11:16] == "17:16", f"grafica: primer punto {tl[0]['timestamp']}")
    ok(tl[-1]["timestamp"][11:16] == "18:03", f"grafica: ultimo punto {tl[-1]['timestamp']}")
    for k in ("response_times_by_label", "latency_timeline", "error_rate_timeline", "active_threads_timeline", "tps_by_label", "codes_per_second"):
        s = ch.get(k) or []
        if s:
            ok(s[0]["timestamp"][11:13] == "17" and s[-1]["timestamp"][11:13] == "18", f"{k}: {s[0]['timestamp'][11:19]} .. {s[-1]['timestamp'][11:19]}")
    label = ch["response_times_by_label"][0]["label"]
    tx = cli.get(f"{API}/executions/{eid}/transaction-charts", params={"label": label}).json()
    rt = tx.get("response_times") or tx.get("series", {}).get("response_times")
    ok(rt[0]["timestamp"][11:13] == "17", f"transaccion {label}: primer punto {rt[0]['timestamp']}")
    h = cli.get(f"{API}/executions/{eid}/export/html").text
    ok("17:16:37 &rarr; 18:03:51" in h and not re.search(r"(?<![\d:])(22:16|23:03)", h) and not re.search(r"T2[23]:\d\d:\d\d", h), "HTML: cabecera 17:16:37 -> 18:03:51 y ningun 22:16 / 23:03")
    xs = re.findall(r'"x":\s*\[\s*"(2026-09-18T\d\d:\d\d:\d\d)', h)
    ok(xs and all(x[11:13] in ("17", "18") for x in xs), f"HTML: {len(xs)} trazas Plotly empiezan en hora de Colombia ({sorted(set(x[11:16] for x in xs))[:3]})")
    pdf = cli.get(f"{API}/executions/{eid}/export/pdf").content
    open("/tmp/146_sodexo.pdf", "wb").write(pdf)
    ok(pdf[:4] == b"%PDF", f"PDF generado ({len(pdf)} bytes) -> /tmp/146_sodexo.pdf")
cur.execute("select start_time from test_executions where id=%s", (eid,))
ok(str(cur.fetchone()[0]) == str(st_db), "la base no cambio")
print("\nTODO PASA" if not fallos else f"\n{len(fallos)} FALLA(N)")
sys.exit(1 if fallos else 0)
