"""
Constructor de bundle exportable de un diseño AI Script.

- Si el diseño tiene CSVs físicos asociados → ZIP con el JMX + carpeta Data/.
- Sin CSVs → solo JMX puro.

El JMX dentro del ZIP tiene la UDV `Data` reescrita a path relativo `./Data`
para que JMeter desktop lo abra sin configuración manual.

Fix HF14b sobre el bug H del diagnóstico forense
(docs/reports/diagnostico-forense-post-sprint-2.6.md): la UDV `Data` apuntaba a
un path absoluto Docker-interno que no resuelve al abrir el JMX en desktop.
"""
import io
import os
import re
import zipfile
from datetime import datetime
from typing import List, Optional, Tuple


def rewrite_data_udv_to_relative(jmx_content: str) -> str:
    """
    Reescribe la variable UDV `Data` en el JMX a path relativo `./Data`.

    Busca el par:
        <stringProp name="Argument.name">Data</stringProp>
        <stringProp name="Argument.value">/app/uploads/ai_data_files/...</stringProp>
    y deja el value como `./Data`. Solo reescribe la primera coincidencia.
    """
    pattern = re.compile(
        r'(<stringProp\s+name="Argument\.name">Data</stringProp>\s*'
        r'<stringProp\s+name="Argument\.value">)[^<]*(</stringProp>)',
        re.DOTALL,
    )
    return pattern.sub(r"\1./Data\2", jmx_content, count=1)


def sanitize_for_filename(name: Optional[str]) -> str:
    """
    Sanea un string para usarlo como filename portable.
    - Espacios → `_`
    - Caracteres no alfanuméricos (excepto _-) → `_`
    - Múltiples `_` consecutivos → uno solo
    - Trim de `_` al inicio/final
    """
    if not name:
        return ""
    s = name.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\-]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def build_export_filename(
    design_name: str,
    client_name: Optional[str],
    extension: str,
    now: Optional[datetime] = None,
) -> str:
    """
    Construye el filename de descarga:
        {cliente}_{nombre}_{YYYYMMDD_HHMMSS}.{ext}
    Si client_name es None/vacío, omite esa parte.
    """
    if now is None:
        now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")

    name_safe = sanitize_for_filename(design_name) or "diseno"
    client_safe = sanitize_for_filename(client_name)

    parts: List[str] = []
    if client_safe:
        parts.append(client_safe)
    parts.append(name_safe)
    parts.append(ts)

    return "_".join(parts) + "." + extension.lstrip(".")


def build_export_bundle(
    jmx_content: str,
    csv_files: List[Tuple[str, bytes]],
) -> Tuple[bytes, str]:
    """
    Construye el bundle exportable.

    Args:
        jmx_content: contenido XML del JMX original.
        csv_files: lista [(filename, contenido_bytes), ...] de los CSVs físicos.

    Returns:
        (payload_bytes, mime_type):
        - csv_files vacío → (jmx_bytes, "application/xml").
        - con CSVs → (zip_bytes, "application/zip") con script.jmx + Data/ + README.
    """
    if not csv_files:
        # JMX puro: no hay carpeta Data en el destino, no se reescribe la UDV.
        return jmx_content.encode("utf-8"), "application/xml"

    rewritten_jmx = rewrite_data_udv_to_relative(jmx_content)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("script.jmx", rewritten_jmx)
        for fname, content in csv_files:
            # basename neutraliza cualquier intento de path traversal.
            safe_fname = os.path.basename(fname)
            zf.writestr(f"Data/{safe_fname}", content)
        readme = (
            "Bundle exportado de SQA Kinetix Pro.\n\n"
            "Estructura:\n"
            "  script.jmx       - Plan JMeter\n"
            "  Data/            - CSV Data Sets referenciados por el plan\n\n"
            "Uso: descomprimir y abrir script.jmx con JMeter Desktop.\n"
            "Los CSV se resuelven automaticamente via path relativo ./Data\n"
        )
        zf.writestr("README.txt", readme)

    return buf.getvalue(), "application/zip"
