"""O2e.2a — la validacion de la ingesta, en proceso. Sin base, sin red, sin API.

    docker exec jmeter_backend python3 /app/pruebas_e2e/o2e2a_ingesta.py

No escribe nada en ningun sitio: solo llama a funciones puras de
`services/observabilidad/ingesta.py` y compila el DDL de `ingest_tokens` sin
ejecutarlo.

A. El token: prefijo, largo, huella estable y distinta, prefijo visible.
B. La etiqueta `cliente` en lineas reales del agente, con escapes.
C. El lote: aceptado, rechazado entero, y el motivo con recuentos.
D. El cuerpo: gzip, tope DESPUES de descomprimir (bomba), 413 frente a 400.
E. El limitador: 300 por minuto, Retry-After, ventana deslizante, por token.
F. El modelo: el DDL que generaria `create_all`.
"""
import gzip
import sys

sys.path.insert(0, "/app")

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.models.ingest_token import IngestToken
from app.services.observabilidad import ingesta as I

fallos = []


def comprobar(nombre, condicion, detalle=""):
    print(("  ok   " if condicion else "  FALLA ") + nombre
          + ("" if condicion else f"  -> {detalle}"))
    if not condicion:
        fallos.append(nombre)


# ---------------------------------------------------------------------------
print("A. El token")
t1, t2 = I.generar_token(), I.generar_token()
comprobar("empieza por kxi_", t1.startswith("kxi_"), t1[:6])
comprobar("256 bits: 43 caracteres tras el prefijo", len(t1) == 4 + 43, len(t1))
comprobar("dos tokens distintos", t1 != t2)
comprobar("huella estable", I.huella(t1) == I.huella(t1))
comprobar("huella de 64 hex", len(I.huella(t1)) == 64
          and all(c in "0123456789abcdef" for c in I.huella(t1)))
comprobar("huellas distintas", I.huella(t1) != I.huella(t2))
comprobar("la huella no contiene el token", t1 not in I.huella(t1))
comprobar("prefijo visible de 12", I.prefijo_visible(t1) == t1[:12])

# ---------------------------------------------------------------------------
print("B. La etiqueta cliente")
casos = [
    # Lo que manda el agente de O2b, tal cual.
    ('cpu,cpu=cpu-total,cliente=laboratorio,host=lab_servidor,modo=agente '
     'usage_idle=97.5 1790000000000000000', "laboratorio"),
    # Un nombre con espacio y coma, escapado por Telegraf.
    (r'mem,cliente=Banco\ X\,\ S.A.,host=srv1 used=1i 1790000000000000000',
     "Banco X, S.A."),
    # Un igual dentro del valor.
    (r'mem,cliente=a\=b,host=srv1 used=1i', "a=b"),
    # Una barra delante de otra cosa se queda como esta.
    (r'disk,device=C:\x,cliente=acme,host=w1 free=1i', "acme"),
    # Pero una barra AL FINAL de una etiqueta se come la coma que la sigue:
    # es la leccion de O2a, e InfluxDB lo lee igual. `cliente` queda dentro
    # del valor de `device`, la linea no es de nadie y el lote se rechaza.
    (r'disk,device=C:\,cliente=acme,host=w1 free=1i', None),
    # La medida con espacio escapado no corta la cabecera.
    (r'mi\ medida,cliente=acme used=1i', "acme"),
    # `cliente` en un CAMPO no es la etiqueta.
    ('cpu,host=x cliente="acme",usage=1', None),
    # Sin etiquetas.
    ('cpu usage=1', None),
    # Otra etiqueta que empieza igual.
    ('cpu,clientes=acme usage=1', None),
]
for linea, esperado in casos:
    obtenido = I.cliente_de_linea(linea)
    comprobar(f"{linea[:48]!r} -> {esperado!r}", obtenido == esperado, obtenido)

# ---------------------------------------------------------------------------
print("C. El lote")
bueno = "\n".join([
    "cpu,cliente=acme,host=a usage=1 1",
    "",
    "# un comentario no cuenta",
    "mem,cliente=acme,host=a used=2i 1",
    "disk,cliente=acme,host=b free=3i 1",
])
r = I.revisar_lote(bueno, "acme")
comprobar("lote bueno aceptado", r.aceptado, r)
comprobar("3 puntos (sin vacias ni comentarios)", r.puntos == 3, r.puntos)

malo = "\n".join([
    "cpu,cliente=acme,host=a usage=1",
    "cpu,cliente=otro,host=a usage=1",
    "cpu,cliente=otro,host=b usage=1",
    "cpu,cliente=otro,host=c usage=1",
    "cpu,host=a usage=1",
    "cpu,host=b usage=1",
])
r = I.revisar_lote(malo, "acme")
comprobar("una sola linea ajena rechaza el lote", not r.aceptado)
comprobar("recuento por cliente",
          r.ajenas == {"otro": 3, None: 2}, dict(r.ajenas))
m = r.motivo("acme")
print("      motivo:", m)
comprobar("el motivo dice cuantas y de quién",
          "5 de 6 lineas" in m and "3 lineas con cliente=«otro»" in m
          and "2 lineas sin la etiqueta cliente" in m and "«acme»" in m, m)
comprobar("el motivo dice que no se escribio nada", "No se ha escrito nada" in m)
comprobar("una sola: singular",
          "1 linea con cliente=«x»" in I.revisar_lote("c,cliente=x v=1", "acme").motivo("acme"))
comprobar("mayusculas cuentan: Acme no es acme",
          not I.revisar_lote("c,cliente=Acme v=1", "acme").aceptado)
vacio = I.revisar_lote("\n\n", "acme")
comprobar("lote vacio no se acepta", not vacio.aceptado and "ninguna" in vacio.motivo("acme"))

# ---------------------------------------------------------------------------
print("D. El cuerpo")
texto = bueno.encode()
comprobar("sin codificacion: tal cual", I.descomprimir(texto, None) == texto)
comprobar("identity: tal cual", I.descomprimir(texto, "identity") == texto)
comprobar("gzip: descomprime", I.descomprimir(gzip.compress(texto), "gzip") == texto)
comprobar("GZIP en mayusculas", I.descomprimir(gzip.compress(texto), "GZIP") == texto)


def lanza(clase, *args, **kw):
    try:
        I.descomprimir(*args, **kw)
    except clase:
        return True
    except Exception as exc:   # noqa: BLE001
        print("      lanzo otra cosa:", type(exc).__name__, exc)
    return False


# 20 MB de ceros caben en ~20 KB de gzip: el tope tiene que saltar DESPUES.
bomba = gzip.compress(b"0" * (20 * 1024 * 1024))
comprobar(f"bomba de {len(bomba)} bytes comprimidos -> 413",
          len(bomba) < I.TOPE_BYTES and lanza(I.CuerpoDemasiadoGrande, bomba, "gzip"))
justo = b"x" * I.TOPE_BYTES
comprobar("exactamente 1 MB descomprimido: entra",
          I.descomprimir(gzip.compress(justo), "gzip") == justo)
comprobar("1 MB + 1 descomprimido -> 413",
          lanza(I.CuerpoDemasiadoGrande, gzip.compress(justo + b"x"), "gzip"))
comprobar("1 MB + 1 sin comprimir -> 413",
          lanza(I.CuerpoDemasiadoGrande, justo + b"x", None))
comprobar("gzip roto -> 400", lanza(I.CuerpoInvalido, b"no es gzip", "gzip"))
comprobar("gzip cortado -> 400",
          lanza(I.CuerpoInvalido, gzip.compress(texto)[:-6], "gzip"))
comprobar("deflate no se acepta -> 400", lanza(I.CuerpoInvalido, texto, "deflate"))

# ---------------------------------------------------------------------------
print("E. El limitador")
ahora = [1000.0]
lim = I.Limitador(reloj=lambda: ahora[0])
admitidas = sum(lim.admitir("k")[0] for _ in range(300))
comprobar("300 en el mismo minuto: todas entran", admitidas == 300, admitidas)
ok, espera = lim.admitir("k")
comprobar("la 301 no entra", not ok)
comprobar("Retry-After de 60 s si todas son de ahora", espera == 60, espera)
comprobar("otro token no se ve afectado", lim.admitir("otra")[0])
ahora[0] += 45
ok, espera = lim.admitir("k")
comprobar("a los 45 s: sigue sin entrar, faltan 15", not ok and espera == 15, (ok, espera))
ahora[0] += 15
comprobar("a los 60 s: vuelve a entrar", lim.admitir("k")[0])

# Ventana deslizante: cada agente, 12 por minuto. 20 con el mismo token son
# 240 por minuto durante 10 minutos: ningun 429. 30 son 360: tiene que frenar.
for agentes, deben_rechazarse in ((20, False), (30, True)):
    ahora = [0.0]
    lim = I.Limitador(reloj=lambda: ahora[0])
    rechazos = 0
    for _ in range(10 * 12 * agentes):
        ahora[0] += 5.0 / agentes
        rechazos += not lim.admitir("cliente")[0]
    comprobar(f"{agentes} agentes con un token durante 10 min: "
              f"{'hay' if deben_rechazarse else 'ningun'} 429",
              (rechazos > 0) == deben_rechazarse, rechazos)

ahora = [0.0]
lim = I.Limitador(reloj=lambda: ahora[0])
for n in range(1500):
    lim.admitir(f"t{n}")
ahora[0] += 120
lim.admitir("nuevo")
comprobar("los tokens callados se olvidan", len(lim._marcas) == 1, len(lim._marcas))

# ---------------------------------------------------------------------------
print("F. El modelo")
ddl = str(CreateTable(IngestToken.__table__).compile(dialect=postgresql.dialect()))
print("      " + ddl.strip().replace("\n", "\n      "))
comprobar("tabla ingest_tokens", "CREATE TABLE ingest_tokens" in ddl)
comprobar("huella unica", "UNIQUE (huella)" in ddl, ddl)
comprobar("sin columna token", "\ttoken " not in ddl and " token " not in ddl)
comprobar("FK a clients con CASCADE", "REFERENCES clients (id) ON DELETE CASCADE" in ddl)

print()
print("RESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
