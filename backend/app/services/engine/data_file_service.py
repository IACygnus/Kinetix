# backend/app/services/engine/data_file_service.py
"""
Data File Service — Maneja la carga y parseo de archivos CSV para parametrizacion.

Los archivos CSV son la fuente de datos para variables en los scripts.
Soporta CSV estandar con header en la primera fila.
"""
import csv
import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from io import StringIO

DATA_FILES_DIR = Path("/app/data/uploaded_files")


class DataFileService:
    """Servicio para parsear y almacenar archivos de datos CSV."""

    def parse_csv(self, content: str, original_filename: str) -> Tuple[List[str], int]:
        """
        Parsear contenido CSV y extraer columnas y conteo de filas.

        Returns:
            (columns, row_count)
        """
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        if not rows:
            raise ValueError("El archivo CSV esta vacio")

        columns = [col.strip() for col in rows[0]]
        if not columns:
            raise ValueError("La primera fila (header) esta vacia")

        row_count = len(rows) - 1  # excluir header

        return columns, row_count

    def save_file(self, content: bytes, original_filename: str) -> Tuple[str, str]:
        """
        Guardar archivo en disco.

        Returns:
            (stored_filename, file_path)
        """
        DATA_FILES_DIR.mkdir(parents=True, exist_ok=True)

        # Nombre unico para evitar colisiones
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', original_filename)
        stored_filename = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = DATA_FILES_DIR / stored_filename

        file_path.write_bytes(content)

        return stored_filename, str(file_path)

    def read_preview(self, file_path: str, max_rows: int = 5) -> List[Dict[str, str]]:
        """
        Leer las primeras N filas del CSV para preview.

        Returns:
            Lista de dicts {columna: valor}
        """
        path = Path(file_path)
        if not path.exists():
            return []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(dict(row))

        return rows
