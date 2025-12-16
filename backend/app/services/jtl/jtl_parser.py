"""
Parser JTL - VERSIÓN DEFINITIVA CORREGIDA CON TODOS LOS CHARTS
"""
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class JTLParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df = None
    
    def parse(self) -> Tuple[pd.DataFrame, Dict]:
        """Parse JTL y calcular todas las métricas"""
        # Leer CSV
        self.df = pd.read_csv(self.file_path)
        
        # DEBUG: Imprimir columnas detectadas
        logger.debug(f"Columnas en JTL: {list(self.df.columns)}")
        
        # Convertir timestamp a datetime
        self.df['timestamp'] = pd.to_datetime(self.df['timeStamp'], unit='ms')
        
        # Convertir success a boolean
        if 'success' in self.df.columns:
            self.df['success'] = self.df['success'].astype(str).str.lower() == 'true'
        
        # Calcular métricas
        metrics = self._calculate_metrics()
        
        return self.df, metrics
    
    def _calculate_metrics(self) -> Dict:
        """Calcular TODAS las métricas del reporte"""
        
        # Métricas básicas
        total_requests = len(self.df)
        total_errors = len(self.df[~self.df['success']])
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        # Tiempos de respuesta
        elapsed_times = self.df['elapsed']
        avg_response_time = elapsed_times.mean()
        median_response_time = elapsed_times.median()
        min_response_time = elapsed_times.min()
        max_response_time = elapsed_times.max()
        
        # Percentiles
        p50 = elapsed_times.quantile(0.50)
        p90 = elapsed_times.quantile(0.90)
        p95 = elapsed_times.quantile(0.95)
        p99 = elapsed_times.quantile(0.99)
        
        # Duración y throughput
        start_time = self.df['timestamp'].min()
        end_time = self.df['timestamp'].max()
        duration_seconds = (end_time - start_time).total_seconds()
        throughput = total_requests / duration_seconds if duration_seconds > 0 else 0
        
        # Latencia
        avg_latency = self.df['Latency'].mean() if 'Latency' in self.df.columns else 0
        
        # KB/s
        total_bytes_received = self.df['bytes'].sum() if 'bytes' in self.df.columns else 0
        total_bytes_sent = self.df['sentBytes'].sum() if 'sentBytes' in self.df.columns else 0
        kb_per_sec_received = (total_bytes_received / 1024) / duration_seconds if duration_seconds > 0 else 0
        kb_per_sec_sent = (total_bytes_sent / 1024) / duration_seconds if duration_seconds > 0 else 0
        
        return {
            'total_requests': int(total_requests),
            'total_errors': int(total_errors),
            'error_rate': float(error_rate),
            'avg_response_time': float(avg_response_time),
            'median_response_time': float(median_response_time),
            'min_response_time': float(min_response_time),
            'max_response_time': float(max_response_time),
            'p50_response_time': float(p50),
            'p90_response_time': float(p90),
            'p95_response_time': float(p95),
            'p99_response_time': float(p99),
            'throughput': float(throughput),
            'avg_latency': float(avg_latency),
            'kb_per_sec_received': float(kb_per_sec_received),
            'kb_per_sec_sent': float(kb_per_sec_sent),
            'start_time': start_time,
            'end_time': end_time,
            'duration_seconds': float(duration_seconds)
        }
    
    def get_summary_table_data(self) -> pd.DataFrame:
        """Generar datos para Reporte Resumen"""
        summary_list = []
        
        # Calcular duración total
        duration = (self.df['timestamp'].max() - self.df['timestamp'].min()).total_seconds()
        if duration == 0:
            duration = 1  # Evitar división por cero
        
        # Verificar qué columnas de bytes existen
        bytes_col = 'bytes' if 'bytes' in self.df.columns else None
        sent_bytes_col = 'sentBytes' if 'sentBytes' in self.df.columns else None
        
        for label in self.df['label'].unique():
            label_df = self.df[self.df['label'] == label]
            
            # KB recibidos y enviados
            kb_received = 0
            kb_sent = 0
            
            if bytes_col:
                total_bytes = label_df[bytes_col].sum()
                kb_received = total_bytes / 1024
                logger.debug(f"{label}: bytes={total_bytes}, kb_received={kb_received}")
            
            if sent_bytes_col:
                total_sent = label_df[sent_bytes_col].sum()
                kb_sent = total_sent / 1024
                logger.debug(f"{label}: sentBytes={total_sent}, kb_sent={kb_sent}")
            
            # Calcular estadísticas
            summary_list.append({
                'label': label,
                'muestras': len(label_df),
                'promedio': label_df['elapsed'].mean(),
                'mediana': label_df['elapsed'].median(),
                'p90': label_df['elapsed'].quantile(0.90),
                'p95': label_df['elapsed'].quantile(0.95),
                'p99': label_df['elapsed'].quantile(0.99),
                'min': label_df['elapsed'].min(),
                'max': label_df['elapsed'].max(),
                'errores': len(label_df[~label_df['success']]),
                'tasa_error': (len(label_df[~label_df['success']]) / len(label_df) * 100) if len(label_df) > 0 else 0,
                'kb_received': round(kb_received, 2),
                'kb_sent': round(kb_sent, 2)
            })
        
        summary = pd.DataFrame(summary_list)
        
        # Calcular rendimiento
        summary['rendimiento'] = (summary['muestras'] / duration).round(2) if duration > 0 else 0
        
        return summary
    
    def get_timeline_data(self, interval_seconds: int = 1) -> pd.DataFrame:
        """Timeline con múltiples métricas - VERSIÓN CORREGIDA"""
        # Crear time buckets
        self.df['time_bucket'] = self.df['timestamp'].dt.floor(f'{interval_seconds}S')
        
        # Agrupar por tiempo
        timeline = self.df.groupby('time_bucket').agg({
            'elapsed': 'mean',
            'Latency': 'mean' if 'Latency' in self.df.columns else 'count',
            'label': 'count'
        }).reset_index()
        
        # Calcular error rate por bucket
        errors_per_bucket = self.df[~self.df['success']].groupby('time_bucket').size()
        total_per_bucket = self.df.groupby('time_bucket').size()
        
        timeline['error_rate'] = 0.0
        for idx, row in timeline.iterrows():
            bucket = row['time_bucket']
            if bucket in errors_per_bucket.index:
                timeline.at[idx, 'error_rate'] = (errors_per_bucket[bucket] / total_per_bucket[bucket] * 100)
        
        # Active threads
        timeline['active_threads'] = 1
        if 'allThreads' in self.df.columns:
            threads_per_bucket = self.df.groupby('time_bucket')['allThreads'].max()
            for idx, row in timeline.iterrows():
                bucket = row['time_bucket']
                if bucket in threads_per_bucket.index:
                    timeline.at[idx, 'active_threads'] = threads_per_bucket[bucket]
        
        # Renombrar columnas
        timeline.columns = ['timestamp', 'avg_response_time', 'avg_latency', 'throughput', 'error_rate', 'active_threads']
        
        return timeline
    
    def get_response_code_distribution(self) -> pd.DataFrame:
        """Distribución de códigos para pie chart"""
        codes = self.df['responseCode'].value_counts().reset_index()
        codes.columns = ['responseCode', 'count']
        return codes
    
    def get_all_charts_data(self, interval_seconds: int = 10) -> Dict:
        """
        ✅ MÉTODO CORREGIDO - Obtener datos para TODOS los gráficos del dashboard
        Retorna 10 datasets completos
        """
        
        logger.info(f"🔧 Generando charts data con intervalo de {interval_seconds}s")
        
        # 1. Timeline general (con TODAS las métricas)
        timeline_df = self.get_timeline_data(interval_seconds)
        logger.debug(f"Timeline generado: {len(timeline_df)} puntos")
        
        # 2. Response times por transacción (multi-línea)
        response_times_by_label = []
        for label in self.df['label'].unique():
            label_df = self.df[self.df['label'] == label].copy()
            label_df['time_bucket'] = label_df['timestamp'].dt.floor(f'{interval_seconds}S')
            
            label_timeline = label_df.groupby('time_bucket')['elapsed'].mean().reset_index()
            label_timeline.columns = ['timestamp', 'value']
            label_timeline['label'] = label
            
            response_times_by_label.append(label_timeline)
        
        logger.debug(f"Response times by label: {len(response_times_by_label)} labels")
        
        # 3. Throughput timeline (del timeline principal)
        throughput_timeline = timeline_df[['timestamp', 'throughput']].copy()
        logger.debug(f"Throughput timeline: {len(throughput_timeline)} puntos")
        
        # 4. Latency timeline (del timeline principal)
        latency_timeline = timeline_df[['timestamp', 'avg_latency']].copy()
        logger.debug(f"Latency timeline: {len(latency_timeline)} puntos")
        
        # 5. Error rate timeline (del timeline principal)
        error_rate_timeline = timeline_df[['timestamp', 'error_rate']].copy()
        logger.debug(f"Error rate timeline: {len(error_rate_timeline)} puntos")
        
        # 6. Active threads timeline (del timeline principal)
        active_threads_timeline = timeline_df[['timestamp', 'active_threads']].copy()
        logger.debug(f"Active threads timeline: {len(active_threads_timeline)} puntos")
        
        # 7. Response codes per second
        codes_per_second = []
        for code in self.df['responseCode'].unique():
            code_df = self.df[self.df['responseCode'] == code].copy()
            code_df['time_bucket'] = code_df['timestamp'].dt.floor(f'{interval_seconds}S')
            
            code_timeline = code_df.groupby('time_bucket').size().reset_index()
            code_timeline.columns = ['timestamp', 'value']
            code_timeline['value'] = code_timeline['value'] / interval_seconds
            code_timeline['code'] = str(code)
            
            codes_per_second.append(code_timeline)
        
        logger.debug(f"Codes per second: {len(codes_per_second)} códigos")
        
        # 8. Transactions per second por label
        tps_by_label = []
        for label in self.df['label'].unique():
            label_df = self.df[self.df['label'] == label].copy()
            label_df['time_bucket'] = label_df['timestamp'].dt.floor(f'{interval_seconds}S')
            
            label_tps = label_df.groupby('time_bucket').size().reset_index()
            label_tps.columns = ['timestamp', 'value']
            label_tps['value'] = label_tps['value'] / interval_seconds
            label_tps['label'] = label
            
            tps_by_label.append(label_tps)
        
        logger.debug(f"TPS by label: {len(tps_by_label)} labels")
        
        # ✅ RETORNAR ESTRUCTURA COMPLETA CON 10 DATASETS
        result = {
            'timeline': timeline_df,
            'response_times_by_label': response_times_by_label,
            'throughput_timeline': throughput_timeline,
            'latency_timeline': latency_timeline,
            'error_rate_timeline': error_rate_timeline,
            'active_threads_timeline': active_threads_timeline,
            'codes_per_second': codes_per_second,
            'tps_by_label': tps_by_label,
            # Estos 2 adicionales se generan en upload.py
            # 'by_label': [],  # Se calcula con get_summary_table_data()
            # 'response_codes': {}  # Se calcula con get_response_code_distribution()
        }
        
        logger.info(f"✅ Charts data generado exitosamente: {len(result)} datasets principales")
        return result