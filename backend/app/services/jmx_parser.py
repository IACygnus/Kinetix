"""
JMX Parser — Extracts metadata from JMeter .jmx test plan files.
KNX-15: Pre-loads test configuration in the upload form.
"""
import xml.etree.ElementTree as ET
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def parse_jmx(file_content: bytes) -> Dict:
    """
    Parse a JMeter .jmx file and extract test metadata.

    Returns:
        {
            "thread_groups": [
                {
                    "name": "Thread Group Name",
                    "num_threads": 100,
                    "ramp_time": 60,
                    "duration": 1800,
                    "loops": -1,
                }
            ],
            "transactions": ["Login", "Search", "Checkout"],
            "http_defaults": {
                "server": "api.example.com",
                "port": "443",
                "protocol": "https",
            }
        }
    """
    root = ET.fromstring(file_content)

    result: Dict = {
        "thread_groups": [],
        "transactions": [],
        "http_defaults": {},
    }

    # ── Thread Groups (standard) ──────────────────────────────────────────
    for tg in root.iter("ThreadGroup"):
        name = tg.get("testname", "Unknown")

        num_threads_elem = tg.find('.//stringProp[@name="ThreadGroup.num_threads"]')
        ramp_elem = tg.find('.//stringProp[@name="ThreadGroup.ramp_time"]')
        duration_elem = tg.find('.//stringProp[@name="ThreadGroup.duration"]')
        loops_elem = tg.find('.//stringProp[@name="LoopController.loops"]')

        result["thread_groups"].append({
            "name": name,
            "num_threads": _safe_int(num_threads_elem),
            "ramp_time": _safe_int(ramp_elem),
            "duration": _safe_int(duration_elem),
            "loops": _safe_int(loops_elem, default=1),
        })

    # ── ConcurrencyThreadGroup (BlazeMeter plugin) ───────────────────────
    for tg in root.iter("com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup"):
        name = tg.get("testname", "Unknown")
        target_elem = tg.find('.//stringProp[@name="TargetLevel"]')
        ramp_elem = tg.find('.//stringProp[@name="RampUp"]')
        hold_elem = tg.find('.//stringProp[@name="Hold"]')

        result["thread_groups"].append({
            "name": name,
            "num_threads": _safe_int(target_elem),
            "ramp_time": _safe_int(ramp_elem),
            "duration": _safe_int(hold_elem),
            "loops": -1,
        })

    # ── Transaction names ─────────────────────────────────────────────────
    transactions: set = set()

    for tc in root.iter("TransactionController"):
        name = tc.get("testname", "")
        if name:
            transactions.add(name)

    # Fallback: use HTTP sampler names if no Transaction Controllers found
    if not transactions:
        for sampler in root.iter("HTTPSamplerProxy"):
            name = sampler.get("testname", "")
            if name:
                transactions.add(name)

    result["transactions"] = sorted(list(transactions))

    # ── HTTP Request Defaults ─────────────────────────────────────────────
    for defaults in root.iter("ConfigTestElement"):
        if defaults.get("guiclass") == "HttpDefaultsGui":
            server = defaults.find('.//stringProp[@name="HTTPSampler.domain"]')
            port = defaults.find('.//stringProp[@name="HTTPSampler.port"]')
            protocol = defaults.find('.//stringProp[@name="HTTPSampler.protocol"]')

            result["http_defaults"] = {
                "server": server.text if server is not None and server.text else "",
                "port": port.text if port is not None and port.text else "",
                "protocol": protocol.text if protocol is not None and protocol.text else "https",
            }
            break

    logger.info(
        f"JMX parsed: {len(result['thread_groups'])} thread groups, "
        f"{len(result['transactions'])} transactions"
    )

    return result


def _safe_int(elem, default: int = 0) -> int:
    """Safely extract integer from an XML element."""
    if elem is not None and elem.text:
        try:
            return int(elem.text)
        except (ValueError, TypeError):
            pass
    return default
