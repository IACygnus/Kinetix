"""
Wrapper para ejecutar Apache JMeter (subprocess) y parsear el JTL resultante.

Usa el binario JMeter 5.6.3 instalado en /opt/apache-jmeter-5.6.3
(Sprint 2.5a — ver `backend/Dockerfile` stage `jmeter-base`).

Flujo tipico de smoke:
1. ``patch_jmx_for_smoke(jmx_content)`` fuerza N=1 user / 1 loop / no scheduler.
2. ``run_jmeter(patched_jmx, timeout_sec)`` ejecuta subprocess y captura
   exit code + stdout + stderr.
3. El caller parsea el JTL resultante con ``csv.DictReader`` (los samples de
   smoke son tipicamente decenas, no necesita pandas).
"""
from __future__ import annotations

import asyncio
import csv
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional
from xml.etree import ElementTree as ET


JMETER_HOME = os.environ.get("JMETER_HOME", "/opt/apache-jmeter-5.6.3")
JMETER_BIN = os.path.join(JMETER_HOME, "bin", "jmeter")


# ---------------------------------------------------------------------------
# Resultado de ejecucion
# ---------------------------------------------------------------------------


@dataclass
class JMeterRunResult:
    """Lo que se sabe inmediatamente tras invocar jmeter (sin parsear el JTL)."""

    exit_code: int
    jtl_path: Optional[str]
    jmeter_log_path: Optional[str]
    duration_sec: float
    stdout_tail: str
    stderr_tail: str
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Patch del JMX para modo smoke
# ---------------------------------------------------------------------------


def patch_jmx_for_smoke(
    jmx_content: str,
    num_threads: int = 1,
    loops: int = 1,
    data_dir_resolver: Optional[Dict[str, str]] = None,
) -> str:
    """Modifica el JMX en memoria para que sea ejecutable como smoke.

    Args:
        jmx_content: XML del JMX.
        num_threads: usuarios concurrentes (1-20). Sprint 2.5c.1.
        loops: iteraciones por usuario (1-5). Sprint 2.5c.1.
        data_dir_resolver: dict ``{nombre_udv: path_real}``. Si se pasa,
            reescribe el valor de esas UDVs en el JMX (ej.
            ``{'Data': '/app/uploads/ai_data_files/abc-123'}``) para que JMeter
            encuentre los CSVs en runtime sin tocar el JMX portable de descarga.

    Cambios:
        * ``ThreadGroup.num_threads`` -> num_threads (en cualquier kind de TG).
        * ``ThreadGroup.ramp_time`` -> 1.
        * ``ThreadGroup.duration`` / ``ThreadGroup.delay`` -> vacios.
        * ``ThreadGroup.scheduler`` -> false (no time-based, solo conteo).
        * ``LoopController.loops`` -> loops; ``continue_forever`` -> false.
        * ``BackendListener`` -> ``enabled="false"`` (no enviar smoke a InfluxDB).
        * ``CSVDataSet.stopThread`` -> false (no abortar si falta el .csv).
        * Stepping props (kg.apc) -> valores minimos seguros.
        * UDVs en ``data_dir_resolver`` -> reescritas al path real del container.

    Returns:
        XML serializado con declaracion ``<?xml version="1.0" encoding="UTF-8"?>``.

    Raises:
        ValueError si el JMX no parsea como XML o si num_threads/loops estan
        fuera de rango (1-20 y 1-5 respectivamente).
    """
    if not (1 <= num_threads <= 20):
        raise ValueError(f"num_threads debe ser 1-20, recibido {num_threads}")
    if not (1 <= loops <= 5):
        raise ValueError(f"loops debe ser 1-5, recibido {loops}")

    num_threads_s = str(num_threads)
    loops_s = str(loops)

    try:
        root = ET.fromstring(jmx_content)
    except ET.ParseError as e:
        raise ValueError(f"JMX invalido para parsear: {e}")

    # Thread Group estandar
    for tg in root.iter("ThreadGroup"):
        for sp in tg.iter("stringProp"):
            name = sp.get("name", "")
            if name == "ThreadGroup.num_threads":
                sp.text = num_threads_s
            elif name == "ThreadGroup.ramp_time":
                sp.text = "1"
            elif name in ("ThreadGroup.duration", "ThreadGroup.delay"):
                sp.text = ""
        for ip in tg.iter("intProp"):
            name = ip.get("name", "")
            if name == "ThreadGroup.num_threads":
                ip.text = num_threads_s
            elif name == "ThreadGroup.ramp_time":
                ip.text = "1"
        for bp in tg.iter("boolProp"):
            if bp.get("name") == "ThreadGroup.scheduler":
                bp.text = "false"
        # LoopController dentro del TG (main_controller)
        for ep in tg.iter("elementProp"):
            if ep.get("name") == "ThreadGroup.main_controller":
                for inner in ep.iter():
                    iname = inner.get("name", "") if inner.tag != ep.tag else ""
                    if inner.tag == "intProp" and iname == "LoopController.loops":
                        inner.text = loops_s
                    elif inner.tag == "stringProp" and iname == "LoopController.loops":
                        inner.text = loops_s
                    elif inner.tag == "boolProp" and iname == "LoopController.continue_forever":
                        inner.text = "false"

    # SteppingThreadGroup (kg.apc) — minimo seguro
    for stg in root.iter("kg.apc.jmeter.threads.SteppingThreadGroup"):
        for sp in stg.iter("stringProp"):
            name = sp.get("name", "")
            if name in (
                "ThreadGroup.num_threads",
                "Threads count",
                "Start users count",
            ):
                sp.text = num_threads_s
            elif name in ("rampUp", "ramp_up", "ThreadGroup.ramp_time"):
                sp.text = "1"
            elif name in (
                "flighttime",
                "flight_time",
                "Threads initial delay",
            ):
                sp.text = "1"
            elif name in (
                "Stop users count",
                "Start users count burst",
                "Start users period",
                "Stop users period",
            ):
                sp.text = "1"

    # Deshabilitar Backend Listener (no enviar smoke a InfluxDB)
    for bl in root.iter("BackendListener"):
        bl.set("enabled", "false")

    # CSVDataSet: stopThread=false para que el sampler corra aunque falte el CSV
    for csv_elem in root.iter("CSVDataSet"):
        for bp in csv_elem.iter("boolProp"):
            if bp.get("name") == "stopThread":
                bp.text = "false"

    # Sprint 2.5c.1 — reescribir UDVs segun el resolver (ej. ${Data} -> path real
    # del container) para que JMeter encuentre los CSVs en runtime. El JMX de
    # descarga mantiene los valores portables; solo el smoke usa los reales.
    if data_dir_resolver:
        for elem_prop in root.iter("elementProp"):
            if elem_prop.get("elementType") != "Argument":
                continue
            name_prop = elem_prop.find("stringProp[@name='Argument.name']")
            value_prop = elem_prop.find("stringProp[@name='Argument.value']")
            if name_prop is None or value_prop is None:
                continue
            udv_name = (name_prop.text or "").strip()
            if udv_name in data_dir_resolver:
                value_prop.text = data_dir_resolver[udv_name]

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
    )


# ---------------------------------------------------------------------------
# Ejecutor subprocess
# ---------------------------------------------------------------------------


def run_jmeter(
    jmx_content: str,
    timeout_sec: int = 60,
    workdir: Optional[str] = None,
) -> JMeterRunResult:
    """Ejecuta JMeter non-GUI sobre el JMX dado.

    Args:
        jmx_content: contenido completo del JMX (string).
        timeout_sec: timeout del subprocess en segundos.
        workdir: directorio donde escribir test.jmx / result.jtl / jmeter.log.
            Si None, crea uno con ``tempfile.mkdtemp(prefix='jmeter_smoke_')``.

    Returns:
        ``JMeterRunResult`` con paths al JTL y al log.
    """
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="jmeter_smoke_")

    workdir_path = Path(workdir)
    workdir_path.mkdir(parents=True, exist_ok=True)

    jmx_path = workdir_path / "test.jmx"
    jtl_path = workdir_path / "result.jtl"
    log_path = workdir_path / "jmeter.log"

    jmx_path.write_text(jmx_content, encoding="utf-8")

    start = time.time()
    error_message: Optional[str] = None
    exit_code = -1
    stdout_tail = ""
    stderr_tail = ""

    cmd = [
        JMETER_BIN,
        "-n",  # non-GUI
        "-t", str(jmx_path),
        "-l", str(jtl_path),
        "-j", str(log_path),
        "-Jjmeter.save.saveservice.output_format=csv",
        "-Jjmeter.save.saveservice.print_field_names=true",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(workdir_path),
        )
        exit_code = proc.returncode
        stdout_tail = (proc.stdout or "")[-2000:]
        stderr_tail = (proc.stderr or "")[-2000:]
    except subprocess.TimeoutExpired:
        error_message = f"JMeter excedio el timeout de {timeout_sec}s"
    except FileNotFoundError:
        error_message = f"JMeter no encontrado en {JMETER_BIN}"
    except Exception as e:
        error_message = f"Error ejecutando JMeter: {e}"

    duration_sec = time.time() - start

    return JMeterRunResult(
        exit_code=exit_code,
        jtl_path=str(jtl_path) if jtl_path.exists() else None,
        jmeter_log_path=str(log_path) if log_path.exists() else None,
        duration_sec=duration_sec,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        error_message=error_message,
    )


def create_smoke_workdir() -> str:
    """Crea un workdir temporal para el smoke test.

    Sprint 2.5c.1-HF12: el caller (endpoint smoke-test) usa este workdir para
    copiar fisicamente los Data Files del diseno con su ``original_filename``
    (el nombre que el JMX referencia como ``${Data}/<archivo>``) ANTES de
    invocar ``run_jmeter(workdir=...)``. JMeter resuelve ``${Data}`` al workdir
    local y encuentra los CSV. El caller es responsable de ``cleanup_workdir``.
    """
    return tempfile.mkdtemp(prefix="jmeter_smoke_")


def cleanup_workdir(workdir: Optional[str]) -> None:
    """Limpia el directorio temporal de un run JMeter."""
    if not workdir:
        return
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sprint 2.5d.1 — Ejecucion FULL (no smoke)
# ---------------------------------------------------------------------------


def prepare_full_run_jmx(
    jmx_content: str,
    data_dir_resolver: Optional[Dict[str, str]] = None,
    influxdb_resolver: Optional[Dict[str, str]] = None,
) -> str:
    """Prepara el JMX para ejecucion completa (NO smoke).

    A diferencia de ``patch_jmx_for_smoke``:
        * NO reduce ``num_threads`` ni ``loops`` (respeta el Thread Group tal cual).
        * Habilita el ``BackendListener`` (``enabled="true"``) para que las
          metricas lleguen a InfluxDB/Grafana.

    Igual que el smoke:
        * ``CSVDataSet.stopThread`` -> false (no abortar si falta el CSV).
        * Reescribe UDVs presentes en ``data_dir_resolver`` / ``influxdb_resolver``
          (ej. ``${Data}`` -> path real del container, ``${InfluxdbURL}`` -> URL).

    Args:
        jmx_content: XML del JMX.
        data_dir_resolver: ``{nombre_udv: path_real}`` para Data Files.
        influxdb_resolver: ``{nombre_udv: valor}`` para config InfluxDB.

    Returns:
        XML serializado con declaracion ``<?xml ...?>``.

    Raises:
        ValueError si el JMX no parsea como XML.
    """
    try:
        root = ET.fromstring(jmx_content)
    except ET.ParseError as e:
        raise ValueError(f"JMX invalido para parsear: {e}")

    # Habilitar Backend Listener (opuesto al smoke).
    for bl in root.iter("BackendListener"):
        bl.set("enabled", "true")

    # CSVDataSet: stopThread=false para que el sampler corra aunque falte el CSV.
    for csv_elem in root.iter("CSVDataSet"):
        for bp in csv_elem.iter("boolProp"):
            if bp.get("name") == "stopThread":
                bp.text = "false"

    # Reescribir UDVs segun los resolvers (Data Files + InfluxDB).
    all_resolvers: Dict[str, str] = {}
    if data_dir_resolver:
        all_resolvers.update(data_dir_resolver)
    if influxdb_resolver:
        all_resolvers.update(influxdb_resolver)

    if all_resolvers:
        for elem_prop in root.iter("elementProp"):
            if elem_prop.get("elementType") != "Argument":
                continue
            name_prop = elem_prop.find("stringProp[@name='Argument.name']")
            value_prop = elem_prop.find("stringProp[@name='Argument.value']")
            if name_prop is None or value_prop is None:
                continue
            udv_name = (name_prop.text or "").strip()
            if udv_name in all_resolvers:
                value_prop.text = all_resolvers[udv_name]

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
    )


async def run_jmeter_async(
    jmx_path: str,
    jtl_path: str,
    log_path: str,
    workdir: str,
    timeout_sec: int = 3600,
    progress_callback: Optional[Callable[[float, int], Awaitable[None]]] = None,
    pid_callback: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """Ejecuta JMeter como subprocess asincrono (modo FULL).

    Lanza ``jmeter -n -t <jmx> -l <jtl> -j <log>`` y, mientras corre, invoca
    ``progress_callback(elapsed_sec, jtl_size_bytes)`` cada ~2s para emitir
    progreso (polling de metricas live).

    Args:
        jmx_path: ruta al JMX ya preparado en disco.
        jtl_path: ruta donde JMeter escribe el JTL.
        log_path: ruta del jmeter.log.
        workdir: cwd del subprocess.
        timeout_sec: timeout duro del subprocess.
        progress_callback: async ``(elapsed_sec, jtl_size_bytes) -> None``.
        pid_callback: sync ``(pid) -> None`` invocado apenas arranca el proceso
            (para registrarlo en el tracker y poder cancelarlo).

    Returns:
        ``{exit_code, duration_sec, stdout_tail, stderr_tail, error}``.
    """
    cmd = [
        JMETER_BIN,
        "-n",
        "-t", jmx_path,
        "-l", jtl_path,
        "-j", log_path,
        "-Jjmeter.save.saveservice.output_format=csv",
        "-Jjmeter.save.saveservice.print_field_names=true",
    ]

    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
    except FileNotFoundError:
        return {
            "exit_code": -1,
            "duration_sec": time.time() - start,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": f"JMeter no encontrado en {JMETER_BIN}",
        }

    if pid_callback:
        try:
            pid_callback(proc.pid)
        except Exception:
            pass

    # Monitor de progreso: poll cada 2s mientras el proceso corre.
    async def monitor() -> None:
        while proc.returncode is None:
            await asyncio.sleep(2)
            if progress_callback:
                jtl_size = 0
                try:
                    if os.path.exists(jtl_path):
                        jtl_size = os.path.getsize(jtl_path)
                except OSError:
                    pass
                elapsed = time.time() - start
                try:
                    await progress_callback(elapsed, jtl_size)
                except Exception:
                    pass

    monitor_task = asyncio.create_task(monitor())

    error: Optional[str] = None
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_sec
        )
        exit_code = proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        exit_code = -1
        stdout = b""
        stderr = b""
        error = f"JMeter excedio timeout de {timeout_sec}s"
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except (asyncio.CancelledError, Exception):
            pass

    return {
        "exit_code": exit_code,
        "duration_sec": time.time() - start,
        "stdout_tail": (stdout or b"")[-2000:].decode("utf-8", errors="replace"),
        "stderr_tail": (stderr or b"")[-2000:].decode("utf-8", errors="replace"),
        "error": error,
    }


def cancel_jmeter_process(pid: int) -> bool:
    """Intenta terminar un proceso JMeter en curso (SIGTERM).

    Returns:
        True si la senal se envio; False si el proceso ya no existe o no se pudo.
    """
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def parse_jtl_summary(jtl_path: str) -> Dict[str, Any]:
    """Lee el JTL CSV (parcial o completo) y calcula metricas agregadas en vivo.

    Pensado para emitir por polling durante una ejecucion en curso. Tolerante a
    archivos incompletos (la ultima fila puede estar a medio escribir).

    Returns:
        dict con total/successful/failed samples, throughput/s, avg response ms,
        error rate %.
    """
    empty = {
        "total_samples": 0,
        "successful_samples": 0,
        "failed_samples": 0,
        "throughput_per_sec": 0.0,
        "avg_response_ms": 0,
        "error_rate_pct": 0.0,
    }
    if not os.path.exists(jtl_path):
        return empty

    total = 0
    success = 0
    fail = 0
    elapsed_sum = 0
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None

    try:
        with open(jtl_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if str(row.get("success", "")).lower() == "true":
                    success += 1
                else:
                    fail += 1
                try:
                    elapsed_sum += int(row.get("elapsed", 0) or 0)
                except (ValueError, TypeError):
                    pass
                try:
                    ts = int(row.get("timeStamp", 0) or 0)
                    if ts > 0:
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    if first_ts and last_ts and last_ts > first_ts:
        duration_sec = (last_ts - first_ts) / 1000.0
    else:
        duration_sec = 0.001

    return {
        "total_samples": total,
        "successful_samples": success,
        "failed_samples": fail,
        "throughput_per_sec": round(total / duration_sec, 2) if duration_sec > 0 else 0.0,
        "avg_response_ms": round(elapsed_sum / total, 1) if total > 0 else 0,
        "error_rate_pct": round((fail / total) * 100, 2) if total > 0 else 0.0,
    }


# Patrones críticos en jmeter.log que indican un fallo aunque JMeter salga con 0.
_SILENT_FAILURE_PATTERNS = [
    r"must exist and be readable",
    r"Test failed!",
    r"java\.lang\.IllegalArgumentException",
    r"java\.io\.FileNotFoundException",
]


def _detect_silent_failure(workdir: str, jtl_path: str) -> tuple[bool, str]:
    """
    Detecta si una ejecución de JMeter falló silenciosamente (HF14a).

    JMeter puede salir con exit_code=0 y JTL vacío cuando, por ejemplo, un CSV
    Data Set apunta a un archivo inexistente. Esto evita el status engañoso
    "completed" con 0 samples.

    Returns:
        (has_failure, error_message). has_failure=True si hay evidencia de fallo.
    """
    jmeter_log = os.path.join(workdir, "jmeter.log")

    # 1) Patrones de error críticos en jmeter.log.
    if os.path.exists(jmeter_log):
        try:
            with open(jmeter_log, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
            for pattern in _SILENT_FAILURE_PATTERNS:
                if re.search(pattern, log_content):
                    for line in log_content.split("\n"):
                        if re.search(pattern, line):
                            return True, f"JMeter error: {line.strip()[:200]}"
                    return True, f"JMeter error detectado: {pattern}"
        except Exception:  # noqa: BLE001 — best-effort, no romper el flujo de status
            pass

    # 2) JTL vacío o solo header (sin samples).
    if jtl_path and os.path.exists(jtl_path):
        try:
            if os.path.getsize(jtl_path) < 100:
                with open(jtl_path, "r", encoding="utf-8", errors="replace") as f:
                    line_count = sum(1 for _ in f)
                if line_count <= 1:
                    return True, (
                        "JMeter terminó sin generar samples — revisar el JMX y los "
                        "archivos CSV referenciados."
                    )
        except Exception:  # noqa: BLE001
            pass

    return False, ""
