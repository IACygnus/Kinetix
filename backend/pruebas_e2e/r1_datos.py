"""ETAPA R1 — los datos de prueba del informe integrado, en la base de PRUEBAS.

    docker exec jmeter_backend python3 /app/pruebas_e2e/r1_datos.py

Idempotente: lo que ya existe (por nombre, siempre con ZZTEST-) se reutiliza.
Escribe SOLO en `jmeter_analyzer_test` (regla 34) y se para si la base de destino
no lleva `test` en el nombre. De la base de Fredy solo LEE una ejecucion de
referencia para copiar sus cifras y sus textos por transaccion (SELECT).

Lo que deja:
  - ZZTEST-R1 carga   (load)   con 3 transacciones con informe y 2 capturas
  - ZZTEST-R1 estres  (stress) sin transacciones con informe
  - ZZTEST-R1 integrado: [carga, monitoreo de carga, estres]

El JTL y las imagenes se COPIAN con nombre propio: ningun registro de pruebas
apunta a un archivo de Fredy, asi que borrar algo de pruebas nunca puede
arrastrar un archivo suyo.
"""
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

PG = dict(host="postgres", user="jmeter_user", password="jmeter_secure_2024")
DB_FREDY = "jmeter_analyzer_db"
DB_TEST = os.environ.get("KX_DB", "jmeter_analyzer_test")
FUENTE = "959a2f05-7851-4683-a969-742aaa2c2634"          # 'prueba 2', 3 transacciones con informe
IMAGENES = [  # capturas pequeñas de la ejecucion 35ca5b92 (solo se copian)
    "/app/media/attachments/35ca5b92-dd0c-4fd5-abfd-f792ef695275/79c57cb9-06f4-4ef2-b115-494448161e48.png",
    "/app/media/attachments/35ca5b92-dd0c-4fd5-abfd-f792ef695275/577a7fba-0bd0-40b2-9c6c-218cd5be192e.png",
]
UPLOADS = "/app/uploads"
CLIENTE = "ZZTEST-R1"
INTEGRADO = "ZZTEST-R1 integrado"

if "test" not in DB_TEST:
    sys.exit(f"PARADA: la base de destino '{DB_TEST}' no lleva 'test' en el nombre. No se escribe nada.")


def conectar(db):
    c = psycopg2.connect(dbname=db, **PG)
    c.autocommit = False
    return c


def main():
    fredy = conectar(DB_FREDY)
    fredy.set_session(readonly=True)
    fc = fredy.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    fc.execute("select * from test_executions where id=%s", (FUENTE,))
    fuente = fc.fetchone()
    fc.execute("select label, section, ai_analysis, sort_order from transaction_chart_analyses "
               "where execution_id=%s", (FUENTE,))
    tx = fc.fetchall()
    fredy.close()
    if not fuente:
        sys.exit("No existe la ejecucion de referencia")

    t = conectar(DB_TEST)
    tc = t.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    tc.execute("select current_database() db")
    assert "test" in tc.fetchone()["db"]

    tc.execute("select id from users where username='admin'")
    admin = tc.fetchone()["id"]

    tc.execute("select id from clients where name=%s", (CLIENTE,))
    fila = tc.fetchone()
    if fila:
        cliente = fila["id"]
    else:
        cliente = str(uuid.uuid4())
        # Con fechas: el modelo las pone en Python (`default=datetime.utcnow`),
        # no en la base, asi que un INSERT a mano las dejaba en NULL y
        # `GET /clients` fallaba entero con un 500 de validacion (reporte 129).
        tc.execute("insert into clients (id, name, description, is_active, created_at, updated_at) "
                   "values (%s,%s,%s,true,now(),now())",
                   (cliente, CLIENTE, "ZZTEST: datos de la etapa R1"))

    tc.execute("select column_name from information_schema.columns where table_name='test_executions'")
    cols_test = {r["column_name"] for r in tc.fetchall()}

    ids = {}
    for nombre, tipo, jtl in (("ZZTEST-R1 carga", "load", "ZZTEST-R1_carga.jtl"),
                              ("ZZTEST-R1 estres", "stress", "ZZTEST-R1_estres.jtl")):
        destino = os.path.join(UPLOADS, jtl)
        if not os.path.exists(destino):
            origen = [f for f in os.listdir(UPLOADS) if f.endswith(fuente["jtl_filename"])][0]
            shutil.copyfile(os.path.join(UPLOADS, origen), destino)
        tc.execute("select id from test_executions where name=%s", (nombre,))
        fila = tc.fetchone()
        if fila:
            ids[tipo] = str(fila["id"])
            continue
        nuevo = dict(fuente)
        nuevo.update(id=str(uuid.uuid4()), name=nombre, project=nombre, test_type=tipo,
                     user_id=admin, client_id=cliente, client=CLIENTE,
                     description="ZZTEST: etapa R1", jtl_filename=jtl, jtl_filenames=None)
        # Las fechas de alta son las de HOY: el modelo no les da valor por defecto
        # en la base y la API responde 500 si llegan vacias.
        ahora = datetime.now(timezone.utc)
        nuevo.update(created_at=ahora, updated_at=ahora)
        nuevo = {k: v for k, v in nuevo.items() if k in cols_test}
        for k, v in list(nuevo.items()):
            if isinstance(v, (dict, list)):
                nuevo[k] = json.dumps(v)
        tc.execute(f"insert into test_executions ({','.join(nuevo)}) values ({','.join(['%s'] * len(nuevo))})",
                   list(nuevo.values()))
        ids[tipo] = nuevo["id"]
    carga, estres = ids["load"], ids["stress"]
    # Una siembra anterior de esta misma suite las dejo sin fecha: se completa.
    tc.execute("update test_executions set created_at=coalesce(created_at, now()), "
               "updated_at=coalesce(updated_at, now()) where id in (%s,%s)", (carga, estres))

    tc.execute("select count(*) n from transaction_chart_analyses where execution_id=%s", (carga,))
    if tc.fetchone()["n"] == 0:
        for r in tx:
            tc.execute("insert into transaction_chart_analyses (id, execution_id, label, section, ai_analysis, "
                       "generated_at, is_edited, sort_order, created_at) values (%s,%s,%s,%s,%s,now(),false,%s,now())",
                       (str(uuid.uuid4()), carga, r["label"], r["section"], r["ai_analysis"], r["sort_order"]))

    tc.execute("select count(*) n from execution_attachments where execution_id=%s", (carga,))
    if tc.fetchone()["n"] == 0:
        carpeta = f"/app/media/attachments/{carga}"
        os.makedirs(carpeta, exist_ok=True)
        for i, img in enumerate(IMAGENES, 1):
            aid = str(uuid.uuid4())
            nombre = f"{aid}.png"
            shutil.copyfile(img, os.path.join(carpeta, nombre))
            tc.execute("insert into execution_attachments (id, execution_id, attachment_type, title, description, "
                       "category, filename, filepath, file_type, file_size, sort_order, ai_analysis, created_at) "
                       "values (%s,%s,'monitoring',%s,%s,'cpu',%s,%s,'image/png',%s,%s,%s,now())",
                       (aid, carga, f"ZZTEST captura {i}", "ZZTEST", nombre,
                        f"/media/attachments/{carga}/{nombre}", os.path.getsize(img), i,
                        f"ZZTEST analisis original de la captura {i}."))

    # R1.2: una evidencia, para cubrir tambien esa rama del selector.
    tc.execute("select count(*) n from execution_attachments where execution_id=%s "
               "and attachment_type='evidence'", (carga,))
    if tc.fetchone()["n"] == 0:
        carpeta = f"/app/media/attachments/{carga}"
        os.makedirs(carpeta, exist_ok=True)
        aid = str(uuid.uuid4())
        nombre = f"{aid}.png"
        shutil.copyfile(IMAGENES[0], os.path.join(carpeta, nombre))
        tc.execute("insert into execution_attachments (id, execution_id, attachment_type, title, description, "
                   "category, filename, filepath, file_type, file_size, sort_order, ai_analysis, created_at) "
                   "values (%s,%s,'evidence','ZZTEST evidencia 1','ZZTEST','log',%s,%s,'image/png',%s,1,%s,now())",
                   (aid, carga, nombre, f"/media/attachments/{carga}/{nombre}", os.path.getsize(IMAGENES[0]),
                    "ZZTEST analisis original de la evidencia 1."))

    # R1.2 (opcion (a)): un integrado con SOLO la seccion de carga. Antes pintaba
    # dentro las capturas de esa ejecucion; ahora no debe pintar ninguna.
    tc.execute("select id from integrated_reports where name='ZZTEST-R1 solo carga'")
    if not tc.fetchone():
        tc.execute("insert into integrated_reports (id, name, sections, consolidated_analysis, created_by, "
                   "created_at, updated_at) values (%s,'ZZTEST-R1 solo carga',%s,'{}',%s,now(),now())",
                   (str(uuid.uuid4()), json.dumps([{"order": 0, "type": "load_test", "source_id": carga,
                                                    "source_name": "ZZTEST-R1 carga"}]), admin))

    # R1.2: el integrado del selector, con las cuatro clases de seccion.
    tc.execute("select id from integrated_reports where name='ZZTEST-R1 seleccion'")
    if not tc.fetchone():
        tc.execute("insert into integrated_reports (id, name, sections, consolidated_analysis, created_by, "
                   "created_at, updated_at) values (%s,'ZZTEST-R1 seleccion',%s,'{}',%s,now(),now())",
                   (str(uuid.uuid4()), json.dumps([
                       {"order": 0, "type": "load_test", "source_id": carga, "source_name": "ZZTEST-R1 carga"},
                       {"order": 1, "type": "monitoring", "source_id": carga, "source_name": "Monitoreo: ZZTEST-R1 carga"},
                       {"order": 2, "type": "evidence", "source_id": carga, "source_name": "Evidencias: ZZTEST-R1 carga"},
                       {"order": 3, "type": "stress_test", "source_id": estres, "source_name": "ZZTEST-R1 estres"},
                   ]), admin))

    tc.execute("select id from integrated_reports where name=%s", (INTEGRADO,))
    fila = tc.fetchone()
    secciones = [
        {"order": 0, "type": "load_test", "source_id": carga, "source_name": "ZZTEST-R1 carga"},
        {"order": 1, "type": "monitoring", "source_id": carga, "source_name": "Monitoreo: ZZTEST-R1 carga"},
        {"order": 2, "type": "stress_test", "source_id": estres, "source_name": "ZZTEST-R1 estres"},
    ]
    if fila:
        rid = str(fila["id"])
    else:
        rid = str(uuid.uuid4())
        tc.execute("insert into integrated_reports (id, name, sections, consolidated_analysis, created_by, "
                   "created_at, updated_at) values (%s,%s,%s,%s,%s,now(),now())",
                   (rid, INTEGRADO, json.dumps(secciones),
                    json.dumps({"load": {"conclusions": "ZZTEST conclusiones de carga.",
                                         "recommendations": "ZZTEST recomendaciones de carga.",
                                         "generated_at": None, "edited": False}}), admin))
    t.commit()
    t.close()
    print(json.dumps({"carga": carga, "estres": estres, "integrado": rid, "admin": str(admin)}))


if __name__ == "__main__":
    main()
