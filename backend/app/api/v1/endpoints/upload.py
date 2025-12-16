"""
Endpoints de JTL Upload y Análisis - CORREGIDO CON VALIDACIÓN UUID
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import List
import uuid
import traceback
import logging

from app.db.session import get_db
from app.db.models.test import TestExecution
from app.services.jtl.jtl_parser import JTLParser
from app.services.ai.gemini import gemini_analyzer
from app.schemas.test import TestExecutionResponse, ChartData, TimelineData, LabelStats, TimeSeriesPoint

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=TestExecutionResponse)
async def upload_jtl(
    file: UploadFile = File(...),
    name: str = Query("Test Execution"),
    description: str = Query(""),
    acceptance_criteria: str = Query(""),
    db: AsyncSession = Depends(get_db)
):
    """Upload y procesar archivo JTL con criterios de aceptación opcionales"""
    
    # Validar extensión
    if not file.filename.endswith(('.jtl', '.csv')):
        raise HTTPException(status_code=400, detail="Solo archivos .jtl o .csv")
    
    # Guardar archivo
    upload_dir = Path("/app/uploads")
    upload_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_path = upload_dir / f"{timestamp}_{file.filename}"
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    try:
        # Parsear JTL
        parser = JTLParser(str(file_path))
        df, metrics = parser.parse()
        
        # Analizar con IA - ANÁLISIS GENERAL
        ai_results = gemini_analyzer.analyze_performance(metrics, acceptance_criteria)
        
        # Generar datos para análisis específicos
        summary_df = parser.get_summary_table_data()
        
        # Análisis de tabla resumen
        ai_analysis_summary = gemini_analyzer.analyze_summary_table(summary_df, metrics)
        
        # Análisis de errores
        errors_for_analysis = []
        for _, row in summary_df.iterrows():
            if row['errores'] > 0:
                errors_for_analysis.append({
                    'label': row['label'],
                    'count': int(row['errores']),
                    'code': '404/405',  # Simplificado
                    'message': 'Not Found / Method Not Allowed'
                })
        
        ai_analysis_errors = gemini_analyzer.analyze_errors(
            errors_for_analysis, 
            metrics['total_requests']
        )
        
        # Crear registro en BD - CON TODOS LOS ANÁLISIS
        execution = TestExecution(
            id=uuid.uuid4(),
            user_id=None,
            name=name,
            description=description,
            jtl_filename=file.filename,
            
            # Info del archivo
            start_time=metrics.get('start_time'),
            end_time=metrics.get('end_time'),
            duration_seconds=float(metrics.get('duration_seconds', 0)),
            
            # Métricas básicas
            total_requests=int(metrics['total_requests']),
            total_errors=int(metrics['total_errors']),
            error_rate=float(metrics['error_rate']),
            avg_response_time=float(metrics['avg_response_time']),
            median_response_time=float(metrics.get('median_response_time', 0)),
            min_response_time=float(metrics['min_response_time']),
            max_response_time=float(metrics['max_response_time']),
            p50_response_time=float(metrics['p50_response_time']),
            p90_response_time=float(metrics['p90_response_time']),
            p95_response_time=float(metrics['p95_response_time']),
            p99_response_time=float(metrics['p99_response_time']),
            throughput=float(metrics['throughput']),
            
            # Nuevas métricas
            avg_latency=float(metrics.get('avg_latency', 0)),
            kb_per_sec_received=float(metrics.get('kb_per_sec_received', 0)),
            kb_per_sec_sent=float(metrics.get('kb_per_sec_sent', 0)),
            
            # Análisis IA - TODOS LOS CAMPOS
            ai_analysis_summary=ai_analysis_summary,
            ai_analysis_errors=ai_analysis_errors,
            ai_recommendations=ai_results.get('recommendations', ''),
            
            # Los otros análisis se generarán bajo demanda o aquí si quieres
            ai_analysis_response_times='',
            ai_analysis_response_time_over_time='',
            ai_analysis_throughput='',
            ai_analysis_latency='',
            ai_analysis_error_rate='',
            ai_analysis_codes_per_second='',
            ai_analysis_transactions_per_second='',
            ai_analysis_active_threads='',
            
            execution_date=datetime.now()
        )
        
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        
        return execution
        
    except Exception as e:
        error_detail = f"Error procesando JTL: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        raise HTTPException(status_code=400, detail=f"Error procesando JTL: {str(e)}")

@router.get("/executions", response_model=List[TestExecutionResponse])
async def get_executions(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Listar ejecuciones"""
    result = await db.execute(
        select(TestExecution)
        .order_by(TestExecution.created_at.desc())
        .limit(limit)
    )
    executions = result.scalars().all()
    return executions

@router.get("/executions/{execution_id}", response_model=TestExecutionResponse)
async def get_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """Obtener ejecución específica"""
    
    # ✅ VALIDACIÓN DEL UUID
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError) as e:
        logger.error(f"UUID inválido en get_execution: {execution_id} - Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecución inválido. Se esperaba un UUID válido, se recibió: '{execution_id}'"
        )
    
    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    return execution

@router.get("/executions/{execution_id}/charts", response_model=ChartData)
async def get_execution_charts(execution_id: str, db: AsyncSession = Depends(get_db)):
    """Obtener datos para gráficos - CORREGIDO CON VALIDACIÓN"""
    
    # ✅ VALIDACIÓN EXPLÍCITA DEL UUID
    try:
        exec_uuid = uuid.UUID(execution_id)
        logger.info(f"📊 Solicitando charts para execution_id: {exec_uuid}")
    except (ValueError, AttributeError) as e:
        logger.error(f"❌ UUID inválido recibido: '{execution_id}' - Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecución inválido. Se esperaba un UUID válido, se recibió: '{execution_id}'"
        )
    
    # Verificar que la ejecución existe
    try:
        result = await db.execute(
            select(TestExecution).where(TestExecution.id == exec_uuid)
        )
        execution = result.scalar_one_or_none()
        
        if not execution:
            logger.warning(f"⚠️ Ejecución no encontrada: {exec_uuid}")
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró la ejecución con ID: {execution_id}"
            )
        
        logger.info(f"✅ Ejecución encontrada: {execution.name} (archivo: {execution.jtl_filename})")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Error buscando ejecución {exec_uuid}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando la ejecución: {str(e)}"
        )
    
    # Buscar archivo JTL original
    upload_dir = Path("/app/uploads")
    jtl_files = list(upload_dir.glob(f"*{execution.jtl_filename}"))
    
    if not jtl_files:
        logger.error(f"❌ Archivo JTL no encontrado: {execution.jtl_filename}")
        raise HTTPException(
            status_code=404,
            detail=f"Archivo JTL no encontrado: {execution.jtl_filename}"
        )
    
    logger.info(f"📁 Archivo JTL encontrado: {jtl_files[0]}")
    
    try:
        # Parsear de nuevo para obtener datos de gráficos
        parser = JTLParser(str(jtl_files[0]))
        df, _ = parser.parse()
        logger.info(f"📊 DataFrame parseado: {len(df)} filas")
        
        # Obtener TODOS los datos de gráficos
        charts_data = parser.get_all_charts_data(interval_seconds=10)
        logger.info(f"✅ Charts data generado con {len(charts_data)} datasets")
        
        # Timeline general (Response Time Over Time)
        timeline_df = charts_data['timeline']
        timeline = [
            TimelineData(
                timestamp=row['timestamp'].isoformat(),
                avg_response_time=float(row['avg_response_time']),
                request_count=int(row['throughput'])
            )
            for _, row in timeline_df.iterrows()
        ]
        logger.debug(f"Timeline: {len(timeline)} puntos")
        
        # By label stats (para tabla)
        summary_df = parser.get_summary_table_data()
        by_label = []
        for _, row in summary_df.iterrows():
            by_label.append(LabelStats(
                label=row['label'],
                count=int(row['muestras']),
                avg_time=float(row['promedio']),
                min_time=float(row['min']),
                max_time=float(row['max']),
                success_count=int(row['muestras'] - row['errores']),
                kb_received=float(row.get('kb_received', 0)),
                kb_sent=float(row.get('kb_sent', 0))
            ))
        logger.debug(f"By label: {len(by_label)} labels")
        
        # Response codes distribution (pie chart)
        codes_df = parser.get_response_code_distribution()
        response_codes = {
            str(row['responseCode']): int(row['count']) 
            for _, row in codes_df.iterrows()
        }
        logger.debug(f"Response codes: {response_codes}")
        
        # Response Times por Transacción
        response_times_by_label = []
        for label_df in charts_data['response_times_by_label']:
            for _, row in label_df.iterrows():
                response_times_by_label.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    label=row['label']
                ))
        logger.debug(f"Response times by label: {len(response_times_by_label)} puntos")
        
        # Throughput Timeline
        throughput_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['throughput'])
            )
            for _, row in timeline_df.iterrows()
        ]
        logger.debug(f"Throughput timeline: {len(throughput_timeline)} puntos")
        
        # Latency Timeline
        latency_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['avg_latency'])
            )
            for _, row in timeline_df.iterrows()
        ]
        logger.debug(f"Latency timeline: {len(latency_timeline)} puntos")
        
        # Error Rate Timeline
        error_rate_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['error_rate'])
            )
            for _, row in timeline_df.iterrows()
        ]
        logger.debug(f"Error rate timeline: {len(error_rate_timeline)} puntos")
        
        # Active Threads Timeline
        active_threads_timeline = [
            TimeSeriesPoint(
                timestamp=row['timestamp'].isoformat(),
                value=float(row['active_threads'])
            )
            for _, row in timeline_df.iterrows()
        ]
        logger.debug(f"Active threads timeline: {len(active_threads_timeline)} puntos")
        
        # Response Codes per Second
        codes_per_second = []
        for code_df in charts_data['codes_per_second']:
            for _, row in code_df.iterrows():
                codes_per_second.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    code=row['code']
                ))
        logger.debug(f"Codes per second: {len(codes_per_second)} puntos")
        
        # Transactions per Second por Label
        tps_by_label = []
        for tps_df in charts_data['tps_by_label']:
            for _, row in tps_df.iterrows():
                tps_by_label.append(TimeSeriesPoint(
                    timestamp=row['timestamp'].isoformat(),
                    value=float(row['value']),
                    label=row['label']
                ))
        logger.debug(f"TPS by label: {len(tps_by_label)} puntos")
        
        logger.info(f"🎉 Charts generados exitosamente para {exec_uuid}")
        
        return ChartData(
            timeline=timeline,
            by_label=by_label,
            response_codes=response_codes,
            response_times_by_label=response_times_by_label,
            throughput_timeline=throughput_timeline,
            latency_timeline=latency_timeline,
            error_rate_timeline=error_rate_timeline,
            codes_per_second=codes_per_second,
            tps_by_label=tps_by_label,
            active_threads_timeline=active_threads_timeline
        )
        
    except Exception as e:
        logger.exception(f"❌ Error generando charts para {exec_uuid}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando datos de gráficos: {str(e)}"
        )

# ====== ENDPOINT PARA ACTUALIZAR ANÁLISIS ======

class UpdateAnalysisRequest(BaseModel):
    """Modelo para actualizar análisis"""
    ai_analysis_summary: Optional[str] = None
    ai_analysis_errors: Optional[str] = None
    ai_analysis_response_times: Optional[str] = None
    ai_analysis_response_time_over_time: Optional[str] = None
    ai_analysis_throughput: Optional[str] = None
    ai_analysis_latency: Optional[str] = None
    ai_analysis_error_rate: Optional[str] = None
    ai_analysis_codes_per_second: Optional[str] = None
    ai_analysis_transactions_per_second: Optional[str] = None
    ai_analysis_active_threads: Optional[str] = None
    ai_recommendations: Optional[str] = None

@router.put("/executions/{execution_id}/analysis")
async def update_analysis(
    execution_id: str,
    data: UpdateAnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """Actualizar análisis IA editados"""
    
    # ✅ VALIDACIÓN DEL UUID
    try:
        exec_uuid = uuid.UUID(execution_id)
    except (ValueError, AttributeError) as e:
        logger.error(f"UUID inválido en update_analysis: {execution_id} - Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"ID de ejecución inválido. Se esperaba un UUID válido, se recibió: '{execution_id}'"
        )
    
    # Verificar que existe
    result = await db.execute(
        select(TestExecution).where(TestExecution.id == exec_uuid)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    
    # Actualizar campos no-null
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    
    if update_data:
        await db.execute(
            update(TestExecution)
            .where(TestExecution.id == exec_uuid)
            .values(**update_data)
        )
        await db.commit()
        logger.info(f"✅ Análisis actualizado para {exec_uuid}")
    
    return {"success": True, "message": "Análisis actualizado correctamente"}