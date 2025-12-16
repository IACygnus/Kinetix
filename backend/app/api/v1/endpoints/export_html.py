"""
Export HTML - CAMPOS REALES DE BD
Usa los valores guardados en cada campo ai_analysis_*
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import uuid
import json
from datetime import datetime
import logging

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.services.jtl.jtl_parser import JTLParser

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/executions/{execution_id}/export/html")
async def export_html(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Exportar HTML con campos REALES de BD"""
    
    logger.info(f"🔵 Iniciando exportación HTML con campos reales para: {execution_id}")
    
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    result = await db.execute(select(TestExecution).where(TestExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    logger.info(f"✅ Ejecución encontrada: {execution.name}")
    
    upload_dir = Path("/app/uploads")
    jtl_files = list(upload_dir.glob(f"*{execution.jtl_filename}"))
    
    if not jtl_files:
        raise HTTPException(status_code=404, detail="Archivo JTL no encontrado")
    
    try:
        parser = JTLParser(str(jtl_files[0]))
        df, _ = parser.parse()
        
        summary_df = parser.get_summary_table_data()
        response_codes = parser.get_response_code_distribution()
        charts_data = parser.get_all_charts_data(interval_seconds=1)
        
        # STATISTICS
        statistics = {}
        for _, row in summary_df.iterrows():
            statistics[row['label']] = {
                'transaction': row['label'],
                'sampleCount': int(row['muestras']),
                'errorCount': int(row['errores']),
                'errorPct': float(row['tasa_error']),
                'meanResTime': float(row['promedio']),
                'medianResTime': float(row['mediana']),
                'minResTime': float(row['min']),
                'maxResTime': float(row['max']),
                'pct1ResTime': float(row['p90']),
                'pct2ResTime': float(row['p95']),
                'pct3ResTime': float(row['p99']),
                'throughput': float(row['rendimiento']),
                'receivedKBytesPerSec': float(row['kb_received']),
                'sentKBytesPerSec': float(row['kb_sent'])
            }
        
        total_samples = int(summary_df['muestras'].sum())
        total_errors = int(summary_df['errores'].sum())
        statistics['Total'] = {
            'transaction': 'Total',
            'sampleCount': total_samples,
            'errorCount': total_errors,
            'errorPct': (total_errors / total_samples * 100) if total_samples > 0 else 0,
            'meanResTime': float(execution.avg_response_time),
            'medianResTime': float(summary_df['mediana'].mean()),
            'minResTime': float(summary_df['min'].min()),
            'maxResTime': float(summary_df['max'].max()),
            'pct1ResTime': float(execution.p90_response_time),
            'pct2ResTime': float(execution.p95_response_time),
            'pct3ResTime': float(execution.p99_response_time),
            'throughput': float(summary_df['rendimiento'].sum()),
            'receivedKBytesPerSec': float(summary_df['kb_received'].sum()),
            'sentKBytesPerSec': float(summary_df['kb_sent'].sum())
        }
        
        # SERIES
        timeline_df = charts_data['timeline']
        series = {'timeline': [], 'response_times_by_label': []}
        
        for _, row in timeline_df.iterrows():
            series['timeline'].append({
                't': int(row['timestamp'].timestamp() * 1000),
                'p95': float(row.get('p95_response_time', row.get('avg_response_time', 0))),
                'tps': float(row['throughput']),
                'err': float(row['error_rate']),
                'threads': int(row['active_threads'])
            })
        
        for label_data in charts_data.get('response_times_by_label', []):
            label_series = []
            for _, row in label_data.iterrows():
                label_series.append({
                    't': int(row['timestamp'].timestamp() * 1000),
                    'value': float(row['value'])
                })
            series['response_times_by_label'].append({
                'label': label_data['label'].iloc[0] if len(label_data) > 0 else 'Unknown',
                'data': label_series
            })
        
        # RESPONSE CODES
        codes_list = []
        for _, row in response_codes.iterrows():
            codes_list.append({
                'code': str(row['responseCode']),
                'count': int(row['count'])
            })
        
        # IA ANALYSIS - USAR CAMPOS REALES DE BD
        ia_analysis = {
            'summary': execution.ai_analysis_summary or '',
            'response_time_over_time': execution.ai_analysis_response_time_over_time or '',
            'throughput': execution.ai_analysis_throughput or '',
            'error_rate': execution.ai_analysis_error_rate or '',
            'active_threads': execution.ai_analysis_active_threads or '',
            'response_times': execution.ai_analysis_response_times or '',
            'errors': execution.ai_analysis_errors or '',
            'recommendations': execution.ai_recommendations or ''
        }
        
        # Log para debug
        logger.info(f"📊 Análisis IA cargado:")
        logger.info(f"  - Summary: {len(ia_analysis['summary'])} chars")
        logger.info(f"  - Response Time Over Time: {len(ia_analysis['response_time_over_time'])} chars")
        logger.info(f"  - Throughput: {len(ia_analysis['throughput'])} chars")
        logger.info(f"  - Error Rate: {len(ia_analysis['error_rate'])} chars")
        logger.info(f"  - Active Threads: {len(ia_analysis['active_threads'])} chars")
        logger.info(f"  - Response Times: {len(ia_analysis['response_times'])} chars")
        logger.info(f"  - Errors: {len(ia_analysis['errors'])} chars")
        
        metadata = {
            'name': execution.name,
            'filename': execution.jtl_filename,
            'duration': f"{int(execution.duration_seconds // 60)}m {int(execution.duration_seconds % 60)}s",
            'totalRequests': execution.total_requests,
            'throughput': f"{execution.throughput:.2f} req/s",
            'timestamp': execution.created_at.isoformat()
        }
        
        html_content = generate_html_with_real_fields(statistics, series, codes_list, ia_analysis, metadata)
        
        filename = f"reporte_{execution.name.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.html"
        logger.info(f"✅ Exportación HTML con campos reales completa: {filename}")
        
        return HTMLResponse(
            content=html_content,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except Exception as e:
        logger.exception(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

def generate_html_with_real_fields(statistics, series, codes_data, ia_analysis, metadata):
    """Genera HTML con campos REALES de análisis IA"""
    
    statistics_json = json.dumps(statistics, ensure_ascii=False)
    series_json = json.dumps(series, ensure_ascii=False)
    codes_json = json.dumps(codes_data, ensure_ascii=False)
    ia_json = json.dumps(ia_analysis, ensure_ascii=False)
    
    # Helper para mostrar análisis o mensaje por defecto
    def render_analysis(field_name, title):
        content = ia_analysis.get(field_name, '')
        if content:
            return f'''
            <div class="analysis-box">
              <div class="analysis-title">{title}</div>
              <div class="analysis-content">{content}</div>
            </div>
            '''
        else:
            return f'''
            <div class="analysis-box" style="background: #f5f5f5; border-left-color: #ccc;">
              <div class="analysis-title">{title}</div>
              <div class="analysis-content" style="color: #999;">Sin análisis disponible.</div>
            </div>
            '''
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reporte de Performance - {metadata['name']}</title>
  
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
  
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    :root {{
      --sqa-cyan: #5BC0EB;
      --sqa-blue: #3E5AA9;
      --sqa-navy: #1E2B5A;
      --sqa-bg: #e8f4f8;
      --success: #4caf50;
      --warning: #ff9800;
      --error: #f44336;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--sqa-bg);
      color: var(--sqa-navy);
      line-height: 1.6;
    }}
    .header {{
      background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
      color: white;
      padding: 2rem;
      box-shadow: 0 4px 20px rgba(30, 43, 90, 0.3);
      position: relative;
      overflow: hidden;
    }}
    .header::before {{
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 200%;
      height: 100%;
      background-image: 
        radial-gradient(circle, rgba(91, 192, 235, 0.4) 2px, transparent 2px),
        radial-gradient(circle, rgba(255, 255, 255, 0.3) 1px, transparent 1px);
      background-size: 50px 50px, 80px 80px;
      background-position: 0 0, 40px 40px;
      animation: moveBackground 20s linear infinite;
      opacity: 0.6;
    }}
    @keyframes moveBackground {{
      0% {{ transform: translateX(0); }}
      100% {{ transform: translateX(50%); }}
    }}
    .header-content {{ position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; }}
    .header-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }}
    .logo {{ font-size: 2rem; font-weight: bold; text-transform: lowercase; }}
    .subtitle {{ color: rgba(255, 255, 255, 0.8); font-size: 0.9rem; }}
    .header-meta {{
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(10px);
      border-radius: 12px;
      padding: 1.5rem;
    }}
    .project-name {{ font-size: 1.8rem; font-weight: bold; margin-bottom: 1rem; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }}
    .meta-label {{ font-size: 0.75rem; opacity: 0.8; margin-bottom: 0.25rem; }}
    .meta-value {{ font-family: monospace; font-size: 0.95rem; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }}
    .kpi-card {{
      background: white;
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      border-left: 4px solid var(--sqa-cyan);
      transition: transform 0.2s;
    }}
    .kpi-card:hover {{ transform: translateY(-4px); }}
    .kpi-card.success {{ border-left-color: var(--success); }}
    .kpi-card.error {{ border-left-color: var(--error); }}
    .kpi-card.warning {{ border-left-color: var(--warning); }}
    .kpi-label {{ font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }}
    .kpi-value {{ font-size: 2rem; font-weight: bold; color: var(--sqa-navy); }}
    .section {{
      background: white;
      border-radius: 12px;
      padding: 2rem;
      margin-bottom: 2rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }}
    .section-title {{
      font-size: 1.5rem;
      font-weight: bold;
      margin-bottom: 1.5rem;
      color: var(--sqa-navy);
      border-left: 4px solid var(--sqa-cyan);
      padding-left: 1rem;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      background: var(--sqa-navy);
      color: white;
      padding: 0.75rem;
      text-align: left;
      font-size: 0.85rem;
      font-weight: 600;
    }}
    td {{ padding: 0.75rem; border-bottom: 1px solid #e0e0e0; font-size: 0.9rem; }}
    tr:hover {{ background: #f5f5f5; }}
    .total-row {{ background: #e3f2fd; font-weight: bold; }}
    .error-cell {{ color: var(--error); font-weight: 600; }}
    .analysis-box {{
      background: #e3f2fd;
      border-left: 4px solid var(--sqa-blue);
      border-radius: 8px;
      padding: 1.5rem;
      margin-top: 1rem;
      margin-bottom: 2rem;
    }}
    .analysis-title {{ font-size: 1.1rem; font-weight: bold; color: var(--sqa-navy); margin-bottom: 1rem; }}
    .analysis-content {{ white-space: pre-wrap; font-size: 0.9rem; line-height: 1.8; color: #333; }}
    .chart-container {{ position: relative; height: 300px; margin-bottom: 1rem; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 2rem; }}
    .bar-chart {{ margin: 1rem 0; }}
    .bar {{ display: flex; align-items: center; margin-bottom: 0.75rem; }}
    .bar-label {{ width: 180px; font-size: 0.9rem; font-weight: 600; }}
    .bar-container {{ flex: 1; height: 30px; background: #e0e0e0; border-radius: 4px; position: relative; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 4px; }}
    .bar-value {{
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 0.85rem;
      font-weight: 700;
      color: white;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }}
    .footer {{
      text-align: center;
      padding: 2rem;
      color: #666;
      font-size: 0.9rem;
      border-top: 1px solid #ddd;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <div class="header-top">
        <div>
          <div class="logo">sqa</div>
          <div class="subtitle">Software Quality Assurance</div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 0.85rem; opacity: 0.8;">Realizado por:</div>
          <div style="font-weight: bold;">Célula de performance SQA</div>
        </div>
      </div>
      <div class="header-meta">
        <div style="font-size: 0.85rem; opacity: 0.8; margin-bottom: 0.5rem;">NOMBRE DEL PROYECTO</div>
        <div class="project-name">{metadata['name']}</div>
        <div class="meta-grid">
          <div><div class="meta-label">📄 Archivo</div><div class="meta-value">{metadata['filename']}</div></div>
          <div><div class="meta-label">⏱️ Duración</div><div class="meta-value">{metadata['duration']}</div></div>
          <div><div class="meta-label">📊 Total Requests</div><div class="meta-value">{metadata['totalRequests']:,}</div></div>
          <div><div class="meta-label">🎯 Throughput</div><div class="meta-value">{metadata['throughput']}</div></div>
        </div>
      </div>
    </div>
  </div>

  <div class="container">
    <div class="kpis" id="kpis"></div>

    <div class="section">
      <div class="section-title">📋 Reporte Resumen</div>
      <div style="overflow-x: auto;">
        <table id="statisticsTable"></table>
      </div>
    </div>

    {render_analysis('summary', '🤖 Análisis del Reporte')}

    <div class="section">
      <div class="section-title">📈 Response Time Over Time</div>
      <div class="chart-container">
        <canvas id="responseTimeChart"></canvas>
      </div>
    </div>
    {render_analysis('response_time_over_time', '🤖 Análisis - Response Time Over Time')}

    <div class="section">
      <div class="section-title">🚀 Throughput Over Time</div>
      <div class="chart-container">
        <canvas id="throughputChart"></canvas>
      </div>
    </div>
    {render_analysis('throughput', '🤖 Análisis - Throughput Over Time')}

    <div class="section">
      <div class="section-title">❌ Error Rate Over Time</div>
      <div class="chart-container">
        <canvas id="errorRateChart"></canvas>
      </div>
    </div>
    {render_analysis('error_rate', '🤖 Análisis - Error Rate Over Time')}

    <div class="section">
      <div class="section-title">👥 Active Threads Over Time</div>
      <div class="chart-container">
        <canvas id="threadsChart"></canvas>
      </div>
    </div>
    {render_analysis('active_threads', '🤖 Análisis - Active Threads Over Time')}

    <div class="section">
      <div class="section-title">⏱️ Response Times by Transaction</div>
      <div class="chart-container" style="height: 400px;">
        <canvas id="responseByLabelChart"></canvas>
      </div>
    </div>
    {render_analysis('response_times', '🤖 Análisis - Tiempos de Respuesta por Transacción')}

    <div class="grid-2">
      <div class="section">
        <div class="section-title">📊 Errores por Transacción</div>
        <div id="errorsBarChart" class="bar-chart"></div>
      </div>
      <div class="section">
        <div class="section-title">🥧 Distribución de Response Codes</div>
        <div style="width: 300px; height: 300px; margin: 0 auto;">
          <canvas id="codesChart"></canvas>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">⏱️ Tiempo de Respuesta Promedio (ms)</div>
      <div id="avgTimeBarChart" class="bar-chart"></div>
    </div>

    {render_analysis('errors', '🔴 Análisis de Errores')}

    <div class="grid-2">
      <div class="analysis-box" style="border-left-color: var(--sqa-blue);">
        <div class="analysis-title">📝 Conclusiones</div>
        <div class="analysis-content">{ia_analysis.get('summary', 'Sin conclusiones disponibles.')}</div>
      </div>
      <div class="analysis-box" style="border-left-color: var(--success);">
        <div class="analysis-title">💡 Recomendaciones</div>
        <div class="analysis-content">{ia_analysis.get('recommendations', 'Sin recomendaciones disponibles.')}</div>
      </div>
    </div>

    <div class="footer">
      <div style="font-weight: bold; margin-bottom: 0.5rem;">Software Quality Assurance (SQA)</div>
      <div style="font-size: 0.85rem;">Powered by FastAPI + React + PostgreSQL + Gemini AI</div>
    </div>
  </div>

  <script>
    const statistics = {statistics_json};
    const series = {series_json};
    const codes = {codes_json};

    const total = statistics['Total'];
    document.getElementById('kpis').innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Total Requests</div>
        <div class="kpi-value">${{total.sampleCount.toLocaleString()}}</div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-label">Avg Response Time</div>
        <div class="kpi-value">${{total.meanResTime.toFixed(0)}} ms</div>
      </div>
      <div class="kpi-card error">
        <div class="kpi-label">Error Rate</div>
        <div class="kpi-value">${{total.errorPct.toFixed(2)}}%</div>
      </div>
      <div class="kpi-card warning">
        <div class="kpi-label">Throughput</div>
        <div class="kpi-value">${{total.throughput.toFixed(2)}} req/s</div>
      </div>
    `;

    let tableHTML = '<thead><tr><th>TRANSACCIÓN</th><th>MUESTRAS</th><th>ERRORES</th><th>% ERROR</th><th>PROMEDIO (MS)</th><th>MEDIANA (MS)</th><th>P90</th><th>P95</th><th>P99</th><th>MÍN</th><th>MÁX</th><th>THROUGHPUT</th></tr></thead><tbody>';
    Object.entries(statistics).forEach(([key, stat]) => {{
      tableHTML += `
        <tr class="${{key === 'Total' ? 'total-row' : ''}}">
          <td>${{stat.transaction}}</td>
          <td>${{stat.sampleCount.toLocaleString()}}</td>
          <td class="error-cell">${{stat.errorCount.toLocaleString()}}</td>
          <td class="error-cell">${{stat.errorPct.toFixed(2)}}%</td>
          <td>${{stat.meanResTime.toFixed(2)}}</td>
          <td>${{stat.medianResTime.toFixed(2)}}</td>
          <td>${{stat.pct1ResTime.toFixed(2)}}</td>
          <td>${{stat.pct2ResTime.toFixed(2)}}</td>
          <td>${{stat.pct3ResTime.toFixed(2)}}</td>
          <td>${{stat.minResTime.toFixed(2)}}</td>
          <td>${{stat.maxResTime.toFixed(2)}}</td>
          <td>${{stat.throughput.toFixed(2)}}</td>
        </tr>
      `;
    }});
    document.getElementById('statisticsTable').innerHTML = tableHTML + '</tbody>';

    const chartOptions = {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ type: 'time', time: {{ unit: 'second', displayFormats: {{ second: 'HH:mm:ss' }} }}, title: {{ display: true, text: 'Tiempo' }} }},
        y: {{ beginAtZero: true }}
      }}
    }};

    new Chart(document.getElementById('responseTimeChart'), {{
      type: 'line',
      data: {{ datasets: [{{ data: series.timeline.map(d => ({{ x: d.t, y: d.p95 }})), borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)', fill: true, tension: 0.4 }}] }},
      options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Response Time (ms)' }} }} }} }}
    }});

    new Chart(document.getElementById('throughputChart'), {{
      type: 'line',
      data: {{ datasets: [{{ data: series.timeline.map(d => ({{ x: d.t, y: d.tps }})), borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', fill: true, tension: 0.4 }}] }},
      options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Requests/sec' }} }} }} }}
    }});

    new Chart(document.getElementById('errorRateChart'), {{
      type: 'line',
      data: {{ datasets: [{{ data: series.timeline.map(d => ({{ x: d.t, y: d.err }})), borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: true, tension: 0.4 }}] }},
      options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Error Rate (%)' }} }} }} }}
    }});

    new Chart(document.getElementById('threadsChart'), {{
      type: 'line',
      data: {{ datasets: [{{ data: series.timeline.map(d => ({{ x: d.t, y: d.threads }})), borderColor: '#ec4899', backgroundColor: 'rgba(236, 72, 153, 0.1)', fill: true, tension: 0.4 }}] }},
      options: {{ ...chartOptions, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Threads' }} }} }} }}
    }});

    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
    new Chart(document.getElementById('responseByLabelChart'), {{
      type: 'line',
      data: {{ datasets: series.response_times_by_label.map((item, idx) => ({{ label: item.label, data: item.data.map(d => ({{ x: d.t, y: d.value }})), borderColor: colors[idx % colors.length], tension: 0.4 }})) }},
      options: {{ ...chartOptions, plugins: {{ legend: {{ display: true, position: 'top' }} }}, scales: {{ ...chartOptions.scales, y: {{ ...chartOptions.scales.y, title: {{ display: true, text: 'Response Time (ms)' }} }} }} }}
    }});

    const errorsChart = document.getElementById('errorsBarChart');
    const statsWithErrors = Object.values(statistics).filter(s => s.errorCount > 0 && s.transaction !== 'Total');
    const maxErrors = Math.max(...statsWithErrors.map(s => s.errorCount));
    statsWithErrors.forEach(stat => {{
      const width = (stat.errorCount / maxErrors) * 100;
      errorsChart.innerHTML += `
        <div class="bar">
          <div class="bar-label">${{stat.transaction}}</div>
          <div class="bar-container">
            <div class="bar-fill" style="width: ${{width}}%; background: linear-gradient(to right, #ef4444, #dc2626);"></div>
            <div class="bar-value">${{stat.errorCount.toLocaleString()}} (${{stat.errorPct.toFixed(1)}}%)</div>
          </div>
        </div>
      `;
    }});

    const codesTotal = codes.reduce((sum, c) => sum + c.count, 0);
    new Chart(document.getElementById('codesChart'), {{
      type: 'pie',
      data: {{
        labels: codes.map(c => c.code),
        datasets: [{{ data: codes.map(c => c.count), backgroundColor: ['#10b981', '#3b82f6', '#f97316', '#ef4444'] }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: true,
        plugins: {{
          legend: {{ position: 'bottom' }},
          tooltip: {{ callbacks: {{ label: (ctx) => `${{ctx.label}}: ${{ctx.parsed.toLocaleString()}} (${{(ctx.parsed/codesTotal*100).toFixed(1)}}%)` }} }}
        }}
      }}
    }});

    const avgTimeChart = document.getElementById('avgTimeBarChart');
    const statsArray = Object.values(statistics).filter(s => s.transaction !== 'Total');
    const maxTime = Math.max(...statsArray.map(s => s.meanResTime));
    statsArray.forEach(stat => {{
      const width = (stat.meanResTime / maxTime) * 100;
      avgTimeChart.innerHTML += `
        <div class="bar">
          <div class="bar-label">${{stat.transaction}}</div>
          <div class="bar-container">
            <div class="bar-fill" style="width: ${{width}}%; background: linear-gradient(to right, #10b981, #059669);"></div>
            <div class="bar-value">${{stat.meanResTime.toFixed(0)}} ms</div>
          </div>
        </div>
      `;
    }});
  </script>
</body>
</html>"""