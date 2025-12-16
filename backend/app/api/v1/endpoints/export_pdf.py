"""
Export PDF
Nuevo endpoint separado para generar PDF del reporte
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import uuid
import logging
from datetime import datetime

# Para generar PDF necesitamos una librería
# Opción 1: weasyprint (CSS to PDF)
# Opción 2: playwright (headless browser)
# Opción 3: puppeteer/pyppeteer

from app.db.session import get_db
from app.db.models.test import TestExecution

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/executions/{execution_id}/export/pdf")
async def export_pdf(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Exportar reporte como PDF
    
    NOTA: Este endpoint requiere instalación de dependencias adicionales:
    - pip install weasyprint  (recomendado)
    O
    - pip install playwright && playwright install chromium
    """
    
    logger.info(f"🔵 Iniciando exportación PDF para: {execution_id}")
    
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    # IMPORTANTE: Primero necesitas instalar la librería
    # Aquí hay 2 opciones:
    
    try:
        # OPCIÓN 1: WeasyPrint (CSS to PDF) - MÁS SIMPLE
        from weasyprint import HTML
        
        # Reutilizar la misma función de HTML
        # Necesitarás importar la función generate_html_with_real_fields desde export_html_CAMPOS_REALES.py
        # O duplicar la lógica aquí
        
        html_content = generate_report_html(execution, db)
        
        # Generar PDF
        pdf_bytes = HTML(string=html_content).write_pdf()
        
        filename = f"reporte_{execution.name.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        
        logger.info(f"✅ PDF generado: {filename}")
        
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except ImportError:
        logger.error("❌ WeasyPrint no instalado")
        
        # OPCIÓN 2: Playwright (headless browser) - MÁS ROBUSTO
        try:
            from playwright.async_api import async_playwright
            
            html_content = generate_report_html(execution, db)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html_content)
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=True,
                    margin={'top': '20px', 'right': '20px', 'bottom': '20px', 'left': '20px'}
                )
                await browser.close()
            
            filename = f"reporte_{execution.name.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
            
            return Response(
                content=pdf_bytes,
                media_type='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
            
        except ImportError:
            logger.error("❌ Playwright no instalado")
            raise HTTPException(
                status_code=500,
                detail="PDF export no disponible. Instalar: pip install weasyprint O pip install playwright && playwright install chromium"
            )
    
    except Exception as e:
        logger.exception(f"❌ Error generando PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def generate_report_html(execution: TestExecution, db: AsyncSession) -> str:
    """
    Genera el HTML del reporte
    Reutiliza la misma lógica que export_html_CAMPOS_REALES.py
    """
    # Aquí deberías importar y reutilizar la función desde export_html_CAMPOS_REALES.py
    # Por ahora, placeholder:
    return "<html><body><h1>Reporte PDF</h1></body></html>"
