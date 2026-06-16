"""Tests del validador de CSVs referenciados (HF14a)."""
import os
import tempfile

from app.services.engine.csv_reference_validator import (
    extract_csv_filenames_from_jmx,
    resolve_csv_filename,
    find_missing_csv_files,
    build_missing_csv_error_message,
)


JMX_SAMPLE_WITH_CSV = """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan testname="Test"><stringProp name="TestPlan.comments"/></TestPlan>
    <hashTree>
      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="Data Data_Create.txt">
        <stringProp name="filename">${Data}/Data_Create.txt</stringProp>
        <stringProp name="variableNames">name,age</stringProp>
      </CSVDataSet>
      <CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="Data Data_Update.txt">
        <stringProp name="filename">${Data}/Data_Update.txt</stringProp>
        <stringProp name="variableNames">id,name</stringProp>
      </CSVDataSet>
    </hashTree>
  </hashTree>
</jmeterTestPlan>"""


def test_extract_csv_filenames():
    refs = extract_csv_filenames_from_jmx(JMX_SAMPLE_WITH_CSV)
    assert len(refs) == 2
    assert refs[0]["filename"] == "${Data}/Data_Create.txt"
    assert refs[1]["filename"] == "${Data}/Data_Update.txt"


def test_extract_csv_filenames_empty_jmx():
    refs = extract_csv_filenames_from_jmx(
        '<?xml version="1.0"?><jmeterTestPlan><hashTree/></jmeterTestPlan>'
    )
    assert refs == []


def test_extract_csv_filenames_invalid_xml():
    refs = extract_csv_filenames_from_jmx("not xml at all")
    assert refs == []


def test_resolve_filename_with_var():
    resolved = resolve_csv_filename("${Data}/file.csv", {"Data": "/tmp/work"})
    assert resolved == "/tmp/work/file.csv"


def test_resolve_filename_no_var():
    resolved = resolve_csv_filename("/abs/path/file.csv", {"Data": "/tmp/work"})
    assert resolved == "/abs/path/file.csv"


def test_find_missing_csv_files_all_available():
    with tempfile.TemporaryDirectory() as workdir:
        for fname in ["Data_Create.txt", "Data_Update.txt"]:
            with open(os.path.join(workdir, fname), "w") as f:
                f.write("col1,col2\n")

        missing = find_missing_csv_files(
            jmx_content=JMX_SAMPLE_WITH_CSV,
            workdir=workdir,
            data_dir_resolver={"Data": workdir},
            available_filenames={"Data_Create.txt", "Data_Update.txt"},
        )
        assert missing == []


def test_find_missing_csv_files_one_missing():
    with tempfile.TemporaryDirectory() as workdir:
        with open(os.path.join(workdir, "Data_Create.txt"), "w") as f:
            f.write("col1\n")

        missing = find_missing_csv_files(
            jmx_content=JMX_SAMPLE_WITH_CSV,
            workdir=workdir,
            data_dir_resolver={"Data": workdir},
            available_filenames={"Data_Create.txt"},
        )
        assert len(missing) == 1
        assert missing[0]["basename"] == "Data_Update.txt"


def test_find_missing_csv_files_absolute_existing(tmp_path):
    """Un CSV con path absoluto existente no se marca como faltante."""
    csv_file = tmp_path / "abs_data.csv"
    csv_file.write_text("a,b\n")
    jmx = f"""<?xml version="1.0"?><jmeterTestPlan><hashTree>
      <CSVDataSet testname="abs"><stringProp name="filename">{csv_file}</stringProp></CSVDataSet>
    </hashTree></jmeterTestPlan>"""
    missing = find_missing_csv_files(
        jmx_content=jmx,
        workdir=str(tmp_path),
        data_dir_resolver={"Data": str(tmp_path)},
        available_filenames=set(),
    )
    assert missing == []


def test_error_message_guides_user():
    missing = [
        {
            "name": "Data Update CSV",
            "filename": "${Data}/Data_Update.txt",
            "resolved": "/tmp/work/Data_Update.txt",
            "basename": "Data_Update.txt",
        },
    ]
    msg = build_missing_csv_error_message(missing)
    assert "Data_Update.txt" in msg
    assert "Gestionar archivos" in msg
    assert "elimina" in msg.lower()


def test_error_message_empty_when_no_missing():
    assert build_missing_csv_error_message([]) == ""
