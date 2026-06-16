"""Tests del export bundle builder (HF14b)."""
import io
import zipfile
from datetime import datetime

from app.services.engine.export_bundle_builder import (
    rewrite_data_udv_to_relative,
    sanitize_for_filename,
    build_export_filename,
    build_export_bundle,
)


JMX_WITH_DATA_UDV = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <Arguments>
      <collectionProp name="Arguments.arguments">
        <elementProp name="Data" elementType="Argument">
          <stringProp name="Argument.name">Data</stringProp>
          <stringProp name="Argument.value">/app/uploads/ai_data_files/abc123</stringProp>
        </elementProp>
      </collectionProp>
    </Arguments>
  </hashTree>
</jmeterTestPlan>"""


def test_rewrite_data_udv_reescribe_a_relativo():
    result = rewrite_data_udv_to_relative(JMX_WITH_DATA_UDV)
    assert "./Data" in result
    assert "/app/uploads/ai_data_files/abc123" not in result


def test_rewrite_data_udv_sin_data_no_cambia():
    jmx_sin_data = '<?xml version="1.0"?><jmeterTestPlan><hashTree/></jmeterTestPlan>'
    assert rewrite_data_udv_to_relative(jmx_sin_data) == jmx_sin_data


def test_sanitize_filename_basico():
    assert sanitize_for_filename("Mi Proyecto") == "Mi_Proyecto"
    assert sanitize_for_filename("Cliente@SQA!") == "Cliente_SQA"
    assert sanitize_for_filename("  spaces   ") == "spaces"
    assert sanitize_for_filename("a__b___c") == "a_b_c"


def test_sanitize_filename_vacio():
    assert sanitize_for_filename("") == ""
    assert sanitize_for_filename(None) == ""


def test_build_export_filename_con_cliente():
    now = datetime(2026, 6, 3, 22, 30, 45)
    fname = build_export_filename("Performance Booking", "Compensar", "zip", now)
    assert fname == "Compensar_Performance_Booking_20260603_223045.zip"


def test_build_export_filename_sin_cliente():
    now = datetime(2026, 6, 3, 22, 30, 45)
    fname = build_export_filename("Performance Booking", None, "jmx", now)
    assert fname == "Performance_Booking_20260603_223045.jmx"


def test_build_export_filename_cliente_vacio():
    now = datetime(2026, 6, 3, 22, 30, 45)
    fname = build_export_filename("Test", "", "jmx", now)
    assert fname == "Test_20260603_223045.jmx"


def test_build_bundle_sin_csvs_devuelve_jmx_puro():
    payload, mime = build_export_bundle(JMX_WITH_DATA_UDV, csv_files=[])
    assert mime == "application/xml"
    assert payload == JMX_WITH_DATA_UDV.encode("utf-8")


def test_build_bundle_con_csvs_devuelve_zip():
    csv1 = ("Data_Create.txt", b"name,age\nSally,30\n")
    csv2 = ("Data_Update.txt", b"id,name\n1,Updated\n")

    payload, mime = build_export_bundle(JMX_WITH_DATA_UDV, csv_files=[csv1, csv2])
    assert mime == "application/zip"

    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        names = zf.namelist()
        assert "script.jmx" in names
        assert "Data/Data_Create.txt" in names
        assert "Data/Data_Update.txt" in names
        assert "README.txt" in names

        jmx_inside = zf.read("script.jmx").decode("utf-8")
        assert "./Data" in jmx_inside
        assert "/app/uploads" not in jmx_inside

        assert zf.read("Data/Data_Create.txt") == csv1[1]
        assert zf.read("Data/Data_Update.txt") == csv2[1]


def test_build_bundle_sanea_nombres_csv_sospechosos():
    """No permitir path traversal en nombres CSV."""
    csv_malicioso = ("../../etc/passwd", b"hack")
    payload, _ = build_export_bundle(JMX_WITH_DATA_UDV, csv_files=[csv_malicioso])

    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        names = zf.namelist()
        assert "Data/passwd" in names
        assert not any(".." in n for n in names)
