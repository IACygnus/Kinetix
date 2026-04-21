# backend/app/api/v1/endpoints/script_variables.py
"""
Endpoint para escanear y retornar el inventario de variables de un script.
Analiza el script_model JSON y extrae todas las variables encontradas en:
- URLs, headers, body de cada request
- Extractors de cada request
- Array variables[] del propio scriptModel
"""
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.script_design import ScriptDesign

router = APIRouter()

BUILTIN_VARS = {'$guid', '$randomIP', '$timestamp', '$isoTimestamp', '$randomInt', '$randomAlphaNum'}


def extract_var_names(text: str) -> list:
    """Extrae nombres de variables de un string con formato ${varName}."""
    if not text:
        return []
    matches = re.findall(r'\$\{([^}]+)\}', str(text))
    return [m for m in matches if m not in BUILTIN_VARS]


@router.get("/{script_id}/variables")
async def get_script_variables(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Escanea el scriptModel completo y retorna el inventario consolidado de variables.
    Incluye: donde se usa cada variable y cuantas veces aparece.
    """
    result = await db.execute(
        select(ScriptDesign).where(
            ScriptDesign.id == script_id,
            ScriptDesign.user_id == current_user.id
        )
    )
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    model = script.script_model or {}
    requests_list = model.get("requests", [])

    # Escanear todas las variables usadas
    usage: dict = {}

    for req in requests_list:
        req_name = req.get("name", req.get("id", "unknown"))

        for var in extract_var_names(req.get("url", "")):
            usage.setdefault(var, []).append(f"URL de '{req_name}'")

        for k, v in (req.get("headers") or {}).items():
            for var in extract_var_names(v):
                usage.setdefault(var, []).append(f"Header '{k}' de '{req_name}'")

        for var in extract_var_names(req.get("body", "")):
            usage.setdefault(var, []).append(f"Body de '{req_name}'")

        for ext in (req.get("extractors") or []):
            vname = ext.get("variable_name", "")
            if vname:
                usage.setdefault(vname, []).append(f"Extractor de '{req_name}'")

    # Construir resultado
    inventory = []
    seen = set()

    # Variables ya definidas en el modelo
    for var_def in model.get("variables", []):
        name = var_def["name"]
        seen.add(name)
        inventory.append({
            "name": name,
            "value": var_def.get("value", ""),
            "type": var_def.get("type", "manual"),
            "source_hint": var_def.get("source_hint", ""),
            "default_value": var_def.get("default_value"),
            "datafile_name": var_def.get("datafile_name"),
            "datafile_column": var_def.get("datafile_column"),
            "used_in": usage.get(name, []),
            "usage_count": len(usage.get(name, [])),
        })

    # Variables usadas en requests pero no definidas aun
    for name, uses in usage.items():
        if name not in seen:
            inventory.append({
                "name": name,
                "value": "",
                "type": "auto",
                "source_hint": "Detectada en requests -- sin valor asignado",
                "used_in": uses,
                "usage_count": len(uses),
            })

    return {
        "script_id": script_id,
        "total": len(inventory),
        "variables": inventory,
    }
