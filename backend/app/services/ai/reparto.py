"""Qué esfuerzo de razonamiento —y qué modelo— lleva cada TIPO de llamada (reporte 151).

Una sola definición para todo el producto. La decide `_generate` por el nombre
de la sección, así que ningún llamador tiene que acordarse.

ESFUERZO
  - El nivel de la CONFIGURACIÓN (`ai_config.reasoning_effort`) solo para lo que
    escribe el dictamen: el resumen (el general y el de cada transacción), las
    conclusiones, las recomendaciones, la comparativa y la conclusión única del
    integrado.
  - BAJO para todo lo demás: el chat del Analista IA, las gráficas (generales y
    por transacción), los errores, las redirecciones, las capturas y sus
    análisis globales. Medido en el 150: −56 % de razonamiento y −33 % de tiempo
    sin perder el uso de los criterios.

MODELO LIGERO (opcional)
  - `AI_MODELO_LIGERO` en el entorno: si tiene valor, el chat y las gráficas lo
    usan en lugar del modelo principal. VACÍO = el mismo modelo (así queda).
"""
from __future__ import annotations

import os
from typing import Optional

BAJO = "low"

# Las que llevan el esfuerzo de la configuración. Todo lo demás, bajo.
CON_ESFUERZO_CONFIGURADO = frozenset({
    "summary_table",          # resumen del informe general
    "txreport_summary",       # resumen de cada transacción
    "conclusions",
    "recommendations",
    "comparison_analysis",    # comparativa carga vs estrés
    "consolidated_unico",     # conclusión única del integrado
})


def esfuerzo_para(seccion: Optional[str], configurado: Optional[str]) -> str:
    """El esfuerzo que se manda en una llamada de esta sección."""
    if (seccion or "") in CON_ESFUERZO_CONFIGURADO:
        return configurado or BAJO
    return BAJO


def es_ligera(seccion: Optional[str]) -> bool:
    """El chat y las gráficas: lo que puede ir con el modelo ligero."""
    s = seccion or ""
    return s == "analista_chat" or s.startswith("chart_") or s.startswith("txreport_chart_")


def modelo_ligero_del_entorno() -> Optional[str]:
    return (os.getenv("AI_MODELO_LIGERO") or "").strip() or None


def modelo_para(seccion: Optional[str], principal: str, ligero: Optional[str]) -> str:
    return ligero if (ligero and es_ligera(seccion)) else principal
