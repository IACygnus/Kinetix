"""
Export PDF - Versión de Producción
Sigue el mismo patrón que export_html.py
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import uuid
from datetime import datetime
import logging

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.services.jtl.jtl_parser import JTLParser

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/executions/{execution_id}/export/pdf")
async def export_pdf(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Exportar reporte como PDF profesional"""
    
    logger.info(f"🔵 PDF solicitado para: {execution_id}")
    
    # Validar UUID
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    # Obtener ejecución de BD
    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    logger.info(f"✅ Ejecución: {execution.name}")
    
    # Buscar archivo JTL
    upload_dir = Path("/app/uploads")
    jtl_files = list(upload_dir.glob(f"*{execution.jtl_filename}"))
    
    if not jtl_files:
        raise HTTPException(status_code=404, detail="Archivo JTL no encontrado")
    
    logger.info(f"📁 JTL: {jtl_files[0]}")
    
    try:
        # Parsear JTL
        parser = JTLParser(str(jtl_files[0]))
        df, _ = parser.parse()
        summary_df = parser.get_summary_table_data()
        
        logger.info(f"📊 DataFrame parseado: {len(df)} filas")
        
        # Generar HTML para PDF
        html_content = generate_html_for_pdf(execution, summary_df)
        
        # Generar PDF
        if WEASYPRINT_AVAILABLE:
            logger.info("🎨 Generando PDF con WeasyPrint...")
            pdf_bytes = HTML(string=html_content).write_pdf()
        else:
            logger.warning("⚠️ WeasyPrint no disponible, generando PDF básico...")
            pdf_bytes = generate_basic_pdf(execution)
        
        logger.info(f"✅ PDF generado: {len(pdf_bytes)} bytes")
        
        # Nombre del archivo
        safe_name = execution.name.replace(' ', '_')
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"reporte_{safe_name}_{date_str}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error generando PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")


def generate_html_for_pdf(execution: TestExecution, summary_df) -> str:
    """Genera HTML optimizado para PDF"""
    
    # Estadísticas de resumen
    stats_rows = ""
    for _, row in summary_df.iterrows():
        stats_rows += f"""
        <tr>
            <td>{row['label']}</td>
            <td>{int(row['muestras'])}</td>
            <td>{int(row['errores'])}</td>
            <td>{row['tasa_error']:.2f}%</td>
            <td>{row['promedio']:.0f}ms</td>
            <td>{row['min']:.0f}ms</td>
            <td>{row['max']:.0f}ms</td>
            <td>{row['p90']:.0f}ms</td>
            <td>{row['p95']:.0f}ms</td>
            <td>{row['p99']:.0f}ms</td>
        </tr>
        """
    
    # Total
    total_samples = int(summary_df['muestras'].sum())
    total_errors = int(summary_df['errores'].sum())
    error_rate = (total_errors / total_samples * 100) if total_samples > 0 else 0
    
    stats_rows += f"""
    <tr style="font-weight: bold; background: #f8f9fa;">
        <td>TOTAL</td>
        <td>{total_samples}</td>
        <td>{total_errors}</td>
        <td>{error_rate:.2f}%</td>
        <td>{execution.avg_response_time:.0f}ms</td>
        <td>{execution.min_response_time:.0f}ms</td>
        <td>{execution.max_response_time:.0f}ms</td>
        <td>{execution.p90_response_time:.0f}ms</td>
        <td>{execution.p95_response_time:.0f}ms</td>
        <td>{execution.p99_response_time:.0f}ms</td>
    </tr>
    """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4 landscape;
                margin: 1.5cm;
            }}
            
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
                color: #333;
            }}
            
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
            }}
            
            .header h1 {{
                margin: 0;
                font-size: 24pt;
            }}
            
            .header p {{
                margin: 5px 0 0 0;
                opacity: 0.9;
            }}
            
            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 15px;
                margin-bottom: 25px;
            }}
            
            .summary-card {{
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }}
            
            .summary-card h3 {{
                margin: 0 0 10px 0;
                font-size: 11pt;
                color: #666;
            }}
            
            .summary-card .value {{
                font-size: 20pt;
                font-weight: bold;
                color: #667eea;
            }}
            
            .section {{
                margin-bottom: 25px;
            }}
            
            .section h2 {{
                font-size: 16pt;
                color: #667eea;
                border-bottom: 2px solid #667eea;
                padding-bottom: 5px;
                margin-bottom: 15px;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 9pt;
                margin-bottom: 20px;
            }}
            
            th {{
                background: #667eea;
                color: white;
                padding: 10px 8px;
                text-align: left;
                font-weight: bold;
            }}
            
            td {{
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }}
            
            tr:nth-child(even) {{
                background: #f8f9fa;
            }}
            
            .analysis-box {{
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin: 10px 0;
                border-radius: 4px;
            }}
            
            .analysis-box h3 {{
                margin: 0 0 10px 0;
                color: #667eea;
                font-size: 12pt;
            }}
            
            .analysis-box p {{
                margin: 5px 0;
                line-height: 1.6;
            }}
            
            .footer {{
                text-align: center;
                color: #999;
                font-size: 9pt;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #e0e0e0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>JMeter Analyzer Pro</h1>
            <p>Reporte de Análisis de Performance</p>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Nombre de la Prueba</h3>
                <div class="value" style="font-size: 14pt;">{execution.name}</div>
            </div>
            <div class="summary-card">
                <h3>Total Requests</h3>
                <div class="value">{execution.total_requests:,}</div>
            </div>
            <div class="summary-card">
                <h3>Tasa de Error</h3>
                <div class="value" style="color: {'#dc3545' if execution.error_rate > 5 else '#28a745'};">
                    {execution.error_rate:.2f}%
                </div>
            </div>
            <div class="summary-card">
                <h3>Tiempo Promedio</h3>
                <div class="value">{execution.avg_response_time:.0f}ms</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Estadísticas por Transacción</h2>
            <table>
                <thead>
                    <tr>
                        <th>Transacción</th>
                        <th>Muestras</th>
                        <th>Errores</th>
                        <th>% Error</th>
                        <th>Promedio</th>
                        <th>Min</th>
                        <th>Max</th>
                        <th>P90</th>
                        <th>P95</th>
                        <th>P99</th>
                    </tr>
                </thead>
                <tbody>
                    {stats_rows}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>🤖 Análisis de IA</h2>
            
            {f'''
            <div class="analysis-box">
                <h3>Resumen General</h3>
                <p>{execution.ai_analysis_summary or "No disponible"}</p>
            </div>
            ''' if execution.ai_analysis_summary else ''}
            
            {f'''
            <div class="analysis-box">
                <h3>Análisis de Errores</h3>
                <p>{execution.ai_analysis_errors or "No se detectaron errores"}</p>
            </div>
            ''' if execution.ai_analysis_errors else ''}
            
            {f'''
            <div class="analysis-box">
                <h3>Recomendaciones</h3>
                <p>{execution.ai_recommendations or "No hay recomendaciones disponibles"}</p>
            </div>
            ''' if execution.ai_recommendations else ''}
        </div>
        
        <div class="footer">
            <p>Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | JMeter Analyzer Pro v1.0</p>
            <p>SQA - Software Quality Assurance</p>
        </div>
    </body>
    </html>
    """
    
    return html


def generate_basic_pdf(execution: TestExecution) -> bytes:
    """Genera PDF básico si WeasyPrint no está disponible"""
    
    pdf_content = f"""
%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 250 >>
stream
BT
/F1 24 Tf
50 750 Td
(JMeter Analyzer Pro) Tj
0 -40 Td
/F1 14 Tf
(Reporte de Performance) Tj
0 -40 Td
/F1 12 Tf
(Prueba: {execution.name[:40]}) Tj
0 -30 Td
(Total Requests: {execution.total_requests}) Tj
0 -20 Td
(Tasa de Error: {execution.error_rate:.2f}%) Tj
0 -20 Td
(Tiempo Promedio: {execution.avg_response_time:.0f}ms) Tj
0 -20 Td
(P90: {execution.p90_response_time:.0f}ms) Tj
0 -20 Td
(P95: {execution.p95_response_time:.0f}ms) Tj
0 -20 Td
(P99: {execution.p99_response_time:.0f}ms) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000251 00000 n 
0000000336 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
637
%%EOF
""".encode('latin-1')
    
    return pdf_content