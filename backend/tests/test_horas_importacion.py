"""ETAPA H3.4 — el lector del archivo de horas (§6.1, H-D42 a H-D46).

Estos tests no abren ningún `.xlsx`: prueban las reglas, que es donde están los
fallos que no se ven. Un archivo de muestra comprueba **un** caso de cada cosa;
aquí se comprueban los bordes, que es lo que cambia cuando el archivo viene de
otro sitio o de otra versión de la herramienta.

Los casos salen del archivo real —títulos con espacio final, fechas `dd/mm/aaaa`,
`Si`/`No`, observaciones con U+202F— más lo que podría llegar si cambia el origen.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from app.services.horas.importacion import (
    COLUMNAS, OBLIGATORIAS, FaltanColumnas,
    leer_fecha, leer_horas, leer_id, leer_si_no, limpiar_texto, mapear_columnas,
)

# La fila de títulos tal cual viene del archivo de Fredy: con espacio al final en
# seis de las once columnas.
TITULOS_REALES = [
    "Id", "Observaciones", "Cliente ", "Proyecto ", "Tarea ", "Tipo de hora",
    "Sub Tipo Hora", "Extra Hour", "Fecha ", "Tiempo total ", "Facturable ",
]


# ==================== LOS TÍTULOS (H-D42) ====================

def test_los_titulos_del_archivo_real_se_reconocen_todos():
    mapa = mapear_columnas(TITULOS_REALES)
    assert set(mapa) == set(COLUMNAS)
    assert mapa["cliente"] == 2 and mapa["horas"] == 9 and mapa["facturable"] == 10


def test_el_espacio_final_no_estorba():
    """Es el caso que trae el archivo: «Cliente » con espacio."""
    assert mapear_columnas(["Cliente ", "Proyecto", "Tarea", "Fecha", "Tiempo total",
                            "Facturable"])["cliente"] == 0


def test_ni_las_tildes_ni_las_mayusculas():
    mapa = mapear_columnas(["CLIENTE", "proyecto", "TAREA", "fecha", "TIEMPO TOTAL",
                            "Facturable"])
    assert mapa["actividad"] == 2 and mapa["horas"] == 4


def test_el_orden_de_las_columnas_da_igual():
    mapa = mapear_columnas(["Facturable", "Tiempo total", "Fecha", "Tarea",
                            "Proyecto", "Cliente"])
    assert mapa["cliente"] == 5 and mapa["facturable"] == 0


def test_las_opcionales_pueden_faltar():
    """Sin `Id`, sin `Observaciones` y sin `Extra Hour` el archivo sigue sirviendo."""
    mapa = mapear_columnas(["Cliente", "Proyecto", "Tarea", "Fecha", "Tiempo total",
                            "Facturable"])
    assert "external_id" not in mapa and "extra" not in mapa and "notas" not in mapa


def test_si_falta_una_obligatoria_se_para_y_se_dice_cual():
    with pytest.raises(FaltanColumnas) as e:
        mapear_columnas(["Cliente", "Proyecto", "Tarea", "Tiempo total", "Facturable"])
    assert e.value.faltan == ["Fecha"]
    assert "«Fecha»" in str(e.value)


def test_se_dicen_TODAS_las_que_faltan_de_una_vez():
    """Descubrirlas de una en una, subiendo el archivo cinco veces, es peor."""
    with pytest.raises(FaltanColumnas) as e:
        mapear_columnas(["Id", "Observaciones"])
    assert len(e.value.faltan) == len(OBLIGATORIAS)


def test_facturable_es_obligatoria_aunque_su_celda_vacia_sea_no():
    """Que falte la columna entera importaría el mes como no facturable sin que
    nadie lo haya decidido, y eso es dinero."""
    with pytest.raises(FaltanColumnas) as e:
        mapear_columnas(["Cliente", "Proyecto", "Tarea", "Fecha", "Tiempo total"])
    assert e.value.faltan == ["Facturable"]


def test_una_columna_vacia_o_nula_no_rompe_el_mapeo():
    mapa = mapear_columnas(["Cliente", None, "Proyecto", "", "Tarea", "Fecha",
                            "Tiempo total", "Facturable"])
    assert mapa["proyecto"] == 2


# ==================== LA FECHA (H-D43) ====================

def test_el_formato_del_archivo_es_dd_mm_aaaa():
    assert leer_fecha("15/09/2026") == date(2026, 9, 15)


def test_con_un_solo_digito_tambien():
    assert leer_fecha("1/9/2026") == date(2026, 9, 1)


def test_el_dia_va_primero_y_no_el_mes():
    """`05/09` es el 5 de septiembre, no el 9 de mayo. Si esto se invierte, las
    horas se van a otro mes sin que nada falle."""
    assert leer_fecha("05/09/2026") == date(2026, 9, 5)


def test_tambien_vale_el_formato_iso():
    assert leer_fecha("2026-09-15") == date(2026, 9, 15)


def test_y_el_numero_de_serie_de_excel():
    assert leer_fecha(46280) == date(2026, 9, 15)
    assert leer_fecha("46280") == date(2026, 9, 15)


def test_una_fecha_de_verdad_pasa_tal_cual():
    from datetime import datetime
    assert leer_fecha(date(2026, 9, 15)) == date(2026, 9, 15)
    assert leer_fecha(datetime(2026, 9, 15, 13, 30)) == date(2026, 9, 15)


def test_una_fecha_con_hora_pegada():
    assert leer_fecha("15/09/2026 00:00:00") == date(2026, 9, 15)


@pytest.mark.parametrize("basura", [
    None, "", "  ", "ayer", "15 de septiembre", "2026/09/15/00", "31/02/2026", 3.5, 0,
])
def test_lo_que_no_se_entiende_devuelve_none(basura):
    """Y la fila se marcará inválida con su motivo (H-D40), sin tumbar el resto."""
    assert leer_fecha(basura) is None


def test_el_31_de_febrero_no_existe():
    assert leer_fecha("31/02/2026") is None


def test_los_seriales_del_error_de_1900_se_rechazan():
    """Excel cree que 1900 fue bisiesto y los 60 primeros seriales están
    corridos un día. Nadie registra horas en enero de 1900: mejor rechazarlos
    que inventarse la fecha."""
    assert leer_fecha(1) is None
    assert leer_fecha(60) is None
    assert leer_fecha(61) == date(1900, 3, 1)


# ==================== LAS HORAS (H-D44) ====================

@pytest.mark.parametrize("valor,esperado", [
    (0.5, "0.5"), (8.5, "8.5"), (8, "8"), (1, "1"), (0.25, "0.25"),
])
def test_el_formato_del_archivo_es_numero(valor, esperado):
    assert leer_horas(valor) == D(esperado)


def test_tambien_vale_el_texto_con_coma():
    assert leer_horas("8,5") == D("8.5")
    assert leer_horas("0,25") == D("0.25")


def test_y_con_punto():
    assert leer_horas("8.5") == D("8.5")


def test_con_espacios_alrededor():
    assert leer_horas("  8,5  ") == D("8.5")


@pytest.mark.parametrize("basura", [None, "", "   ", "ocho", "8:30", True, False])
def test_lo_que_no_es_un_numero_devuelve_none(basura):
    assert leer_horas(basura) is None


def test_el_paso_no_se_comprueba_aqui():
    """`leer_horas` lee; el paso de 0,25 lo dice `validar_paso()`, que ya tiene el
    mensaje en español. Dos sitios diciendo lo mismo acabarían discrepando."""
    assert leer_horas(0.3) == D("0.3")


# ==================== SÍ / NO (H-D45) ====================

@pytest.mark.parametrize("valor", ["Si", "Sí", "SI", "SÍ", "sí", "s", "S",
                                   "true", "TRUE", "Verdadero", 1, 1.0, True, "x"])
def test_lo_que_cuenta_como_si(valor):
    assert leer_si_no(valor) is True


@pytest.mark.parametrize("valor", ["No", "NO", "n", "N", "false", "Falso", 0, 0.0,
                                   False, "", "   ", None])
def test_lo_que_cuenta_como_no(valor):
    assert leer_si_no(valor) is False


def test_lo_que_no_se_reconoce_cuenta_como_no():
    """En horas facturables, el que no lo dice claramente no se cobra."""
    assert leer_si_no("quizá") is False
    assert leer_si_no("pendiente") is False


# ==================== LAS OBSERVACIONES (H-D46) ====================

def test_los_saltos_de_linea_se_quedan_en_una_linea():
    assert limpiar_texto("Primera\nSegunda\r\nTercera") == "Primera Segunda Tercera"


def test_el_espacio_fino_sin_salto_que_cuela_excel():
    """U+202F. Viene en el archivo real y, sin limpiarlo, sale en pantalla como
    un cuadrito."""
    assert limpiar_texto("Reunión de seguimiento") == "Reunión de seguimiento"


@pytest.mark.parametrize("raro", [" ", " ", " ", "​"])
def test_los_demas_espacios_raros_tambien(raro):
    assert limpiar_texto(f"antes{raro}despues") == "antes despues"


def test_los_espacios_de_mas_se_colapsan():
    assert limpiar_texto("   uno    dos   ") == "uno dos"


def test_una_celda_vacia_es_texto_vacio_no_un_error():
    """H-D46: un comentario raro nunca invalida la fila."""
    assert limpiar_texto(None) == ""
    assert limpiar_texto("") == ""


def test_las_tildes_se_conservan():
    """`normalizar()` es para comparar, no para guardar: lo que se guarda va con
    sus tildes."""
    assert limpiar_texto("Gestión de proyectos") == "Gestión de proyectos"


# ==================== EL Id (H-D35) ====================

def test_el_id_numerico_se_guarda_como_texto():
    assert leer_id(1234) == "1234"


def test_un_entero_que_excel_dio_como_decimal():
    """`1234.0` y `1234` tienen que ser el mismo identificador, o la segunda
    importación duplicaría en vez de actualizar."""
    assert leer_id(1234.0) == "1234"


def test_un_id_de_texto():
    assert leer_id("  ABC-99 ") == "ABC-99"


def test_sin_id_es_cadena_vacia():
    """Se importa como nueva y la vista previa la señala (H-D35)."""
    assert leer_id(None) == ""
    assert leer_id("") == ""
