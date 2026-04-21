"""
WAPT parser — normalizes WAPT CSV/XML output to JTL-compatible DataFrame.
Column detection is flexible to handle various WAPT versions.
"""
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


def parse_wapt_csv(file_content: bytes) -> pd.DataFrame:
    """Parse WAPT CSV results and normalize to JTL-compatible format."""
    df = pd.read_csv(BytesIO(file_content))
    col_map = _detect_columns(df.columns.tolist())

    normalized = pd.DataFrame()

    # Timestamp
    time_col = col_map.get('time')
    if time_col:
        try:
            normalized['timeStamp'] = (pd.to_datetime(df[time_col]).astype('int64') // 10**6)
        except Exception:
            normalized['timeStamp'] = pd.Series(range(len(df))) * 100 + int(pd.Timestamp.now().timestamp() * 1000)
    else:
        normalized['timeStamp'] = pd.Series(range(len(df))) * 100 + int(pd.Timestamp.now().timestamp() * 1000)

    # Duration / elapsed
    dur_col = col_map.get('duration')
    normalized['elapsed'] = df[dur_col].fillna(0).astype('int32') if dur_col else 0

    # Label from URL
    url_col = col_map.get('url')
    if url_col:
        normalized['label'] = df[url_col].apply(_label_from_url)
    else:
        normalized['label'] = 'Unknown'

    # Status code
    status_col = col_map.get('status')
    if status_col:
        normalized['responseCode'] = df[status_col].astype(str)
        normalized['success'] = df[status_col].apply(lambda x: 200 <= int(x) <= 399 if str(x).isdigit() else False)
    else:
        normalized['responseCode'] = '200'
        normalized['success'] = True

    # Bytes
    recv_col = col_map.get('received')
    normalized['bytes'] = df[recv_col].fillna(0).astype('int32') if recv_col else 0
    sent_col = col_map.get('sent')
    normalized['sentBytes'] = df[sent_col].fillna(0).astype('int32') if sent_col else 0

    normalized['Latency'] = normalized['elapsed']
    normalized['allThreads'] = 1
    normalized['threadName'] = 'WAPT-Thread'

    logger.info(f"WAPT CSV parsed: {len(normalized)} rows")
    return normalized


def parse_wapt_xml(file_content: bytes) -> pd.DataFrame:
    """Parse WAPT XML results and normalize to JTL-compatible format."""
    root = ET.fromstring(file_content)

    records = []
    base_time = int(pd.Timestamp.now().timestamp() * 1000)

    # Try common WAPT XML structures
    for i, req in enumerate(_find_request_elements(root)):
        ts_text = _get_text(req, ['timestamp', 'time', 'startTime'])
        dur_text = _get_text(req, ['duration', 'responseTime', 'elapsed'])
        url_text = _get_text(req, ['url', 'name', 'label', 'page'])
        status_text = _get_text(req, ['status', 'statusCode', 'responseCode', 'httpCode'])
        bytes_text = _get_text(req, ['received', 'bytes', 'contentLength', 'size'])

        ts = int(ts_text) if ts_text and ts_text.isdigit() else base_time + i * 100
        duration = int(dur_text) if dur_text and dur_text.isdigit() else 0
        status = status_text if status_text else '200'
        success = 200 <= int(status) <= 399 if status.isdigit() else False
        recv_bytes = int(bytes_text) if bytes_text and bytes_text.isdigit() else 0

        records.append({
            'timeStamp': ts,
            'elapsed': duration,
            'label': _label_from_url(url_text or 'Unknown'),
            'responseCode': status,
            'success': success,
            'bytes': recv_bytes,
            'sentBytes': 0,
            'Latency': duration,
            'allThreads': 1,
            'threadName': 'WAPT-Thread',
        })

    result = pd.DataFrame(records)
    logger.info(f"WAPT XML parsed: {len(result)} rows")
    return result


def _detect_columns(columns: list) -> dict:
    """Auto-detect WAPT CSV column mappings."""
    col_lower = {c.lower().strip(): c for c in columns}
    mapping = {}

    for key, candidates in {
        'time': ['time', 'timestamp', 'date', 'datetime', 'start time'],
        'duration': ['duration', 'duration (ms)', 'elapsed', 'response time', 'responsetime'],
        'url': ['url', 'name', 'label', 'request', 'page'],
        'status': ['status', 'statuscode', 'status code', 'http code', 'response code'],
        'received': ['received', 'received (bytes)', 'bytes', 'content size', 'response size'],
        'sent': ['sent', 'sent (bytes)', 'request size'],
    }.items():
        for cand in candidates:
            if cand in col_lower:
                mapping[key] = col_lower[cand]
                break

    return mapping


def _label_from_url(url: str) -> str:
    """Extract a readable label from a URL."""
    try:
        parsed = urlparse(str(url))
        path = parsed.path.rstrip('/')
        return path.split('/')[-1] if path else parsed.netloc or str(url)[:50]
    except Exception:
        return str(url)[:50]


def _find_request_elements(root):
    """Find request-like elements in various WAPT XML structures."""
    for tag in ['request', 'sample', 'httpSample', 'page', 'transaction', 'result', 'entry']:
        elements = list(root.iter(tag))
        if elements:
            return elements
    return list(root)


def _get_text(element, tag_candidates: list) -> str:
    """Try multiple tag names to find a value in an XML element."""
    for tag in tag_candidates:
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        attr = element.get(tag) or element.get(tag.lower())
        if attr:
            return attr.strip()
    return ''
