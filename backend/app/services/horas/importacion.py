"""El lector del archivo de horas (ETAPA H3.4, especificación §6.1).

Dos mitades, separadas a propósito:

  1. **Interpretar un valor** —una fecha, unas horas, un «Sí»— son funciones puras
     que reciben lo que venga y devuelven un dato o `None`. No saben qué es Excel.
  2. **Abrir el libro** es lo único que necesita `openpyxl`, y lo importa dentro
     de la función, no arriba.

La separación no es estética: las reglas de H-D42 a H-D46 son las que se rompen
en silencio cuando el archivo cambia de origen, y así se prueban una a una sin
tener que fabricar un `.xlsx` en cada test.

Todo lo que este módulo decide viene medido contra el archivo real de la
herramienta de horas de Fredy, no supuesto:

  - los títulos traen espacio final (`"Cliente "`), así que **se comparan
    normalizados** con `normalizar()` de H1 — la misma función que evita duplicar
    un cliente por una tilde (H-D42);
  - las fechas son texto `dd/mm/aaaa` (H-D43);
  - las horas son número, con decimales (H-D44);
  - `Facturable` y `Extra Hour` vienen como `Si`/`No` (H-D45);
  - las observaciones traen saltos de línea y espacios finos U+202F (H-D46).
"""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from app.db.models.time_tracking import normalizar

# ===================== LAS COLUMNAS (§6.1) =====================

# clave interna -> título tal como se lee en el archivo. La comparación es
# normalizada (H-D42), así que el espacio final de «Cliente » no estorba.
COLUMNAS: Dict[str, str] = {
    "external_id": "Id",
    "notas": "Observaciones",
    "cliente": "Cliente",
    "proyecto": "Proyecto",
    "actividad": "Tarea",
    "tipo_hora": "Tipo de hora",        # §6.1: se ignora
    "subtipo_hora": "Sub Tipo Hora",    # §6.1: se ignora
    "extra": "Extra Hour",
    "fecha": "Fecha",
    "horas": "Tiempo total",
    "facturable": "Facturable",
}

# Sin estas cinco no hay registro que construir.
#
# `Facturable` entra en la lista aunque una celda vacía cuente como «no»
# (H-D45): que falte **la columna entera** es otra cosa — importaría un mes
# completo como no facturable sin que nadie lo hubiera decidido, y eso es dinero.
# `Extra Hour`, `Id` y `Observaciones` sí son opcionales: su ausencia tiene un
# valor por defecto que no engaña a nadie.
OBLIGATORIAS = ("cliente", "proyecto", "actividad", "fecha", "horas", "facturable")

# §6.1: estas dos se leen y se tiran, para que quede dicho en el código.
IGNORADAS = ("tipo_hora", "subtipo_hora")


class FaltanColumnas(Exception):
    """El archivo no sirve: se avisa antes de leer ni una fila (H-D42)."""

    def __init__(self, faltan: List[str]):
        self.faltan = faltan
        super().__init__(
            "Al archivo le faltan columnas obligatorias: "
            + ", ".join(f"«{f}»" for f in faltan)
        )


def mapear_columnas(titulos: List[Any]) -> Dict[str, int]:
    """De la fila de títulos a `{clave: posición}`.

    Compara normalizado (H-D42). Si falta una obligatoria, se para aquí con el
    nombre de la que falta: leer 500 filas para descubrirlo al final no ayuda a
    nadie.
    """
    vistos = {normalizar(t): i for i, t in enumerate(titulos) if t is not None and str(t).strip()}
    mapa = {clave: vistos[normalizar(titulo)]
            for clave, titulo in COLUMNAS.items()
            if normalizar(titulo) in vistos}
    faltan = [COLUMNAS[c] for c in OBLIGATORIAS if c not in mapa]
    if faltan:
        raise FaltanColumnas(faltan)
    return mapa


# ===================== LOS VALORES =====================

# Excel cuenta los días desde el 31/12/1899 y además cree que 1900 fue bisiesto,
# así que los 60 primeros números de serie están corridos un día. No se aceptan:
# ninguna hora de trabajo se registra en enero de 1900, y adivinar ahí sería
# inventarse un dato.
_ORIGEN_EXCEL = date(1899, 12, 30)
_SERIE_MINIMA = 61

_FECHA_DDMMAAAA = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")
_FECHA_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def leer_fecha(valor: Any) -> Optional[date]:
    """La fecha de la fila (H-D43).

    Acepta, en este orden: lo que ya venga como fecha, `dd/mm/aaaa`,
    `aaaa-mm-dd` y el número de serie de Excel. Cualquier otra cosa devuelve
    `None`, y la fila se marca inválida con su motivo (H-D40).
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        serie = int(valor)
        if serie < _SERIE_MINIMA:
            return None
        return _ORIGEN_EXCEL + timedelta(days=serie)

    texto = str(valor).strip()
    # Una fecha con hora pegada: «15/09/2026 00:00:00».
    texto = texto.split(" ")[0] if " " in texto else texto

    m = _FECHA_DDMMAAAA.match(texto)
    if m:
        d, mes, a = (int(x) for x in m.groups())
        return _fecha_o_none(a, mes, d)
    m = _FECHA_ISO.match(texto)
    if m:
        a, mes, d = (int(x) for x in m.groups())
        return _fecha_o_none(a, mes, d)
    # Un número guardado como texto: «45915».
    if texto.isdigit():
        serie = int(texto)
        return _ORIGEN_EXCEL + timedelta(days=serie) if serie >= _SERIE_MINIMA else None
    return None


def _fecha_o_none(a: int, m: int, d: int) -> Optional[date]:
    """El 31 de febrero no existe, y `date()` lo dice con una excepción."""
    try:
        return date(a, m, d)
    except ValueError:
        return None


def leer_horas(valor: Any) -> Optional[Decimal]:
    """Las horas de la fila (H-D44).

    Número o texto, con punto o con coma. Devuelve `None` si no se entiende; el
    paso de 0,25 y el «mayor que cero» los comprueba `validar_paso()`, que ya
    tiene el mensaje en español.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return None
    # «8,5» es lo normal aquí; «1.234,5» no aparece en horas, pero si apareciera
    # el punto sería de millares.
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


_SI = {"si", "s", "sí", "true", "verdadero", "x", "1", "yes", "y"}
_NO = {"no", "n", "false", "falso", "0", ""}


def leer_si_no(valor: Any) -> bool:
    """`Facturable` y `Extra Hour` (H-D45).

    Lo que no se reconoce cuenta como **no**: en horas facturables, el que no lo
    dice claramente no se cobra.
    """
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor != 0
    return normalizar(str(valor)) in _SI


# Espacios que no son el espacio de siempre y que Excel cuela sin avisar: el fino
# sin salto (U+202F), el duro (U+00A0), el fino (U+2009) y el de tabla (U+2007).
_ESPACIOS_RAROS = dict.fromkeys(map(ord, "    ​"), " ")


def limpiar_texto(valor: Any) -> str:
    """Las observaciones, en una sola línea (H-D46).

    Los saltos de línea y los espacios especiales se cambian por espacios
    normales y se colapsan. **Nunca invalida la fila**: un comentario raro no es
    motivo para perder unas horas de trabajo.
    """
    if valor is None:
        return ""
    texto = str(valor).translate(_ESPACIOS_RAROS)
    return " ".join(texto.split())


def leer_id(valor: Any) -> str:
    """El `Id` del archivo, que va a `external_id` (H-D35).

    Puede venir como número o como texto; se guarda siempre como texto, y un
    `1234.0` de Excel se queda en `1234` para que no haya dos formas de escribir
    el mismo identificador.
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, int):
        return str(valor)
    return str(valor).strip()


# ===================== EL LIBRO =====================

# Un mes de una persona son ~25 filas; un año de todo el equipo, unas 3.000. El
# tope deja sitio de sobra y corta un archivo equivocado antes de que ocupe la
# memoria del contenedor.
MAX_BYTES = 5 * 1024 * 1024
MAX_FILAS = 20_000


class ArchivoIlegible(Exception):
    """No es un `.xlsx` que se pueda abrir."""


def filas_del_libro(datos: bytes) -> Tuple[str, List[str], List[Tuple[int, List[Any]]]]:
    """Abre el `.xlsx` y devuelve `(hoja, títulos, [(nº de fila, valores)])`.

    El número es **el del archivo**, empezando en 1 por la fila de títulos, para
    que un aviso diga «fila 14» y Fredy pueda ir a mirarla (H-D40). Por eso las
    filas vacías se saltan sin renumerar las siguientes.

    **La primera hoja del libro** (H-D47): el archivo de horas trae una sola, y
    si algún día trae más, la vista previa dice cuál se usó en vez de elegir por
    su cuenta y callarse.

    `openpyxl` se importa aquí dentro y no arriba: así el resto del módulo —que
    es donde están las reglas— se puede probar sin depender de la librería.
    """
    if len(datos) > MAX_BYTES:
        raise ArchivoIlegible(
            f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB. "
            "¿Seguro que es el archivo de horas?")
    try:
        import io
        from openpyxl import load_workbook
    except ImportError as e:      # pragma: no cover - depende del contenedor
        raise ArchivoIlegible(
            "Falta el lector de Excel en el servidor (openpyxl). "
            "Hay que reconstruir el backend.") from e

    try:
        # `data_only`: de una celda con fórmula se quiere el número, no la fórmula.
        # `read_only`: recorre el archivo en streaming, sin cargarlo entero.
        libro = load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
    except Exception as e:
        raise ArchivoIlegible(
            "No se pudo abrir el archivo. Tiene que ser un Excel .xlsx.") from e

    try:
        hoja = libro.worksheets[0]
        filas: List[Tuple[int, List[Any]]] = []
        titulos: List[str] = []
        for i, fila in enumerate(hoja.iter_rows(values_only=True), start=1):
            if i == 1:
                titulos = list(fila)
                continue
            if len(filas) >= MAX_FILAS:
                break
            # Una fila entera vacía no es un error: se salta, pero las que vienen
            # detrás conservan su número del archivo.
            if all(c is None or str(c).strip() == "" for c in fila):
                continue
            filas.append((i, list(fila)))
        return hoja.title or "", [str(t) if t is not None else "" for t in titulos], filas
    finally:
        libro.close()


def hojas_del_libro(datos: bytes) -> List[str]:
    """Los nombres de todas las hojas, para declarar en la vista previa cuál se
    usó cuando hay más de una (H-D47)."""
    import io
    from openpyxl import load_workbook
    libro = load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
    try:
        return list(libro.sheetnames)
    finally:
        libro.close()
