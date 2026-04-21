"""
KNX-16: Auto-detect file format (JTL, Locust CSV, WAPT CSV/XML).
"""
import os
import logging

logger = logging.getLogger(__name__)


def detect_file_format(filename: str, file_path: str) -> str:
    """
    Detect the format of a performance test results file.
    Returns: 'jtl', 'locust', 'wapt_csv', 'wapt_xml', or 'unknown'.
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.jtl':
        return 'jtl'

    if ext == '.xml':
        try:
            with open(file_path, 'rb') as f:
                head = f.read(5000)
            head_str = head.decode('utf-8', errors='ignore').lower()
            if any(tag in head_str for tag in ['<wapt', '<waptresults', '<results']):
                return 'wapt_xml'
        except Exception:
            pass
        return 'wapt_xml'  # default XML to WAPT

    if ext == '.csv':
        try:
            with open(file_path, 'rb') as f:
                header_line = f.readline().decode('utf-8', errors='ignore').lower().strip()

            # JTL CSV: has timeStamp + elapsed + label
            if 'timestamp' in header_line and 'elapsed' in header_line and 'label' in header_line:
                return 'jtl'

            # Locust: has 'request count' (stats) or 'response time' (requests)
            if 'request count' in header_line or '# requests' in header_line:
                return 'locust'
            if 'response time' in header_line and ('name' in header_line or 'type' in header_line):
                return 'locust'

            # WAPT: has 'duration' + 'url' or 'page'
            if 'duration' in header_line and ('url' in header_line or 'page' in header_line):
                return 'wapt_csv'

            # Default: treat as JTL CSV (most common)
            logger.warning(f"Could not determine CSV format for {filename}, defaulting to JTL")
            return 'jtl'

        except Exception as e:
            logger.error(f"Error detecting format for {filename}: {e}")
            return 'jtl'

    return 'unknown'
