"""La aplicacion del servidor de laboratorio (O-D9).

Biblioteca estandar y `psycopg2` del paquete de Ubuntu: ni un `pip install`, ni
una dependencia nueva en Kinetix. Cuatro endpoints, y uno de ellos cuesta de
verdad —esa es toda la gracia—:

    GET  /salud            no toca la base. Para el arranque y el semaforo
    GET  /productos        consulta por indice. Barata
    POST /pedidos          una insercion. Escribe, para que haya transacciones
    GET  /buscar?q=...     recorre las 200.000 filas. Esta es la que duele
"""
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from psycopg2 import pool

PUERTO = int(os.environ.get("LAB_APP_PUERTO", "8080"))
DSN = os.environ.get("LAB_APP_DSN", "")
MAX_CUERPO = 64 * 1024

# Un pozo de conexiones: abrir una conexion por peticion mediria el coste de
# conectarse, no el de la consulta.
_pozo = pool.ThreadedConnectionPool(2, 24, DSN)


class _Conexion:
    """`with _Conexion() as cur:` — devuelve la conexion al pozo pase lo que pase."""

    def __enter__(self):
        self.con = _pozo.getconn()
        self.cur = self.con.cursor()
        return self.cur

    def __exit__(self, tipo, valor, traza):
        try:
            if tipo is None:
                self.con.commit()
            else:
                self.con.rollback()
        finally:
            self.cur.close()
            _pozo.putconn(self.con)
        return False


def _productos(parametros):
    categoria = (parametros.get("categoria") or [""])[0]
    limite = min(int((parametros.get("limite") or ["20"])[0] or 20), 200)
    with _Conexion() as cur:
        if categoria:
            cur.execute(
                "SELECT id, sku, nombre, categoria, precio, existencias "
                "FROM productos WHERE categoria = %s ORDER BY id LIMIT %s",
                (categoria, limite))
        else:
            cur.execute(
                "SELECT id, sku, nombre, categoria, precio, existencias "
                "FROM productos ORDER BY id LIMIT %s", (limite,))
        filas = cur.fetchall()
    return {"total": len(filas), "productos": [
        {"id": f[0], "sku": f[1], "nombre": f[2], "categoria": f[3],
         "precio": float(f[4]), "existencias": f[5]} for f in filas]}


def _buscar(parametros):
    """La consulta cara: `descripcion` no tiene indice, asi que hay recorrido."""
    termino = (parametros.get("q") or ["a1"])[0]
    # Sin indice de texto, pero tampoco se le da al usuario un comodin libre.
    termino = re.sub(r"[^A-Za-z0-9 ]", "", termino)[:40] or "a1"
    with _Conexion() as cur:
        cur.execute(
            "SELECT p.categoria, count(*) AS cuantos, round(avg(p.precio), 2) AS medio, "
            "       sum(p.existencias) AS existencias "
            "FROM productos p "
            "WHERE p.descripcion ILIKE %s "
            "GROUP BY p.categoria ORDER BY cuantos DESC",
            ("%" + termino + "%",))
        filas = cur.fetchall()
    return {"termino": termino, "grupos": [
        {"categoria": f[0], "cuantos": f[1], "precio_medio": float(f[2] or 0),
         "existencias": int(f[3] or 0)} for f in filas]}


def _pedido(cuerpo):
    datos = json.loads(cuerpo or b"{}")
    producto_id = int(datos.get("producto_id") or 1)
    cantidad = max(1, min(int(datos.get("cantidad") or 1), 99))
    cliente = str(datos.get("cliente") or "anonimo")[:60]
    with _Conexion() as cur:
        cur.execute(
            "INSERT INTO pedidos (producto_id, cantidad, cliente) "
            "VALUES (%s, %s, %s) RETURNING id, creado_en",
            (producto_id, cantidad, cliente))
        fila = cur.fetchone()
    return {"id": fila[0], "creado_en": fila[1].isoformat()}


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LabTienda/1.0"

    def log_message(self, formato, *args):
        sys.stderr.write(self.address_string() + " " + (formato % args) + "\n")

    def _responder(self, codigo, cuerpo):
        crudo = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(crudo)))
        self.end_headers()
        self.wfile.write(crudo)

    def do_GET(self):
        ruta = urlparse(self.path)
        parametros = parse_qs(ruta.query)
        try:
            if ruta.path == "/salud":
                self._responder(200, {"estado": "ok"})
            elif ruta.path == "/productos":
                self._responder(200, _productos(parametros))
            elif ruta.path == "/buscar":
                self._responder(200, _buscar(parametros))
            else:
                self._responder(404, {"error": "no existe esa ruta"})
        except Exception as exc:  # que un fallo no tumbe el hilo del servidor
            self._responder(500, {"error": str(exc)})

    def do_POST(self):
        ruta = urlparse(self.path)
        try:
            largo = min(int(self.headers.get("Content-Length") or 0), MAX_CUERPO)
            cuerpo = self.rfile.read(largo) if largo else b"{}"
            if ruta.path == "/pedidos":
                self._responder(201, _pedido(cuerpo))
            else:
                self._responder(404, {"error": "no existe esa ruta"})
        except Exception as exc:
            self._responder(500, {"error": str(exc)})


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador)
    servidor.daemon_threads = True
    sys.stderr.write("tienda escuchando en 0.0.0.0:" + str(PUERTO) + "\n")
    servidor.serve_forever()
