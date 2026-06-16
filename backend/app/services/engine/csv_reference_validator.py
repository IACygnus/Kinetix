"""
Validador de CSVs referenciados en un JMX vs archivos físicos disponibles.

Detecta si un CSV Data Set apunta a un archivo que no existe en el workdir
(ni tiene registro materializado), previniendo fallos silenciosos de JMeter al
ejecutar (status "completed" con 0 samples).

Fix HF14a sobre el bug descubierto en docs/reports/diagnostico-forense-post-sprint-2.6.md
(la IA agrega un CSV Data Set vía refine pero el archivo físico nunca se crea).
"""
import os
from typing import Dict, List, Set
from xml.etree import ElementTree as ET


def extract_csv_filenames_from_jmx(jmx_content: str) -> List[Dict[str, str]]:
    """
    Extrae todas las referencias a archivos CSV en un JMX.

    Retorna lista de dicts:
        [{"name": "Data Data_Update.txt", "filename": "${Data}/Data_Update.txt"}, ...]

    Args:
        jmx_content: contenido XML del JMX.

    Returns:
        Lista de CSV Data Sets con sus filenames raw. Vacía si el XML es inválido.
    """
    csv_refs: List[Dict[str, str]] = []

    try:
        root = ET.fromstring(jmx_content)
    except ET.ParseError:
        # JMX inválido → vacío; el caller maneja el error de validez por separado.
        return csv_refs

    # JMeter usa CSVDataSet como elementType:
    #   <CSVDataSet guiclass="..." testname="...">
    #     <stringProp name="filename">...</stringProp>
    for csv_elem in root.iter("CSVDataSet"):
        testname = csv_elem.get("testname", "CSV Data Set")
        filename = None
        for prop in csv_elem.iter("stringProp"):
            if prop.get("name") == "filename":
                filename = (prop.text or "").strip()
                break
        if filename:
            csv_refs.append({"name": testname, "filename": filename})

    return csv_refs


def resolve_csv_filename(raw_filename: str, data_dir_resolver: Dict[str, str]) -> str:
    """
    Resuelve variables JMeter en el filename (e.g. ``${Data}/file.csv``).

    Args:
        raw_filename: filename tal cual aparece en el JMX (puede tener ${vars}).
        data_dir_resolver: mapa {"Data": "/path/workdir", ...}.

    Returns:
        Path final donde JMeter buscará el archivo (vars sin resolver se dejan).
    """
    resolved = raw_filename
    for var_name, var_value in data_dir_resolver.items():
        resolved = resolved.replace("${" + var_name + "}", var_value)
    return resolved


def find_missing_csv_files(
    jmx_content: str,
    workdir: str,
    data_dir_resolver: Dict[str, str],
    available_filenames: Set[str],
) -> List[Dict[str, str]]:
    """
    Determina qué CSV Data Sets del JMX apuntan a archivos NO disponibles.

    Un archivo se considera disponible si:
    - Resuelve a un path absoluto que existe físicamente, O
    - Su nombre base está en ``available_filenames`` y existe en el workdir.

    Args:
        jmx_content: JMX a validar (se recomienda el original, con ${vars}).
        workdir: directorio donde se ejecutará JMeter.
        data_dir_resolver: mapa de variables JMeter.
        available_filenames: nombres (original_filename) realmente copiados al workdir.

    Returns:
        Lista de CSVs faltantes:
        [{"name", "filename", "resolved", "basename"}, ...].
    """
    missing: List[Dict[str, str]] = []
    csv_refs = extract_csv_filenames_from_jmx(jmx_content)

    for ref in csv_refs:
        raw = ref["filename"]
        resolved = resolve_csv_filename(raw, data_dir_resolver)
        basename = os.path.basename(resolved)

        # Caso 1: path absoluto que existe físicamente.
        if os.path.isabs(resolved) and os.path.exists(resolved):
            continue

        # Caso 2: el basename está disponible y físicamente en el workdir.
        if basename in available_filenames:
            workdir_path = os.path.join(workdir, basename)
            if os.path.exists(workdir_path):
                continue

        missing.append({
            "name": ref["name"],
            "filename": raw,
            "resolved": resolved,
            "basename": basename,
        })

    return missing


def build_missing_csv_error_message(missing: List[Dict[str, str]]) -> str:
    """Construye un mensaje guiado para el usuario cuando faltan CSVs."""
    if not missing:
        return ""

    lines = ["No se puede ejecutar: el JMX referencia CSVs sin archivo físico disponible:"]
    for m in missing:
        lines.append(f"  - {m['basename']} (referenciado por: {m['name']})")

    lines.append("")
    lines.append("Soluciones:")
    lines.append("  1. Sube los archivos desde 'Gestionar archivos' en el árbol del Editor IA.")
    lines.append("  2. O elimina el CSV Data Set desde el árbol si ya no lo necesitas.")

    return "\n".join(lines)
