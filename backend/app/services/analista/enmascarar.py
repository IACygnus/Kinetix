"""El enmascarado de los datos sensibles — BLOQUE 5, parte B.7.

Se aplica ANTES de guardar un ejemplo y antes de cualquier prompt. Es
deliberadamente generoso: tapar de más un número que no era un documento cuesta
poco; dejar a la vista un token cuesta mucho.

Lo que tapa:
  - cabeceras Authorization, Proxy-Authorization, Cookie, Set-Cookie y las de
    claves de API, y el bloque «Cookie Data» que JMeter escribe en samplerData;
  - Bearer/Basic/Digest y cualquier JWT (eyJ….….…);
  - el valor de cualquier campo que se llame password, secret, token, key,
    clave, contraseña, session id… en JSON, en XML y en formularios o URL;
  - números largos (tarjetas, documentos, cuentas) y correos.
"""
import re

OCULTO = "[oculto]"

_CLAVE = (r"(?:password|passwd|pwd|pass|secret|token|api[_-]?key|apikey|clave|contrase(?:ñ|n)a"
          r"|authorization|session[_-]?id|sessionid|jsessionid|access[_-]?key|private[_-]?key|credential\w*|key)")

_PATRONES = [
    (re.compile(r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-auth-token"
                r"|api-key|x-access-token)\s*:\s*).*$"), r"\1" + OCULTO),
    (re.compile(r"(?is)(cookie data:\s*).*?(?=\n\s*\n|\Z)"), r"\1" + OCULTO),
    (re.compile(r"(?i)\b(bearer|basic|digest)\s+[A-Za-z0-9\-._~+/=]{6,}"), r"\1 " + OCULTO),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[jwt]"),
    # JSON: "algo_password": "valor" | "token": 123
    (re.compile(r'(?i)("[\w.-]*?' + _CLAVE + r'"\s*:\s*)("(?:[^"\\]|\\.)*"|[^,}\]\s]+)'), r'\1"' + OCULTO + '"'),
    # XML: <password>valor</password>, <ns:token>…</ns:token>
    (re.compile(r"(?is)<((?:[\w.-]+:)?[\w.-]*?" + _CLAVE + r")(\s[^>]*)?>(.*?)</\1>"), r"<\1\2>" + OCULTO + r"</\1>"),
    # formulario o query: password=valor&…
    (re.compile(r"(?i)\b([\w.-]*?" + _CLAVE + r")=([^&\s\"'<>]+)"), r"\1=" + OCULTO),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[correo]"),
    (re.compile(r"\b\d(?:[ -]?\d){12,18}\b"), "[número]"),        # tarjetas, con o sin separadores
    (re.compile(r"\b\d{7,}\b"), "[número]"),                      # documentos, cuentas, números largos
]


def enmascarar(texto) -> str:
    if not texto:
        return ""
    t = str(texto)
    for patron, sustituto in _PATRONES:
        t = patron.sub(sustituto, t)
    return t


def recortar(texto: str, tope: int) -> str:
    t = re.sub(r"[ \t]+", " ", texto or "").strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t if len(t) <= tope else t[:tope - 1].rstrip() + "…"


def seguro(texto, tope: int) -> str:
    """Enmascarar y LUEGO recortar: recortar antes podría partir un token por la
    mitad y dejar su primera parte sin reconocer."""
    return recortar(enmascarar(texto), tope)
