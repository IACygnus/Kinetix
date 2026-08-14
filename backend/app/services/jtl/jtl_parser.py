"""
Parser JTL v2.0 - Multi-JTL consolidation + redirect separation
"""
import re
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
import logging

logger = logging.getLogger(__name__)


def validate_jtl_compatibility(file_paths: List[str]) -> Dict:
    """
    Valida que multiples archivos JTL sean compatibles para consolidar.
    Retorna errors, warnings y summary.
    """
    result = {"errors": [], "warnings": [], "compatible": True, "summary": None}

    if len(file_paths) < 2:
        result["summary"] = {"total_files": len(file_paths)}
        return result

    dataframes_info = []
    for path in file_paths:
        try:
            df = pd.read_csv(path, nrows=100)  # Solo leer 100 filas para validar
            df_full_ts = pd.read_csv(path, usecols=['timeStamp'])

            info = {
                "file": Path(path).name,
                "columns": set(df.columns),
                "start_time": pd.to_datetime(df_full_ts['timeStamp'].min(), unit='ms'),
                "end_time": pd.to_datetime(df_full_ts['timeStamp'].max(), unit='ms'),
                "date": pd.to_datetime(df_full_ts['timeStamp'].min(), unit='ms').date(),
                "labels": set(df['label'].unique()),
                "row_count": len(df_full_ts),
            }
            dataframes_info.append(info)
        except Exception as e:
            result["errors"].append(f"Error leyendo {Path(path).name}: {str(e)}")
            result["compatible"] = False
            return result

    # 1. Verificar misma estructura de columnas
    base_columns = dataframes_info[0]["columns"]
    for info in dataframes_info[1:]:
        if info["columns"] != base_columns:
            missing = base_columns - info["columns"]
            extra = info["columns"] - base_columns
            msg = f"Estructura incompatible: {info['file']}"
            if missing:
                msg += f" - columnas faltantes: {missing}"
            if extra:
                msg += f" - columnas extra: {extra}"
            result["errors"].append(msg)
            result["compatible"] = False

    # 2. Verificar misma fecha de ejecucion
    base_date = dataframes_info[0]["date"]
    for info in dataframes_info[1:]:
        if info["date"] != base_date:
            result["warnings"].append(
                f"ALERTA DE COMPATIBILIDAD: {info['file']} tiene fecha "
                f"{info['date']} diferente a {dataframes_info[0]['file']} "
                f"con fecha {base_date}. "
                f"Seguro que son de la misma ejecucion?"
            )

    # 3. Verificar que los rangos de tiempo se solapan
    all_starts = [i["start_time"] for i in dataframes_info]
    all_ends = [i["end_time"] for i in dataframes_info]
    max_start_diff = (max(all_starts) - min(all_starts)).total_seconds()
    if max_start_diff > 300:
        result["warnings"].append(
            f"Los archivos tienen {max_start_diff:.0f}s de diferencia "
            f"en hora de inicio. Verificar que son de la misma ejecucion."
        )

    # 4. Summary
    result["summary"] = {
        "total_files": len(file_paths),
        "total_samples": sum(i["row_count"] for i in dataframes_info),
        "date_range": f"{min(all_starts)} -> {max(all_ends)}",
        "unique_labels": len(set().union(*[i['labels'] for i in dataframes_info])),
    }

    return result


def classify_transactions(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Set[str]]:
    """
    Separa transacciones principales de redirecciones.

    Patron de redireccion: 'TransactionName-N' donde:
    - N es un digito (0, 1, 2...)
    - 'TransactionName' existe como label principal en el dataset

    Retorna: (df_main, df_redirects, redirect_labels_set)
    """
    all_labels = set(df['label'].unique())
    redirect_labels: Set[str] = set()

    for label in all_labels:
        match = re.match(r'^(.+)-(\d+)$', label)
        if match:
            parent_label = match.group(1)
            if parent_label in all_labels:
                redirect_labels.add(label)

    df_main = df[~df['label'].isin(redirect_labels)].copy()
    df_redirects = df[df['label'].isin(redirect_labels)].copy()

    logger.info(
        f"Clasificacion: {len(all_labels)} labels totales, "
        f"{len(redirect_labels)} redirecciones detectadas, "
        f"{len(all_labels) - len(redirect_labels)} principales"
    )

    return df_main, df_redirects, redirect_labels


def _is_xml_jtl(file_path: str) -> bool:
    """Detecta si un archivo JTL está en formato XML."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                return line.startswith('<?xml') or line.startswith('<testResults')
    except Exception:
        return False
    return False


def _parse_xml_jtl_to_df(file_path: str) -> pd.DataFrame:
    """
    Parsea un archivo JTL en formato XML y retorna un DataFrame
    con las MISMAS columnas que pd.read_csv() produciría para un
    JTL en formato CSV.
    Solo parsea httpSample/sample de nivel superior (depth=1).
    """
    ATTR_MAP = {
        'ts': 'timeStamp',
        't': 'elapsed',
        'lb': 'label',
        'rc': 'responseCode',
        'rm': 'responseMessage',
        'tn': 'threadName',
        'dt': 'dataType',
        's': 'success',
        'by': 'bytes',
        'sby': 'sentBytes',
        'ng': 'grpThreads',
        'na': 'allThreads',
        'lt': 'Latency',
        'it': 'IdleTime',
        'ct': 'Connect',
    }

    rows = []
    depth = 0

    for event, elem in ET.iterparse(file_path, events=('start', 'end')):
        if event == 'start':
            if elem.tag in ('httpSample', 'sample'):
                depth += 1
        elif event == 'end':
            if elem.tag in ('httpSample', 'sample'):
                if depth == 1:
                    row = {}
                    for xml_attr, csv_col in ATTR_MAP.items():
                        row[csv_col] = elem.get(xml_attr, '')

                    s_val = elem.get('s', 'true')
                    row['success'] = s_val.lower() if s_val else 'true'

                    row['failureMessage'] = ''
                    row['URL'] = elem.get('u', '')

                    rows.append(row)

                depth -= 1
                elem.clear()

    if not rows:
        raise ValueError("No se encontraron samples en el archivo XML JTL")

    df = pd.DataFrame(rows)

    numeric_cols = ['timeStamp', 'elapsed', 'bytes', 'sentBytes',
                    'grpThreads', 'allThreads', 'Latency', 'IdleTime', 'Connect']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df


class JTLParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df: Optional[pd.DataFrame] = None
        self.df_main: Optional[pd.DataFrame] = None
        self.df_redirects: Optional[pd.DataFrame] = None
        self.redirect_labels: Set[str] = set()

    def parse(self) -> Tuple[pd.DataFrame, Dict]:
        """Parse JTL y calcular todas las metricas"""
        if _is_xml_jtl(self.file_path):
            self.df = _parse_xml_jtl_to_df(self.file_path)
        else:
            self.df = pd.read_csv(self.file_path)
        logger.debug(f"Columnas en JTL: {list(self.df.columns)}")

        # Convertir timestamp a datetime
        self.df['timestamp'] = pd.to_datetime(self.df['timeStamp'], unit='ms')

        # Convertir success a boolean
        if 'success' in self.df.columns:
            self.df['success'] = self.df['success'].astype(str).str.lower() == 'true'

        # Clasificar transacciones
        self.df_main, self.df_redirects, self.redirect_labels = classify_transactions(self.df)

        # Calcular metricas sobre transacciones principales
        metrics = self._calculate_metrics(self.df_main)

        # Agregar info de redirecciones a metricas
        metrics['total_redirects'] = len(self.df_redirects)
        metrics['redirect_labels'] = sorted(list(self.redirect_labels))
        metrics['total_all_samples'] = len(self.df)
        metrics['total_main_samples'] = len(self.df_main)

        return self.df, metrics

    @staticmethod
    def parse_multiple(file_paths: List[str]) -> Tuple[pd.DataFrame, Dict]:
        """Consolida multiples JTL en un unico DataFrame"""
        dataframes = []
        for path in file_paths:
            df = pd.read_csv(path)
            df['source_file'] = Path(path).name
            dataframes.append(df)

        combined = pd.concat(dataframes, ignore_index=True)
        combined.sort_values('timeStamp', inplace=True)
        combined.reset_index(drop=True, inplace=True)

        # Convertir timestamp a datetime
        combined['timestamp'] = pd.to_datetime(combined['timeStamp'], unit='ms')

        # Convertir success a boolean
        if 'success' in combined.columns:
            combined['success'] = combined['success'].astype(str).str.lower() == 'true'

        # Tiempo transcurrido desde el inicio del dataset consolidado
        consolidated_start = combined['timeStamp'].min()
        combined['elapsed_from_start'] = combined['timeStamp'] - consolidated_start
        combined['elapsed_seconds'] = combined['elapsed_from_start'] / 1000

        # Crear parser temporal para calcular metricas
        parser = JTLParser.__new__(JTLParser)
        parser.df = combined
        parser.file_path = file_paths[0]

        # Clasificar transacciones
        parser.df_main, parser.df_redirects, parser.redirect_labels = classify_transactions(combined)

        # Calcular metricas sobre transacciones principales
        metrics = parser._calculate_metrics(parser.df_main)
        metrics['total_redirects'] = len(parser.df_redirects)
        metrics['redirect_labels'] = sorted(list(parser.redirect_labels))
        metrics['total_all_samples'] = len(combined)
        metrics['total_main_samples'] = len(parser.df_main)
        metrics['source_files'] = [Path(p).name for p in file_paths]

        return combined, metrics, parser

    def _calculate_metrics(self, df: Optional[pd.DataFrame] = None) -> Dict:
        """Calcular TODAS las metricas del reporte"""
        if df is None:
            df = self.df_main if self.df_main is not None else self.df

        total_requests = len(df)
        total_errors = len(df[~df['success']])
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

        elapsed_times = df['elapsed']
        avg_response_time = elapsed_times.mean()
        median_response_time = elapsed_times.median()
        min_response_time = elapsed_times.min()
        max_response_time = elapsed_times.max()

        p50 = elapsed_times.quantile(0.50)
        p90 = elapsed_times.quantile(0.90)
        p95 = elapsed_times.quantile(0.95)
        p99 = elapsed_times.quantile(0.99)

        start_time = df['timestamp'].min()
        end_time = df['timestamp'].max()
        duration_seconds = (end_time - start_time).total_seconds()
        throughput = total_requests / duration_seconds if duration_seconds > 0 else 0

        avg_latency = df['Latency'].mean() if 'Latency' in df.columns else 0

        total_bytes_received = df['bytes'].sum() if 'bytes' in df.columns else 0
        total_bytes_sent = df['sentBytes'].sum() if 'sentBytes' in df.columns else 0
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
            'duration_seconds': float(duration_seconds),
        }

    def get_summary_table_data(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Generar datos para Reporte Resumen"""
        if df is None:
            df = self.df_main if self.df_main is not None else self.df

        summary_list = []
        duration = (df['timestamp'].max() - df['timestamp'].min()).total_seconds()
        if duration == 0:
            duration = 1

        bytes_col = 'bytes' if 'bytes' in df.columns else None
        sent_bytes_col = 'sentBytes' if 'sentBytes' in df.columns else None

        for label in df['label'].unique():
            label_df = df[df['label'] == label]

            kb_received = 0.0
            kb_sent = 0.0
            if bytes_col:
                kb_received = label_df[bytes_col].sum() / 1024
            if sent_bytes_col:
                kb_sent = label_df[sent_bytes_col].sum() / 1024

            n_samples = len(label_df)
            n_errors = len(label_df[~label_df['success']])

            summary_list.append({
                'label': label,
                'muestras': n_samples,
                'promedio': label_df['elapsed'].mean(),
                'mediana': label_df['elapsed'].median(),
                'p90': label_df['elapsed'].quantile(0.90),
                'p95': label_df['elapsed'].quantile(0.95),
                'p99': label_df['elapsed'].quantile(0.99),
                'min': label_df['elapsed'].min(),
                'max': label_df['elapsed'].max(),
                'errores': n_errors,
                'tasa_error': (n_errors / n_samples * 100) if n_samples > 0 else 0,
                'kb_received': round(kb_received, 2),
                'kb_sent': round(kb_sent, 2),
            })

        summary = pd.DataFrame(summary_list)
        summary['rendimiento'] = (summary['muestras'] / duration).round(2) if duration > 0 else 0
        return summary

    def get_redirect_summary_data(self) -> Optional[pd.DataFrame]:
        """Generar datos de resumen para redirecciones"""
        if self.df_redirects is None or len(self.df_redirects) == 0:
            return None
        return self.get_summary_table_data(self.df_redirects)

    def get_timeline_data(self, interval_seconds: int = 1) -> pd.DataFrame:
        """Timeline con multiples metricas"""
        df = self.df
        df_copy = df.copy()
        df_copy['time_bucket'] = df_copy['timestamp'].dt.floor(f'{interval_seconds}s')

        timeline = df_copy.groupby('time_bucket').agg(
            avg_response_time=('elapsed', 'mean'),
            avg_latency=('Latency', 'mean') if 'Latency' in df_copy.columns else ('elapsed', 'count'),
            throughput=('label', 'count'),
        ).reset_index()

        # Recalculate avg_latency if Latency column wasn't available
        if 'Latency' not in df_copy.columns:
            timeline['avg_latency'] = 0.0

        # Error rate por bucket
        errors_per_bucket = df_copy[~df_copy['success']].groupby('time_bucket').size()
        total_per_bucket = df_copy.groupby('time_bucket').size()

        timeline['error_rate'] = 0.0
        for bucket in timeline['time_bucket']:
            if bucket in errors_per_bucket.index and bucket in total_per_bucket.index:
                rate = (errors_per_bucket[bucket] / total_per_bucket[bucket] * 100)
                timeline.loc[timeline['time_bucket'] == bucket, 'error_rate'] = rate

        # Active threads
        timeline['active_threads'] = 1
        if 'allThreads' in df_copy.columns:
            threads_per_bucket = df_copy.groupby('time_bucket')['allThreads'].max()
            for bucket in timeline['time_bucket']:
                if bucket in threads_per_bucket.index:
                    timeline.loc[timeline['time_bucket'] == bucket, 'active_threads'] = threads_per_bucket[bucket]

        timeline.rename(columns={'time_bucket': 'timestamp'}, inplace=True)
        return timeline

    def get_response_code_distribution(self) -> pd.DataFrame:
        """Distribucion de codigos para pie chart"""
        codes = self.df['responseCode'].value_counts().reset_index()
        codes.columns = ['responseCode', 'count']
        return codes

    def _calculate_adaptive_interval(self) -> int:
        """Calculate adaptive time bucket interval based on total sample count"""
        total_samples = len(self.df) if self.df is not None else 0
        duration = 0
        if self.df is not None and 'timestamp' in self.df.columns:
            duration = (self.df['timestamp'].max() - self.df['timestamp'].min()).total_seconds()

        if total_samples < 500:
            # Raw data - use 1s buckets
            return max(1, int(duration / max(total_samples, 1)))
        elif total_samples <= 5000:
            # 200 time buckets
            return max(1, int(duration / 200))
        elif total_samples <= 50000:
            # 500 time buckets
            return max(1, int(duration / 500))
        else:
            # 1000 time buckets
            return max(1, int(duration / 1000))

    def get_all_charts_data(self, interval_seconds: int = 10) -> Dict:
        """Obtener datos para TODOS los graficos del dashboard"""
        # Use adaptive interval for more granular data
        interval_seconds = self._calculate_adaptive_interval()
        logger.info(f"Generando charts data con intervalo adaptativo de {interval_seconds}s")

        # 1. Timeline general
        timeline_df = self.get_timeline_data(interval_seconds)

        # 2. Response times por transaccion (solo principales)
        # GRAF1-A: SOLO esta serie usa intervalo fijo de 1s + agregacion dual
        # (value=promedio, value_max=maximo) para que los picos no se suavicen.
        # El resto de series conserva el intervalo adaptativo.
        RT_INTERVAL_SECONDS = 1
        df_for_charts = self.df_main if self.df_main is not None and len(self.df_main) > 0 else self.df
        response_times_by_label = []
        for label in df_for_charts['label'].unique():
            label_df = df_for_charts[df_for_charts['label'] == label].copy()
            label_df['time_bucket'] = label_df['timestamp'].dt.floor(f'{RT_INTERVAL_SECONDS}s')
            label_timeline = label_df.groupby('time_bucket')['elapsed'].agg(['mean', 'max']).reset_index()
            label_timeline.columns = ['timestamp', 'value', 'value_max']
            label_timeline['label'] = label
            response_times_by_label.append(label_timeline)

        # 3-6. From timeline
        throughput_timeline = timeline_df[['timestamp', 'throughput']].copy()
        latency_timeline = timeline_df[['timestamp', 'avg_latency']].copy()
        error_rate_timeline = timeline_df[['timestamp', 'error_rate']].copy()
        active_threads_timeline = timeline_df[['timestamp', 'active_threads']].copy()

        # 7. Response codes per second
        codes_per_second = []
        for code in self.df['responseCode'].unique():
            code_df = self.df[self.df['responseCode'] == code].copy()
            code_df['time_bucket'] = code_df['timestamp'].dt.floor(f'{interval_seconds}s')
            code_timeline = code_df.groupby('time_bucket').size().reset_index()
            code_timeline.columns = ['timestamp', 'value']
            code_timeline['value'] = code_timeline['value'] / interval_seconds
            code_timeline['code'] = str(code)
            codes_per_second.append(code_timeline)

        # 8. TPS por label (solo principales)
        tps_by_label = []
        for label in df_for_charts['label'].unique():
            label_df = df_for_charts[df_for_charts['label'] == label].copy()
            label_df['time_bucket'] = label_df['timestamp'].dt.floor(f'{interval_seconds}s')
            label_tps = label_df.groupby('time_bucket').size().reset_index()
            label_tps.columns = ['timestamp', 'value']
            label_tps['value'] = label_tps['value'] / interval_seconds
            label_tps['label'] = label
            tps_by_label.append(label_tps)

        result = {
            'timeline': timeline_df,
            'response_times_by_label': response_times_by_label,
            'throughput_timeline': throughput_timeline,
            'latency_timeline': latency_timeline,
            'error_rate_timeline': error_rate_timeline,
            'active_threads_timeline': active_threads_timeline,
            'codes_per_second': codes_per_second,
            'tps_by_label': tps_by_label,
        }

        logger.info(f"Charts data generado: {len(result)} datasets principales")
        return result
