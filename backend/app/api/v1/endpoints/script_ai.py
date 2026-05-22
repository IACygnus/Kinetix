"""
AI Script Designer endpoints — JMeter JMX generation via OpenAI / Gemini.

Provides conversational JMX generation:
- POST /generate    First-shot JMX from a natural-language prompt.
- POST /refine      Iterative refinement of an existing JMX.
- POST /validate    Structural validation + component extraction.
- POST /download    Returns a .jmx attachment.

Auth: admin or analyst role. AI provider/model/key are read from the
ai_config table via load_ai_config_from_db (same source used by the
performance analysis pipeline).
"""
from __future__ import annotations

import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.models.user import User
from app.db.session import get_db
from app.services.ai.gemini import load_ai_config_from_db

# Max bytes of an uploaded reference file (Postman / Swagger / text).
# Anything bigger gets truncated to keep OpenAI token usage bounded.
MAX_FILE_BYTES = 500 * 1024  # 500 KB

logger = logging.getLogger(__name__)
router = APIRouter()


# ===================== SYSTEM PROMPT =====================

SYSTEM_PROMPT = """
Eres un arquitecto experto en Apache JMeter con 15 anos de
experiencia disenando pruebas de carga empresariales.

Tu tarea es generar scripts JMeter (JMX) COMPLETOS y PROFESIONALES
listos para ejecucion.

## ESTRUCTURA OBLIGATORIA DEL JMX

Todo JMX debe incluir en este ORDEN EXACTO:

1. **Test Plan** con nombre descriptivo del proyecto
2. **User Defined Variables** (Arguments):
   - host: dominio del servidor
   - scheme: https o http
   - port: puerto (443, 8080, etc.)
   - Paths de datos si se usan CSV
3. **HTTP Request Defaults**: dominio=${host}, protocol=${scheme}
4. **HTTP Cookie Manager** (clearEachIteration=true)
5. **HTTP Cache Manager** (clearEachIteration=true, useExpires=true)
6. **CSV Data Sets** (si se necesita parametrizacion):
   - delimiter=","
   - recycle=true
   - shareMode=shareMode.all
   - Nombres descriptivos de variables
7. **Thread Group** (tipo estandar o Stepping):
   - Nombre descriptivo
   - num_threads, ramp-up, loops configurables
   - on_sample_error=continue
8. **HTTP Samplers** numerados ("1. Auth", "2. Get Booking", etc.):
   Cada sampler DEBE tener:
   a. Path relativo (ej: /auth, /booking/${bookingid})
   b. Method correcto (GET, POST, PUT, DELETE)
   c. Port 443 si es HTTPS
   d. **Header Manager** con headers apropiados:
      - Content-Type: application/json (para POST/PUT)
      - Accept: application/json
      - Cookie: token=${token} (si requiere auth)
      - Authorization: Bearer ${token} (si aplica)
   e. **Body** JSON completo para POST/PUT
   f. **Response Assertion** verificando codigo HTTP (200, 201, etc.)
   g. **Regex Extractor** si se necesita correlacion:
      - Extraer tokens, IDs, session cookies
      - refname descriptivo (token, bookingid, etc.)
      - template=$1$
      - match_number=1
9. **View Results Tree** (listener, enabled=false para ejecucion)
10. **Summary Report** (listener)

## FORMATO XML JMX

Usar EXACTAMENTE esta estructura XML de JMeter 5.6:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan"
     testname="[NOMBRE]">
      ...
    </TestPlan>
    <hashTree>
      <!-- Variables, Defaults, Cookie, Cache aqui -->
      <ThreadGroup ...>
      </ThreadGroup>
      <hashTree>
        <!-- Samplers con sus hijos aqui -->
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
```

Cada elemento DEBE tener los atributos guiclass, testclass, testname.
Los hijos de cada sampler van DENTRO del <hashTree> que sigue
al sampler.

## CUANDO RECIBES UNA COLECCION POSTMAN

Si el usuario sube un archivo Postman Collection:
1. Extraer TODOS los endpoints con su metodo, URL, headers y body
2. Identificar el flujo logico (auth primero, luego CRUD)
3. Detectar variables de entorno ({{baseUrl}}, {{token}})
4. Convertir variables Postman -> variables JMeter (${host}, ${token})
5. Crear extractores de correlacion para tokens y IDs dinamicos
6. Generar assertions para cada endpoint
7. Numerar los samplers en orden logico de ejecucion

## CUANDO RECIBES UN SWAGGER/OPENAPI

Si el usuario sube un archivo Swagger/OpenAPI:
1. Extraer todos los paths con sus operaciones
2. Identificar schemas de request body
3. Generar samplers para cada operacion
4. Crear datos de prueba realistas basados en los schemas

## REGLAS DE CALIDAD
- Nombres de samplers en espanol numerados: "1. Autenticacion",
  "2. Consultar Reservas", etc.
- Comentarios XML explicando secciones complejas
- Variables para TODO lo configurable (host, port, paths, credenciales)
- NUNCA hardcodear URLs completas - usar ${host}, ${scheme}, etc.
- Assertions en CADA sampler
- Headers en CADA sampler que los necesite
- Si hay autenticacion, el primer sampler SIEMPRE es Auth + extractor
  de token
- Body JSON formateado (no en una sola linea)

## FORMATO DE RESPUESTA
1. Explicacion breve (2-3 parrafos) de lo que se genero
2. Lista de componentes incluidos
3. JMX completo dentro de ```xml ... ```
4. Notas/advertencias al final (archivos CSV necesarios,
   variables a configurar, etc.)
""".strip()


# ===================== PYDANTIC SCHEMAS =====================


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str


class GenerateRequest(BaseModel):
    prompt: str
    conversation_history: Optional[List[ChatMessage]] = None


class RefineRequest(BaseModel):
    prompt: str
    current_jmx: str
    conversation_history: Optional[List[ChatMessage]] = None
    file_content: Optional[str] = None  # Persisted reference (Postman / Swagger / text)
    file_name: Optional[str] = None


class ValidateRequest(BaseModel):
    jmx_content: str


class DownloadRequest(BaseModel):
    jmx_content: str
    filename: Optional[str] = None


class ComponentInfo(BaseModel):
    type: str
    name: str
    props: dict


class AIResponse(BaseModel):
    jmx_content: str
    explanation: str
    is_valid: bool
    error: Optional[str] = None
    components: Optional[List[ComponentInfo]] = None


class ValidationResponse(BaseModel):
    is_valid: bool
    components: List[ComponentInfo]
    errors: List[str]


# ===================== PARSING HELPERS =====================

_JMX_FENCE_RE = re.compile(r"```(?:xml|jmx)?\s*(<\?xml[\s\S]+?</jmeterTestPlan>)\s*```", re.IGNORECASE)
_JMX_BARE_RE = re.compile(r"(<\?xml[\s\S]+?</jmeterTestPlan>)", re.IGNORECASE)


def _extract_jmx_and_explanation(text: str) -> tuple[str, str]:
    """Extract the JMX XML block and the surrounding explanation from an AI response."""
    if not text:
        return "", ""

    match = _JMX_FENCE_RE.search(text)
    if not match:
        match = _JMX_BARE_RE.search(text)

    if not match:
        return "", text.strip()

    jmx = match.group(1).strip()
    explanation = (text[: match.start()] + text[match.end():]).strip()
    explanation = re.sub(r"```(?:xml|jmx)?\s*```", "", explanation).strip()
    return jmx, explanation


# JMeter component testclass → human label
_COMPONENT_LABELS = {
    "TestPlan": "Test Plan",
    "ThreadGroup": "Thread Group",
    "PostThreadGroup": "Post Thread Group",
    "SetupThreadGroup": "Setup Thread Group",
    "HTTPSamplerProxy": "HTTP Sampler",
    "HTTPSampler": "HTTP Sampler",
    "HeaderManager": "HTTP Header Manager",
    "CookieManager": "HTTP Cookie Manager",
    "CacheManager": "HTTP Cache Manager",
    "ConfigTestElement": "HTTP Request Defaults",
    "ResponseAssertion": "Response Assertion",
    "DurationAssertion": "Duration Assertion",
    "SizeAssertion": "Size Assertion",
    "JSONPostProcessor": "JSON Extractor",
    "RegexExtractor": "Regex Extractor",
    "ConstantTimer": "Constant Timer",
    "GaussianRandomTimer": "Gaussian Random Timer",
    "UniformRandomTimer": "Uniform Random Timer",
    "ResultCollector": "Listener",
    "CSVDataSet": "CSV Data Set",
    "Arguments": "User Defined Variables",
    "LoopController": "Loop Controller",
    "IfController": "If Controller",
    "WhileController": "While Controller",
}


def _string_props(node: ET.Element) -> dict:
    """Read <stringProp name='...'>value</stringProp> children into a dict."""
    out: dict = {}
    for child in node:
        tag = child.tag.lower()
        if tag in ("stringprop", "intprop", "longprop", "boolprop"):
            key = child.attrib.get("name", "")
            if key:
                out[key] = (child.text or "").strip()
    return out


def _summarize_component(elem: ET.Element) -> ComponentInfo:
    """Pull the most useful props from a JMeter element."""
    testclass = elem.attrib.get("testclass") or elem.attrib.get("guiclass") or elem.tag
    name = elem.attrib.get("testname") or testclass
    label = _COMPONENT_LABELS.get(testclass, testclass)
    props_all = _string_props(elem)

    keys_of_interest = {
        "ThreadGroup.num_threads",
        "ThreadGroup.ramp_time",
        "ThreadGroup.duration",
        "LoopController.loops",
        "HTTPSampler.domain",
        "HTTPSampler.path",
        "HTTPSampler.method",
        "HTTPSampler.protocol",
        "HTTPSampler.port",
        "ConstantTimer.delay",
        "RandomTimer.range",
        "Assertion.test_field",
        "filename",
    }
    props = {k: v for k, v in props_all.items() if k in keys_of_interest}
    return ComponentInfo(type=label, name=name, props=props)


def _parse_jmx(jmx_content: str) -> tuple[bool, List[ComponentInfo], List[str]]:
    """Parse a JMX string. Returns (is_valid, components, errors)."""
    errors: List[str] = []
    components: List[ComponentInfo] = []

    if not jmx_content or not jmx_content.strip():
        return False, [], ["JMX vacio"]

    if "<jmeterTestPlan" not in jmx_content:
        errors.append("Falta el elemento raiz <jmeterTestPlan>")

    try:
        root = ET.fromstring(jmx_content)
    except ET.ParseError as e:
        return False, [], [f"XML invalido: {e}"]

    if root.tag != "jmeterTestPlan":
        errors.append(f"Elemento raiz inesperado: <{root.tag}> (esperado <jmeterTestPlan>)")

    # Walk every element with a testclass — those are the JMeter components.
    interesting = (
        "TestPlan", "ThreadGroup", "PostThreadGroup", "SetupThreadGroup",
        "HTTPSamplerProxy", "HTTPSampler", "HeaderManager", "CookieManager",
        "CacheManager", "ConfigTestElement", "ResponseAssertion",
        "DurationAssertion", "SizeAssertion", "JSONPostProcessor",
        "RegexExtractor", "ConstantTimer", "GaussianRandomTimer",
        "UniformRandomTimer", "ResultCollector", "CSVDataSet", "Arguments",
        "LoopController", "IfController", "WhileController",
    )
    for elem in root.iter():
        testclass = elem.attrib.get("testclass") or ""
        if testclass in interesting or elem.tag in interesting:
            try:
                components.append(_summarize_component(elem))
            except Exception:
                continue

    is_valid = not errors and any(c.type in ("Thread Group", "Test Plan") for c in components)
    if not any(c.type == "Test Plan" for c in components):
        errors.append("No se encontro un Test Plan")
        is_valid = False

    return is_valid, components, errors


# ===================== AI CLIENT =====================


def _build_messages(
    base_prompt: str,
    history: Optional[List[ChatMessage]],
    current_jmx: Optional[str] = None,
    file_context: Optional[str] = None,
) -> List[dict]:
    """Compose the message list for the chat completion."""
    messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for m in history:
            if m.role in ("user", "assistant", "system") and m.content:
                messages.append({"role": m.role, "content": m.content})

    parts: List[str] = []
    if file_context:
        parts.append(file_context)
    if current_jmx:
        parts.append(
            "JMX actual (modifica solo lo solicitado y devuelvelo COMPLETO):\n"
            f"```xml\n{current_jmx}\n```"
        )
    parts.append(f"Instruccion del usuario:\n{base_prompt}")
    messages.append({"role": "user", "content": "\n\n".join(parts)})
    return messages


# ===================== FILE PARSING =====================


def _truncate(text: str, limit: int = MAX_FILE_BYTES) -> str:
    """Cap a text blob so we don't blow the AI context."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncado: {len(text) - limit} bytes adicionales omitidos ...]"


def _try_load_json(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _try_load_yaml(raw: str):
    try:
        import yaml  # PyYAML, available per requirements.txt
        return yaml.safe_load(raw)
    except Exception:
        return None


def _format_postman_collection(data: dict) -> str:
    """Walk a Postman Collection v2.x and emit a JMeter-friendly summary."""
    lines: List[str] = []
    info = data.get("info", {}) or {}
    name = info.get("name") or "Postman Collection"
    lines.append(f"COLECCION POSTMAN: {name}")
    schema = info.get("schema") or ""
    if schema:
        lines.append(f"Schema: {schema}")

    variables = data.get("variable") or []
    if variables:
        lines.append("\nVariables de coleccion:")
        for v in variables:
            key = v.get("key") or v.get("name")
            value = v.get("value", "")
            if key:
                lines.append(f"  - {{{{{key}}}}} = {value}")

    counter = {"n": 0}

    def walk(items, parent: str = ""):
        for item in items or []:
            # Folders contain nested items
            if isinstance(item.get("item"), list):
                folder = item.get("name") or ""
                walk(item["item"], parent=f"{parent}/{folder}" if parent else folder)
                continue
            req = item.get("request")
            if not req:
                continue
            counter["n"] += 1
            label = item.get("name") or f"Request {counter['n']}"
            method = (req.get("method") if isinstance(req, dict) else None) or "GET"
            url_obj = req.get("url") if isinstance(req, dict) else None
            if isinstance(url_obj, dict):
                url_str = url_obj.get("raw") or "/".join(url_obj.get("path") or [])
            else:
                url_str = url_obj or ""
            lines.append(f"\n{counter['n']}. [{method}] {label}")
            if parent:
                lines.append(f"   Carpeta: {parent}")
            if url_str:
                lines.append(f"   URL: {url_str}")
            headers = (req.get("header") or []) if isinstance(req, dict) else []
            if headers:
                lines.append("   Headers:")
                for h in headers:
                    if h.get("disabled"):
                        continue
                    hk = h.get("key", "")
                    hv = h.get("value", "")
                    if hk:
                        lines.append(f"     - {hk}: {hv}")
            body = req.get("body") if isinstance(req, dict) else None
            if isinstance(body, dict):
                mode = body.get("mode")
                if mode == "raw" and body.get("raw"):
                    raw = str(body["raw"])
                    lines.append(f"   Body (raw): {raw[:600]}")
                elif mode == "urlencoded":
                    pairs = body.get("urlencoded") or []
                    lines.append(
                        "   Body (urlencoded): "
                        + ", ".join(f"{p.get('key')}={p.get('value')}" for p in pairs[:10])
                    )
                elif mode == "formdata":
                    pairs = body.get("formdata") or []
                    lines.append(
                        "   Body (form-data): "
                        + ", ".join(f"{p.get('key')}={p.get('value', '<file>')}" for p in pairs[:10])
                    )
            # Postman tests give us assertion hints
            events = item.get("event") or []
            for ev in events:
                if ev.get("listen") == "test":
                    script = ev.get("script", {}) or {}
                    exec_lines = script.get("exec") or []
                    test_text = "\n".join(exec_lines[:8])
                    if test_text.strip():
                        lines.append(f"   Tests/Assertions Postman:\n     {test_text[:400]}")

    walk(data.get("item"))
    return "\n".join(lines)


def _format_openapi_spec(data: dict) -> str:
    """Summarize an OpenAPI 3.x / Swagger 2.x spec for the AI."""
    lines: List[str] = []
    info = data.get("info", {}) or {}
    title = info.get("title") or "OpenAPI Spec"
    version = info.get("version") or ""
    lines.append(f"OPENAPI/SWAGGER: {title} v{version}")

    servers = data.get("servers") or []
    if servers:
        lines.append("Servers:")
        for s in servers[:5]:
            lines.append(f"  - {s.get('url', '')}")
    elif data.get("host"):
        scheme = (data.get("schemes") or ["https"])[0]
        base = data.get("basePath", "")
        lines.append(f"Host: {scheme}://{data['host']}{base}")

    paths = data.get("paths") or {}
    if paths:
        lines.append(f"\nEndpoints ({len(paths)} paths):")
        n = 0
        for path, ops in paths.items():
            if not isinstance(ops, dict):
                continue
            for method, op in ops.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                    continue
                n += 1
                summary = (op.get("summary") if isinstance(op, dict) else "") or ""
                lines.append(f"  {n}. [{method.upper()}] {path}  -  {summary}")
                if isinstance(op, dict):
                    params = op.get("parameters") or []
                    if params:
                        names = ", ".join(p.get("name", "?") for p in params[:6])
                        lines.append(f"      params: {names}")
                    if op.get("requestBody"):
                        rb = op["requestBody"]
                        content = (rb or {}).get("content") or {}
                        types = ", ".join(list(content.keys())[:3])
                        if types:
                            lines.append(f"      requestBody content-types: {types}")
                if n >= 80:
                    lines.append("  ... (lista truncada a 80 endpoints)")
                    return "\n".join(lines)
    return "\n".join(lines)


def _detect_and_format(raw: str, filename: str) -> tuple[str, str]:
    """Detect file kind and produce (kind_label, formatted_context).

    kind_label: 'postman' | 'openapi' | 'text'
    formatted_context: text the AI will see, prefixed with a hint.
    """
    raw = _truncate(raw)

    # 1) Try JSON
    parsed = _try_load_json(raw)
    if isinstance(parsed, dict):
        if "info" in parsed and "item" in parsed:
            body = _format_postman_collection(parsed)
            return "postman", (
                "CONTEXTO: el usuario adjunto una coleccion Postman. "
                "Usa esta informacion como fuente de verdad para los samplers JMX.\n\n"
                + body
            )
        if "openapi" in parsed or "swagger" in parsed:
            body = _format_openapi_spec(parsed)
            return "openapi", (
                "CONTEXTO: el usuario adjunto un spec OpenAPI/Swagger. "
                "Genera un sampler por cada operacion relevante.\n\n"
                + body
            )

    # 2) Try YAML for OpenAPI
    if filename.lower().endswith((".yaml", ".yml")) or "openapi:" in raw[:200] or "swagger:" in raw[:200]:
        yaml_data = _try_load_yaml(raw)
        if isinstance(yaml_data, dict) and ("openapi" in yaml_data or "swagger" in yaml_data):
            body = _format_openapi_spec(yaml_data)
            return "openapi", (
                "CONTEXTO: el usuario adjunto un spec OpenAPI/Swagger en YAML.\n\n" + body
            )

    # 3) Fallback: generic text
    return "text", (
        f"CONTEXTO: el usuario adjunto un archivo de referencia ({filename}). "
        f"Usalo como base para generar el JMX.\n\n"
        f"--- CONTENIDO DEL ARCHIVO ---\n{raw}\n--- FIN ---"
    )


def _call_ai(messages: List[dict], ai_conf: dict) -> str:
    """Dispatch to OpenAI or Gemini based on the stored config. Returns raw text."""
    provider = (ai_conf.get("provider") or "").lower()
    model = ai_conf.get("model_name") or ""
    api_key = ai_conf.get("api_key") or ""

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="No hay API key de IA configurada. Configurala en Administracion > Configuracion IA.",
        )

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as e:
            raise HTTPException(status_code=500, detail=f"openai SDK no disponible: {e}")
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model or "gpt-4o",
            messages=messages,
            temperature=0.4,
            max_tokens=8192,
        )
        if not completion.choices:
            raise HTTPException(status_code=502, detail="OpenAI devolvio respuesta vacia")
        return completion.choices[0].message.content or ""

    if provider == "gemini":
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise HTTPException(status_code=500, detail=f"google-generativeai no disponible: {e}")
        genai.configure(api_key=api_key, transport="rest")
        # Gemini does not use the OpenAI chat schema — flatten to a single prompt
        # but keep role markers so the model gets the conversation order.
        flat = []
        for m in messages:
            role = m["role"].upper()
            flat.append(f"[{role}]\n{m['content']}")
        prompt = "\n\n".join(flat)
        model_obj = genai.GenerativeModel(model or "gemini-2.5-flash")
        resp = model_obj.generate_content(
            prompt,
            generation_config={"max_output_tokens": 8192, "temperature": 0.4},
        )
        return (resp.text or "") if resp else ""

    raise HTTPException(
        status_code=400,
        detail=f"Provider de IA no soportado para JMX: {provider!r}. Soportados: openai, gemini.",
    )


# ===================== ENDPOINTS =====================


@router.post("/generate", response_model=AIResponse)
async def generate_jmx(
    body: GenerateRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Generate a JMX script from a natural-language prompt."""
    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )

    messages = _build_messages(body.prompt, body.conversation_history)

    try:
        raw_text = _call_ai(messages, ai_conf)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /generate")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_text)
    if not jmx:
        return AIResponse(
            jmx_content="",
            explanation=explanation or raw_text,
            is_valid=False,
            error="La IA no devolvio un bloque JMX. Reformula tu prompt.",
            components=[],
        )

    is_valid, components, errors = _parse_jmx(jmx)
    return AIResponse(
        jmx_content=jmx,
        explanation=explanation,
        is_valid=is_valid,
        error="; ".join(errors) if errors else None,
        components=components,
    )


class FileGenerateResponse(AIResponse):
    file_kind: Optional[str] = None
    file_content: Optional[str] = None  # echoed back so the FE can persist for /refine
    file_name: Optional[str] = None


@router.post("/generate-from-file", response_model=FileGenerateResponse)
async def generate_jmx_from_file(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    conversation_history: str = Form(""),
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Generate a JMX using an uploaded reference file (Postman / Swagger / text)
    plus an optional natural-language prompt.

    conversation_history is a JSON-encoded list of {role, content} (multipart can't
    nest arrays cleanly, so we serialize it on the FE side).
    """
    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )

    # Read + size-check the file
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="El archivo esta vacio")
    if len(raw_bytes) > MAX_FILE_BYTES:
        # Don't reject — just truncate later in _detect_and_format. Log a warning.
        logger.warning(
            "AI Script Designer: file %s is %d bytes, will be truncated to %d",
            file.filename, len(raw_bytes), MAX_FILE_BYTES,
        )
    try:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {e}")

    filename = file.filename or "archivo"
    kind, file_ctx = _detect_and_format(raw_text, filename)
    logger.info(
        "AI Script Designer: file upload kind=%s name=%s size=%d",
        kind, filename, len(raw_bytes),
    )

    # Parse history (frontend sends JSON because multipart can't nest arrays)
    history: Optional[List[ChatMessage]] = None
    if conversation_history:
        try:
            arr = json.loads(conversation_history)
            history = [ChatMessage(**m) for m in arr if isinstance(m, dict)]
        except (json.JSONDecodeError, ValueError, TypeError):
            history = None

    effective_prompt = (prompt or "").strip() or (
        "Genera un script JMeter profesional basado en el archivo adjunto. "
        "Aplica todas las buenas practicas: variables, headers, assertions, "
        "extractores de correlacion, Cookie Manager y listeners."
    )

    messages = _build_messages(effective_prompt, history, file_context=file_ctx)

    try:
        raw_response = _call_ai(messages, ai_conf)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /generate-from-file")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_response)
    if not jmx:
        return FileGenerateResponse(
            jmx_content="",
            explanation=explanation or raw_response,
            is_valid=False,
            error="La IA no devolvio un bloque JMX. Reformula tu prompt o revisa el archivo.",
            components=[],
            file_kind=kind,
            file_content=_truncate(raw_text),
            file_name=filename,
        )

    is_valid, components, errors = _parse_jmx(jmx)
    return FileGenerateResponse(
        jmx_content=jmx,
        explanation=explanation,
        is_valid=is_valid,
        error="; ".join(errors) if errors else None,
        components=components,
        file_kind=kind,
        file_content=_truncate(raw_text),
        file_name=filename,
    )


@router.post("/refine", response_model=AIResponse)
async def refine_jmx(
    body: RefineRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Refine an existing JMX based on a follow-up prompt."""
    if not body.current_jmx or "<jmeterTestPlan" not in body.current_jmx:
        raise HTTPException(status_code=400, detail="current_jmx no es un JMX valido")

    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )

    file_ctx = None
    if body.file_content:
        # Re-format on each refine so the context stays under the file size cap
        _, file_ctx = _detect_and_format(body.file_content, body.file_name or "archivo_referencia")

    messages = _build_messages(
        body.prompt,
        body.conversation_history,
        current_jmx=body.current_jmx,
        file_context=file_ctx,
    )

    try:
        raw_text = _call_ai(messages, ai_conf)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /refine")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_text)
    if not jmx:
        # If the AI returned no fenced JMX, keep the existing one but report the issue.
        return AIResponse(
            jmx_content=body.current_jmx,
            explanation=explanation or raw_text,
            is_valid=True,
            error="La IA no devolvio un bloque JMX actualizado. Se conserva el actual.",
            components=_parse_jmx(body.current_jmx)[1],
        )

    is_valid, components, errors = _parse_jmx(jmx)
    return AIResponse(
        jmx_content=jmx,
        explanation=explanation,
        is_valid=is_valid,
        error="; ".join(errors) if errors else None,
        components=components,
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_jmx(
    body: ValidateRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Parse a JMX string and return components + structural errors."""
    is_valid, components, errors = _parse_jmx(body.jmx_content)
    return ValidationResponse(is_valid=is_valid, components=components, errors=errors)


@router.post("/download")
async def download_jmx(
    body: DownloadRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Return the JMX as a downloadable .jmx file."""
    if not body.jmx_content or "<jmeterTestPlan" not in body.jmx_content:
        raise HTTPException(status_code=400, detail="JMX invalido")

    filename = (body.filename or "ai_generated_test.jmx").strip()
    if not filename.lower().endswith(".jmx"):
        filename += ".jmx"
    # Sanitize filename — strip path separators
    filename = re.sub(r"[\\/:*?\"<>|]+", "_", filename)

    buffer = io.BytesIO(body.jmx_content.encode("utf-8"))
    return StreamingResponse(
        buffer,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
