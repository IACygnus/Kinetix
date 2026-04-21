# backend/app/services/engine/variable_engine.py
"""
Variable Engine — Sustitución de variables ${var} en strings del Script Model.

Maneja el contexto de variables de un VirtualUser durante una ejecución.
Soporta variables manuales del script, variables extraídas de responses (correlación),
y variables de DataFiles (parametrización CSV).

REGLA CRÍTICA: Si una variable ${var} no está definida en el contexto,
se registra un WARNING explícito y se deja el placeholder sin sustituir.
NUNCA falla silenciosamente.
"""
import re
import logging
import uuid
import time
import random
import string
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Patrón para detectar variables ${var_name}
VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

# ── Nombres para built-ins ──────────────────────────────────────────────────
FIRST_NAMES = [
    "Carlos", "Maria", "Jose", "Ana", "Luis", "Laura", "Jorge", "Sandra",
    "Miguel", "Patricia", "Andres", "Claudia", "Fernando", "Diana", "Ricardo",
    "Valentina", "Sebastian", "Camila", "Alejandro", "Isabella", "Daniel",
    "Sofia", "Mateo", "Lucia", "David", "Emma", "Juan", "Paula", "Pablo",
    "Natalia", "Roberto", "Gabriela", "Eduardo", "Monica",
]
LAST_NAMES = [
    "Gonzalez", "Perez", "Rodriguez", "Lopez", "Martinez", "Garcia",
    "Hernandez", "Diaz", "Torres", "Ramirez", "Flores", "Rivera",
    "Morales", "Jimenez", "Castro", "Vargas", "Reyes", "Mendoza",
    "Cruz", "Ortega", "Rojas", "Sanchez", "Guerrero", "Ruiz",
    "Estrada", "Medina", "Aguilar", "Vasquez", "Ramos", "Herrera",
]

# ── Funciones built-in ──────────────────────────────────────────────────────
BUILTIN_GENERATORS = {
    '$guid':            lambda: str(uuid.uuid4()),
    '$randomIP':        lambda: f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
    '$timestamp':       lambda: str(int(time.time() * 1000)),
    '$isoTimestamp':    lambda: datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    '$randomInt':       lambda: str(random.randint(0, 1000)),
    '$randomAlphaNum':  lambda: ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)),
    '$randomFirstName': lambda: random.choice(FIRST_NAMES),
    '$randomLastName':  lambda: random.choice(LAST_NAMES),
    '$randomEmail':     lambda: f"user_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}@test.com",
}


WORDS = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "theta", "kappa",
    "lambda", "sigma", "omega", "phoenix", "nova", "echo", "vortex", "nexus",
    "apex", "prime", "core", "flex", "pulse", "wave", "stream", "cloud", "forge",
]


def _format_date(dt: datetime, fmt: str) -> str:
    """Format a datetime according to the named format."""
    if fmt == 'YYYY-MM-DD':  return dt.strftime('%Y-%m-%d')
    if fmt == 'DD/MM/YYYY':  return dt.strftime('%d/%m/%Y')
    if fmt == 'MM/DD/YYYY':  return dt.strftime('%m/%d/%Y')
    if fmt == 'DD-MM-YYYY':  return dt.strftime('%d-%m-%Y')
    if fmt == 'YYYY/MM/DD':  return dt.strftime('%Y/%m/%d')
    if fmt == 'D MMM YYYY':  return dt.strftime('%d %b %Y').lstrip('0')
    if fmt == 'iso':         return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    if fmt == 'timestamp':   return str(int(dt.timestamp()))
    return dt.strftime('%Y-%m-%d')


def _resolve_date_range(from_str: str, to_str: str, fmt: str) -> str:
    """Generate a random date between from_str and to_str in the given format."""
    try:
        d_from = datetime.strptime(from_str, '%Y-%m-%d')
        d_to = datetime.strptime(to_str, '%Y-%m-%d')
        delta = (d_to - d_from).days
        if delta <= 0:
            return _format_date(d_from, fmt)
        return _format_date(d_from + timedelta(days=random.randint(0, delta)), fmt)
    except Exception:
        return from_str


def resolve_builtin_function(var_expr: str) -> Optional[str]:
    """
    Resolve parameterized and new built-in functions.

    Supports:
      Text:    $randomAlphaNum(N), $randomString(N), $randomWord, $randomPhrase
      Numbers: $randomInt(min,max), $randomFloat(min,max,decimals), $randomPrice
      Dates:   $randomDate(from,to,fmt), $today(fmt), $tomorrow(fmt), $dateOffset(days,fmt)
      Data:    $randomCNP, $randomPhone
    """
    # ── Text functions ───────────────────────────────────────────────────────
    # $randomAlphaNum(N) or $randomAlphaNum without param
    m = re.match(r'\$randomAlphaNum(?:\((\d+)\))?$', var_expr)
    if m:
        n = int(m.group(1)) if m.group(1) else 8
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    # $randomString(N)
    m = re.match(r'\$randomString\((\d+)\)', var_expr)
    if m:
        return ''.join(random.choices(string.ascii_lowercase, k=int(m.group(1))))

    if var_expr == '$randomWord':
        return random.choice(WORDS)

    if var_expr == '$randomPhrase':
        return ' '.join(random.sample(WORDS, k=random.randint(3, 5)))

    # ── Number functions ─────────────────────────────────────────────────────
    # $randomInt(min,max)
    m = re.match(r'\$randomInt\((-?\d+),(-?\d+)\)', var_expr)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return str(random.randint(min(lo, hi), max(lo, hi)))

    # $randomFloat(min,max,decimals)
    m = re.match(r'\$randomFloat\((-?[\d.]+),(-?[\d.]+)(?:,(\d+))?\)', var_expr)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2))
        dec = int(m.group(3)) if m.group(3) else 2
        return str(round(random.uniform(lo, hi), dec))

    if var_expr == '$randomPrice':
        return str(round(random.uniform(1.0, 999.99), 2))

    # ── Date functions ───────────────────────────────────────────────────────
    # $randomDate(from,to,fmt)
    m = re.match(r'\$randomDate\(([^,]+),([^,]+),([^)]+)\)', var_expr)
    if m:
        return _resolve_date_range(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())

    # $today(fmt) or $today
    m = re.match(r'\$today(?:\(([^)]+)\))?$', var_expr)
    if m:
        fmt = m.group(1) or 'YYYY-MM-DD'
        return _format_date(datetime.now(), fmt)

    # $tomorrow(fmt) or $tomorrow
    m = re.match(r'\$tomorrow(?:\(([^)]+)\))?$', var_expr)
    if m:
        fmt = m.group(1) or 'YYYY-MM-DD'
        return _format_date(datetime.now() + timedelta(days=1), fmt)

    # $dateOffset(days,fmt)
    m = re.match(r'\$dateOffset\((-?\d+)(?:,([^)]+))?\)', var_expr)
    if m:
        days = int(m.group(1))
        fmt = m.group(2).strip() if m.group(2) else 'YYYY-MM-DD'
        return _format_date(datetime.now() + timedelta(days=days), fmt)

    # ── Data functions ───────────────────────────────────────────────────────
    if var_expr == '$randomCNP':
        return ''.join(random.choices(string.digits, k=10))

    if var_expr == '$randomPhone':
        return f"+57{random.randint(300, 399)}{random.randint(1000000, 9999999)}"

    return None


class VariableEngine:
    """
    Gestiona el contexto de variables de un único VirtualUser.

    Orden de resolución:
    1. Variables extraídas (correlación) — mayor prioridad
    2. Variables de DataFile (fila asignada al VU)
    3. Variables manuales del script
    """

    def __init__(self, thread_name: str):
        self.thread_name = thread_name
        self._context: Dict[str, str] = {}
        self._unresolved_log: list = []

    def initialize(self, script_variables: list, datafile_row: Optional[Dict[str, str]] = None):
        """
        Inicializar contexto con variables del script y fila de DataFile.

        Args:
            script_variables: Lista de dicts {"name": str, "value": str, "source": str}
            datafile_row: Fila del CSV asignada a este VirtualUser (o None)
        """
        # 1. Variables manuales del script (menor prioridad)
        for var in script_variables:
            name = var.get("name", "").strip()
            value = str(var.get("value", ""))
            if name:
                self._context[name] = value

        # 2. Variables de DataFile sobreescriben manuales
        if datafile_row:
            for col, val in datafile_row.items():
                self._context[col.strip()] = val

    def set(self, name: str, value: str):
        """Definir o actualizar una variable (para variables extraídas de responses)."""
        self._context[name] = value
        logger.debug(f"[{self.thread_name}] Variable set: {name}={value[:50]}{'...' if len(value) > 50 else ''}")

    def get(self, name: str, default: str = "") -> str:
        """Obtener el valor de una variable."""
        return self._context.get(name, default)

    def substitute(self, text: str) -> str:
        """
        Sustituir todas las variables ${var} en un string.

        Si una variable no está definida:
        - Registra un WARNING con thread_name y nombre de variable
        - Deja el placeholder ${var} sin sustituir (para que el error sea visible en el request)

        Returns:
            String con variables sustituidas
        """
        if not text or '${' not in text:
            return text

        unresolved = []

        def replace(match):
            var_name = match.group(1)
            if var_name in self._context:
                val = self._context[var_name]
                # If the stored value is itself a function reference (e.g. "$randomFirstName"),
                # resolve it as a builtin — generates a NEW value each call (each iteration)
                if isinstance(val, str) and val.startswith('$'):
                    fn_result = resolve_builtin_function(val)
                    if fn_result is not None:
                        return fn_result
                    if val in BUILTIN_GENERATORS:
                        return BUILTIN_GENERATORS[val]()
                return val
            # Try parameterized built-in functions first (e.g. ${randomInt(1,500)})
            fn_result = resolve_builtin_function(var_name)
            if fn_result is not None:
                return fn_result
            # Check built-in functions (e.g. ${guid}, ${randomIP})
            if var_name in BUILTIN_GENERATORS:
                return BUILTIN_GENERATORS[var_name]()
            # Also try with $ prefix for ${randomIP} -> $randomIP
            prefixed = f"${var_name}"
            if prefixed in BUILTIN_GENERATORS:
                return BUILTIN_GENERATORS[prefixed]()
            # Try as parameterized builtin with $ prefix (e.g. ${randomInt(1,500)} -> $randomInt(1,500))
            fn_result = resolve_builtin_function(prefixed)
            if fn_result is not None:
                return fn_result
            unresolved.append(var_name)
            return match.group(0)  # Dejar ${var} sin sustituir

        result = VAR_PATTERN.sub(replace, text)

        # Log explícito por cada variable no resuelta — NUNCA silencioso
        for var_name in unresolved:
            msg = f"[{self.thread_name}] UNRESOLVED VARIABLE: ${{{var_name}}} — variable not found in context. Available: {list(self._context.keys())}"
            logger.warning(msg)
            self._unresolved_log.append({"variable": var_name, "context_keys": list(self._context.keys())})

        return result

    def substitute_dict(self, d: dict) -> dict:
        """Sustituir variables en todos los valores de un dict."""
        return {k: self.substitute(str(v)) for k, v in d.items()}

    def apply_extractors(self, extractors: list, response_body: str, response_headers: dict):
        """
        Aplicar extractores de un request al response recibido.
        Las variables extraídas se agregan al contexto inmediatamente
        para estar disponibles en el próximo request.

        Args:
            extractors: Lista de extractors del request (ya definidos en Sprint 0)
            response_body: Cuerpo del response como string
            response_headers: Headers del response como dict
        """
        import re as re_mod
        for extractor in extractors:
            var_name = extractor.get("variable_name", "").strip()
            regex = extractor.get("regex", "")
            extract_from = extractor.get("extract_from", "body")
            match_no = extractor.get("match_no", 1)
            default = extractor.get("default_value", "")
            header_name = extractor.get("header_name", "")

            if not var_name or not regex:
                continue

            source_text = ""
            if extract_from == "body":
                source_text = response_body
            elif extract_from == "header":
                source_text = response_headers.get(header_name, "")

            try:
                matches = re_mod.findall(regex, source_text)
                if matches:
                    idx = min(match_no - 1, len(matches) - 1)
                    val = matches[idx]
                    extracted = val if isinstance(val, str) else (val[0] if val else default)
                    self.set(var_name, extracted)
                    logger.debug(f"[{self.thread_name}] Extracted {var_name}={extracted[:30]}...")
                else:
                    self.set(var_name, default)
                    if default == "":
                        logger.warning(f"[{self.thread_name}] EXTRACTOR MISS: ${{{var_name}}} — regex '{regex}' found no match. Using default='{default}'")
            except re_mod.error as e:
                logger.error(f"[{self.thread_name}] REGEX ERROR in extractor for {var_name}: {e}")
                self.set(var_name, default)

    @property
    def unresolved_variables(self) -> list:
        """Retorna el log de variables no resueltas (para el reporte de errores)."""
        return self._unresolved_log.copy()

    def snapshot(self) -> dict:
        """Snapshot del contexto actual (para debugging)."""
        return dict(self._context)
