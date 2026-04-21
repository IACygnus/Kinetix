"""
Locust CSV parser — normalizes Locust output to JTL-compatible DataFrame.
Supports both detailed request CSVs and aggregated stats CSVs.
"""
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def parse_locust_csv(file_content: bytes) -> pd.DataFrame:
    """
    Parse Locust CSV and normalize to JTL-compatible format.
    Auto-detects whether it's a detailed request CSV or aggregated stats CSV.
    """
    df = pd.read_csv(BytesIO(file_content))
    columns_lower = {c.lower().strip(): c for c in df.columns}

    if 'response time' in columns_lower or 'response_time' in columns_lower:
        logger.info("Detected Locust detailed request CSV")
        return _parse_locust_requests(df, columns_lower)
    elif 'request count' in columns_lower or '# requests' in columns_lower:
        logger.info("Detected Locust aggregated stats CSV")
        return _parse_locust_stats(df, columns_lower)
    else:
        raise ValueError(
            f"Formato CSV de Locust no reconocido. "
            f"Columnas: {list(df.columns)}"
        )


def _parse_locust_requests(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Parse detailed per-request Locust CSV."""
    normalized = pd.DataFrame()

    ts_col = col_map.get('timestamp', col_map.get('start time', col_map.get('start_time', '')))
    if ts_col:
        normalized['timeStamp'] = (df[ts_col] * 1000).astype('int64')
    else:
        normalized['timeStamp'] = pd.Series(range(len(df))) * 100 + int(pd.Timestamp.now().timestamp() * 1000)

    rt_col = col_map.get('response time', col_map.get('response_time', col_map.get('elapsed time', '')))
    normalized['elapsed'] = df[rt_col].fillna(0).astype('int32') if rt_col else 0

    name_col = col_map.get('name', col_map.get('request', ''))
    type_col = col_map.get('type', col_map.get('method', ''))
    if name_col and type_col:
        normalized['label'] = df[type_col].astype(str) + ' ' + df[name_col].astype(str)
    elif name_col:
        normalized['label'] = df[name_col].astype(str)
    else:
        normalized['label'] = 'Unknown'

    success_col = col_map.get('success', col_map.get('status', ''))
    if success_col:
        normalized['success'] = df[success_col].astype(str).str.lower().isin(['true', '1', 'ok', 'success'])
    else:
        normalized['success'] = True

    code_col = col_map.get('response code', col_map.get('status code', col_map.get('status_code', '')))
    if code_col:
        normalized['responseCode'] = df[code_col].astype(str)
    else:
        normalized['responseCode'] = normalized['success'].map({True: '200', False: '500'})

    len_col = col_map.get('response length', col_map.get('content size', col_map.get('content_size', '')))
    normalized['bytes'] = df[len_col].fillna(0).astype('int32') if len_col else 0
    normalized['sentBytes'] = 0
    normalized['Latency'] = normalized['elapsed']
    normalized['allThreads'] = 1
    normalized['threadName'] = 'Locust-User'

    logger.info(f"Locust requests parsed: {len(normalized)} rows")
    return normalized


def _parse_locust_stats(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Parse aggregated Locust stats CSV — generates synthetic rows."""
    records = []
    base_time = int(pd.Timestamp.now().timestamp() * 1000)

    name_col = col_map.get('name', '')
    type_col = col_map.get('type', '')
    count_col = col_map.get('request count', col_map.get('# requests', ''))
    fail_col = col_map.get('failure count', col_map.get('# failures', ''))
    avg_col = col_map.get('average response time', col_map.get('average', ''))

    if not name_col or not count_col:
        raise ValueError("CSV de Locust stats no tiene columnas 'Name' y 'Request Count'")

    row_offset = 0
    for _, row in df.iterrows():
        label = f"{row.get(type_col, '')} {row[name_col]}".strip() if type_col else str(row[name_col])
        if label.lower() in ('aggregated', 'total', ''):
            continue

        count = int(row[count_col]) if pd.notna(row[count_col]) else 0
        failures = int(row[fail_col]) if fail_col and pd.notna(row.get(fail_col)) else 0
        avg_rt = float(row[avg_col]) if avg_col and pd.notna(row.get(avg_col)) else 0
        successes = max(count - failures, 0)

        for i in range(min(successes, 1000)):
            records.append({
                'timeStamp': base_time + (row_offset + i) * 100,
                'elapsed': int(avg_rt),
                'label': label,
                'responseCode': '200',
                'success': True,
                'bytes': 0,
                'sentBytes': 0,
                'Latency': int(avg_rt),
                'allThreads': 1,
                'threadName': 'Locust-User',
            })
        for i in range(min(failures, 100)):
            records.append({
                'timeStamp': base_time + (row_offset + successes + i) * 100,
                'elapsed': int(avg_rt),
                'label': label,
                'responseCode': '500',
                'success': False,
                'bytes': 0,
                'sentBytes': 0,
                'Latency': int(avg_rt),
                'allThreads': 1,
                'threadName': 'Locust-User',
            })
        row_offset += count

    result = pd.DataFrame(records)
    logger.info(f"Locust stats parsed: {len(result)} synthetic rows from {len(df)} aggregated entries")
    return result
