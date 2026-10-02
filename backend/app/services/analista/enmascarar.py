"""El enmascarado de los datos sensibles — BLOQUE 5, parte B.7 (ampliado en el 150).

Se aplica ANTES de guardar un ejemplo y antes de cualquier prompt. Es
deliberadamente generoso: tapar de más un número que no era un documento cuesta
poco; dejar a la vista un token cuesta mucho.

Lo que tapa:
  - cabeceras Authorization, Proxy-Authorization, Cookie, Set-Cookie y las de
    claves de API, y el bloque «Cookie Data» que JMeter escribe en samplerData;
  - cualquier Bearer/Basic/Digest y cualquier JWT (eyJ….….…);
  - el valor de cualquier campo cuyo NOMBRE contenga token, password, secret,
    key, doc, account, login, user, customer o name (y clave, contraseña,
    session…), en JSON, en XML y en formularios o URL;
  - cuerpos en base64 o cifrados: «[cuerpo cifrado, N caracteres]»;
  - IP (v4 y v6) y MAC;
  - números largos (tarjetas, documentos, cuentas) y correos.
"""
import re

OCULTO = "[oculto]"

# Lo que hace sensible a un campo por su NOMBRE (150: doc, account, login, user,
# customer y name, además de los de siempre).
_CLAVE = (r"(?:password|passwd|pwd|pass|secret|token|api[_-]?key|apikey|clave|contrase(?:ñ|n)a"
          r"|authorization|session[_-]?id|sessionid|jsessionid|access[_-]?key|private[_-]?key|credential"
          r"|key|doc|account|cuenta|login|user|usuario|customer|cliente|name|nombre)")
# El nombre entero de un campo que CONTIENE una de esas palabras: «documentNumber»,
# «customerId», «userName», «x-api-key»…
_CAMPO = r"[\w.-]*?" + _CLAVE + r"[\w.-]*?"
# Un bloque base64 o cifrado: 40 o más caracteres seguidos sin espacios, con
# mayúsculas, minúsculas y dígitos (un hash hexadecimal en minúsculas no entra).
_CIFRADO = re.compile(r"(?<![\w+/=-])(?=[A-Za-z0-9+/=_-]*[A-Z])(?=[A-Za-z0-9+/=_-]*[a-z])"
                      r"(?=[A-Za-z0-9+/=_-]*\d)[A-Za-z0-9+/_-]{40,}={0,2}(?![\w+/=-])")

_PATRONES = [
    (re.compile(r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key|x-auth-token"
                r"|api-key|x-access-token)\s*:\s*).*$"), r"\1" + OCULTO),
    (re.compile(r"(?is)(cookie data:\s*).*?(?=\n\s*\n|\Z)"), r"\1" + OCULTO),
    (re.compile(r"(?i)\b(bearer|basic|digest)\s+[A-Za-z0-9\-._~+/=]{2,}"), r"\1 " + OCULTO),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[jwt]"),
    # JSON: "algo_password": "valor" | "customerId": 123 | "documento": null
    (re.compile(r'(?i)("' + _CAMPO + r'"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d[\d.eE+-]*|true|false)'),
     r'\1"' + OCULTO + '"'),
    # XML: <password>valor</password>, <ns:userName>…</ns:userName>
    (re.compile(r"(?is)<((?:[\w.-]+:)?" + _CAMPO + r")(\s[^>]*)?>([^<]*)</\1>"), r"<\1\2>" + OCULTO + r"</\1>"),
    # formulario o query: password=valor&…
    (re.compile(r"(?i)\b(" + _CAMPO + r")=([^&\s\"'<>]+)"), r"\1=" + OCULTO),
]

_DESPUES = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[correo]"),
    # MAC antes que IPv6: una MAC con «:» también parece IPv6
    (re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "[mac]"),
    (re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){5,7}[0-9A-Fa-f]{1,4}(?![\w:])"
                r"|(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4})?(?![\w:])"), "[ip]"),
    (re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "[ip]"),
    (re.compile(r"\b\d(?:[ -]?\d){12,18}\b"), "[número]"),        # tarjetas, con o sin separadores
    (re.compile(r"\b\d{7,}\b"), "[número]"),                      # documentos, cuentas, números largos
]


def enmascarar(texto) -> str:
    if not texto:
        return ""
    t = str(texto)
    for patron, sustituto in _PATRONES:
        t = patron.sub(sustituto, t)
    t = _CIFRADO.sub(lambda m: f"[cuerpo cifrado, {len(m.group(0))} caracteres]", t)
    for patron, sustituto in _DESPUES:
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
