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

import asyncio
import csv as csv_module
import io
import os
import json
import logging
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.models.ai_design_data_file import AIDesignDataFile
from app.db.models.ai_script_design import AIScriptDesign
from app.db.models.client import Client
from app.db.models.performance_execution import PerformanceExecution
from app.db.models.user import User
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.ai_script_design import (
    AIScriptDesignDetail,
    AIScriptDesignSaveAs,
    AIScriptDesignSummary,
    AIScriptDesignUpsert,
)
from app.schemas.ai_script_structure import AIScriptStructure
from app.schemas.refine_operations import (
    RefineOperationSet,
    RefineSurgicalRequest,
    RefineSurgicalResponse,
)
from app.services.ai.gemini import (
    OPENAI_DEFAULT_MAX_TOKENS,
    OPENAI_MAX_TOKENS,
    load_ai_config_from_db,
)
from app.schemas.smoke import SmokeSamplerResult, SmokeTestResult
from app.services.engine.har_compressor import compress_har
from app.services.engine.execution_tracker import execution_tracker
from app.services.engine.jmeter_runner import (
    JMeterRunResult,
    cleanup_workdir,
    create_smoke_workdir,
    parse_jtl_summary,
    patch_jmx_for_smoke,
    prepare_full_run_jmx,
    run_jmeter,
    run_jmeter_async,
    _detect_silent_failure,
)
from app.services.engine.csv_reference_validator import (
    find_missing_csv_files,
    build_missing_csv_error_message,
)
from app.services.engine.export_bundle_builder import (
    build_export_bundle,
    build_export_filename,
)
from app.services.engine.jmx_to_structure import parse_jmx_to_structure
from app.services.engine.refine_operations_applier import (
    OperationError,
    apply_operations,
)
from app.services.engine.structure_to_jmx import regenerate_jmx_from_structure

# Max bytes of an uploaded reference file (Postman / Swagger / text / HAR).
# Anything bigger gets truncated to keep OpenAI token usage bounded.
# HF6: subido a 50 MB para HARs reales (Croydonistas-class ~45 MB). HAR
# detectado se comprime antes de mandarlo a la IA con el modulo har_compressor.
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB (Sprint 2.4-HF6, antes 5 MB en HF3)

# Sprint 2.4-HF5 — output ceilings raised so a complete JMX (~95KB ≈ 30K tokens)
# fits without truncation. Generation keeps the legacy 8192 cap to avoid changing
# its behavior; refine uses the model's maximum.
REFINE_OPENAI_FALLBACK_MAX_TOKENS = 16384
REFINE_GEMINI_MAX_TOKENS = 32768

logger = logging.getLogger(__name__)
router = APIRouter()


# ===================== SYSTEM PROMPT =====================

SYSTEM_PROMPT = """
Eres un arquitecto experto en Apache JMeter con 15 anos de
experiencia disenando pruebas de carga empresariales.

Tu tarea es generar scripts JMeter (JMX) COMPLETOS y PROFESIONALES
listos para ejecucion.

═══════════════════════════════════════════════════════════════════════════════
REGLA DE ORO #1 — BODY DE PETICIONES POST/PUT (CRITICA)
═══════════════════════════════════════════════════════════════════════════════

CUANDO un HTTPSamplerProxy tenga body JSON/XML/raw:

CORRECTO: el body va DENTRO del <HTTPSamplerProxy> con postBodyRaw=true:
```xml
<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="..." enabled="true">
  <elementProp name="HTTPsampler.Arguments" elementType="Arguments" guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
    <collectionProp name="Arguments.arguments">
      <elementProp name="" elementType="HTTPArgument">
        <boolProp name="HTTPArgument.always_encode">false</boolProp>
        <stringProp name="Argument.value">{"key":"value"}</stringProp>
        <stringProp name="Argument.metadata">=</stringProp>
      </elementProp>
    </collectionProp>
  </elementProp>
  <stringProp name="HTTPSampler.domain">${host}</stringProp>
  <stringProp name="HTTPSampler.path">/api/resource</stringProp>
  <stringProp name="HTTPSampler.method">POST</stringProp>
  <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
</HTTPSamplerProxy>
<hashTree>
  <HeaderManager>...</HeaderManager>
  <hashTree/>
  <ResponseAssertion>...</ResponseAssertion>
  <hashTree/>
</hashTree>
```

PROHIBIDO: NUNCA pongas el body como `<stringProp name="HTTPSampler.postBodyRaw">` o `<elementProp name="HTTPsampler.Arguments">` SUELTOS en el hashTree fuera del sampler. Eso produce JMX malformado que el editor visual y el motor de JMeter no pueden procesar correctamente.

Si necesitas body raw (JSON, XML, texto):
- Pon postBodyRaw=true DENTRO del sampler.
- Pon el JSON real DENTRO de la collectionProp Arguments.arguments del MISMO sampler.
- El hashTree post-sampler SOLO debe tener: HeaderManager, ResponseAssertion, Extractors, Timers. Nunca props del sampler ni args.

═══════════════════════════════════════════════════════════════════════════════
REGLA DE ORO #2 — TODA VARIABLE REFERENCIADA DEBE ESTAR DEFINIDA (CRITICA)
═══════════════════════════════════════════════════════════════════════════════

SI tu Test Plan referencia ${variable_nombre} en cualquier campo (URL, header, body, path, etc.), DEBE estar definida en uno de estos lugares:

- `<Arguments testname="User Defined Variables">` SEPARADO como elemento HERMANO del TestPlan dentro del hashTree principal (NO uses el slot inline `TestPlan.user_defined_variables` — debe ser un bloque Arguments propio), O
- `<CSVDataSet>` que lea esa variable de un archivo .csv, O
- Un Extractor (RegexExtractor, JSONPostProcessor) que la genere de una respuesta previa.

EJEMPLO CORRECTO de UDV hermano del TestPlan:
```xml
<TestPlan ...>
  <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
    <collectionProp name="Arguments.arguments"/>
  </elementProp>
  ...
</TestPlan>
<hashTree>
  <Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">
    <collectionProp name="Arguments.arguments">
      <elementProp name="host" elementType="Argument">
        <stringProp name="Argument.name">host</stringProp>
        <stringProp name="Argument.value">api.example.com</stringProp>
        <stringProp name="Argument.metadata">=</stringProp>
      </elementProp>
      <elementProp name="scheme" elementType="Argument">
        <stringProp name="Argument.name">scheme</stringProp>
        <stringProp name="Argument.value">https</stringProp>
        <stringProp name="Argument.metadata">=</stringProp>
      </elementProp>
    </collectionProp>
  </Arguments>
  <hashTree/>
  <!-- siguen HTTP Defaults, Cookie/Cache Manager, CSV, ThreadGroup -->
```

NOTA CRITICA: el `TestPlan.user_defined_variables` inline DEBE quedar VACIO (collectionProp sin elementProps). Las variables van SIEMPRE en el bloque `<Arguments>` hermano siguiente.

EJEMPLOS de variables que SIEMPRE debes definir si las usas:
- ${host}, ${port}, ${scheme} -> UDV con valores reales (ej. host=restful-booker.herokuapp.com, scheme=https, port=443).
- ${token} -> Extractor del response de Auth (RegexExtractor con regex "token":"([^"]+)").
- ${bookingid}, ${userid} -> Extractor del response de Create.
- ${firstname}, ${lastname}, ${totalprice} -> CSVDataSet con variableNames="firstname,lastname,totalprice" Y filename que apunte a un .csv.

NUNCA dejes variables huerfanas como ${host}, ${port}, ${firstname}, ${totalprice} sin estar definidas en algun lado. El editor las marca como "Variables sin definir" y el script falla en runtime.

═══════════════════════════════════════════════════════════════════════════════
FUNCIONES JMETER HELPER (USALAS PARA DATOS DINAMICOS)
═══════════════════════════════════════════════════════════════════════════════

Cuando el usuario pida datos dinamicos (timestamps, IDs unicos, valores aleatorios), PREFIERE estas funciones nativas en lugar de hard-codear:

ALEATORIOS:
- ${__Random(min,max)}              -> entero aleatorio entre min y max
- ${__RandomString(length,chars)}   -> string aleatorio
- ${__UUID()}                       -> UUID v4

FECHAS:
- ${__time(yyyy-MM-dd)}             -> fecha actual
- ${__time(yyyy-MM-dd HH:mm:ss)}    -> timestamp completo
- ${__timeShift(yyyy-MM-dd,,P1D,)}  -> fecha + 1 dia
- ${__timeShift(yyyy-MM-dd,,-P7D,)} -> fecha - 7 dias
- ${__RandomDate(yyyy-MM-dd,,2030-12-31,)} -> fecha aleatoria entre hoy y limite
- ${__dateTimeConvert(${var},yyyy-MM-dd,dd/MM/yyyy)} -> convertir formato

CONTADORES:
- ${__counter(FALSE,)}              -> contador global
- ${__counter(TRUE,)}               -> contador por usuario
- ${__intSum(${a},${b})}            -> suma entera

HILOS Y ENTORNO:
- ${__threadNum}                    -> numero de hilo virtual
- ${__machineName()}                -> host de la maquina
- ${__machineIP()}                  -> IP de la maquina
- ${__P(prop_name,default_value)}   -> propiedad JMeter desde linea de comando

VARIABLES Y URL:
- ${__V(var_${num})}                -> interpolar variable con nombre dinamico
- ${__urlencode(${text})}           -> URL-encode

USA estas funciones en vez de poner valores fijos cuando aplica. Por ejemplo, en lugar de "checkin": "2024-12-11" usa "checkin": "${__time(yyyy-MM-dd)}", o un UUID en vez de un ID fijo.

═══════════════════════════════════════════════════════════════════════════════

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


# ===================== ADAPTIVE PROMPT (Sprint 2.7c) =====================
#
# The standard SYSTEM_PROMPT pushes maximal verbosity (header + assertion +
# extractor on EVERY sampler). With large HARs (PeopleSoft / SAP / many
# transactions) that target output blows past the model ceiling and truncates.
# For large inputs we swap to a token-economical prompt instead.

# Thresholds that flip generation into the conservative prompt.
_LARGE_INPUT_BYTE_THRESHOLD = 20_000   # reference file > 20 KB → large input
_MANY_TRANSACTIONS_THRESHOLD = 8       # > 8 unique transactions → large input


# Sprint 2.7c — token-economical prompt for large inputs (big HAR, enterprise
# apps like PeopleSoft / SAP, or many transactions).
SYSTEM_PROMPT_CONSERVATIVE = """Eres un arquitecto experto en Apache JMeter 5.6.3 con 15 anos de experiencia.
Tu trabajo es generar un Test Plan JMeter (JMX) a partir del input del usuario.

CONTEXTO ESPECIAL: el input es GRANDE (HAR voluminoso, app empresarial tipo PeopleSoft/SAP, o muchas transacciones).
DEBES generar un JMX COMPLETO PERO conciso para no agotar el limite de tokens de salida.

REGLAS DE ECONOMÍA DE TOKENS (estrictas):
1. Bodies grandes: si un body POST/PUT tiene >500 caracteres, ENVUELVELO en una variable UDV para reducir verbosidad.
   Por ejemplo, en lugar de copiar 2KB de form-urlencoded inline, define una UDV `BODY_SAMPLER_5` y usa `${BODY_SAMPLER_5}` en el sampler.
2. Headers repetidos: define UN solo Header Manager a nivel Thread Group con los headers comunes (Cookie, User-Agent, Accept, etc.).
   NO repitas headers en cada sampler. Solo anade un Header Manager LOCAL si el sampler necesita headers EXTRA.
3. Extractors: solo agrega Regex Extractor / JSON Extractor si CLARAMENTE el siguiente sampler usa el valor extraido (token de auth, ID, etc.).
   NO agregues extractors "por si acaso".
4. Response Assertions: agrega UNA assertion simple por sampler (response code 200/2xx). NO asserts sobre el body salvo que sea critico.
5. Comentarios XML: NINGUNO. Cero `<!-- ... -->`.
6. Atributos por defecto: omite atributos opcionales (concurrentPool, contentEncoding vacio, etc.). Solo incluye los necesarios.
7. Agrupacion: si hay samplers que llaman al MISMO endpoint con bodies similares, considera agruparlos con un CSV Data Set en lugar de duplicarlos.

ESTRUCTURA OBLIGATORIA (en orden, sin repeticion):
1. `<?xml version="1.0" encoding="UTF-8"?>`
2. `<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">`
3. Test Plan
4. User Defined Variables (host, scheme, port, y los bodies grandes)
5. HTTP Request Defaults (usa ${host}, ${scheme}, ${port})
6. Cookie Manager (clearEachIteration=true)
7. Cache Manager (clearEachIteration=true)
8. Thread Group (1 hilo, 1 loop, ramp 1s — el usuario lo ajusta despues)
9. Header Manager GLOBAL con los headers comunes
10. Samplers HTTP (numerados, nombres descriptivos en espanol)
11. UN listener View Results Tree + UN Summary Report

VARIABLES OBLIGATORIAS:
- host (dominio sin protocolo)
- scheme (http o https)
- port (80, 443, 8080, etc.)

FORMATO DE RESPUESTA:
Envuelve el JMX en un bloque ```xml ... ```. NO anadas explicaciones largas antes/despues.
Una nota breve en espanol al final esta OK, pero el JMX debe ser COMPLETO y CERRADO con `</jmeterTestPlan>`.
""".strip()


def _detect_large_input(prompt: str, file_content: Optional[str]) -> tuple[bool, str]:
    """Decide whether the input is large enough to warrant the conservative prompt.

    Returns (is_large, reason). Two signals on the reference file:
    - raw size over _LARGE_INPUT_BYTE_THRESHOLD bytes, or
    - more than _MANY_TRANSACTIONS_THRESHOLD HAR transactions ("request" keys).
    A prompt without a reference file is treated as small.
    """
    if file_content:
        size_bytes = len(file_content.encode("utf-8"))
        if size_bytes > _LARGE_INPUT_BYTE_THRESHOLD:
            return True, (
                f"archivo de referencia >{_LARGE_INPUT_BYTE_THRESHOLD} bytes "
                f"({size_bytes} bytes)"
            )
        # Small in bytes but many transactions (e.g. a HAR with terse entries).
        transaction_count = file_content.count('"request"')
        if transaction_count > _MANY_TRANSACTIONS_THRESHOLD:
            return True, f"input con muchas transacciones ({transaction_count} entries en HAR)"

    return False, ""


def _select_system_prompt(prompt: str, file_content: Optional[str]) -> tuple[str, dict]:
    """Pick the SYSTEM_PROMPT variant by input size.

    Returns (system_prompt, metadata) where metadata carries prompt_mode and the
    reason — logged by the endpoints so large-input behavior is debuggable.
    """
    is_large, reason = _detect_large_input(prompt, file_content)
    if is_large:
        return SYSTEM_PROMPT_CONSERVATIVE, {
            "prompt_mode": "conservative",
            "large_input_reason": reason,
        }
    return SYSTEM_PROMPT, {
        "prompt_mode": "standard",
        "large_input_reason": None,
    }


# Sprint 2.4-HF5 — system prompt dedicado para refinamiento.
# El SYSTEM_PROMPT general empuja a "generar JMX completos" — el modelo
# entonces re-crea/abrevia en vez de modificar. Este prompt invierte la
# instruccion: preservar todo, modificar solo lo pedido.
REFINE_SYSTEM_PROMPT = """
Eres un Arquitecto experto en Apache JMeter. Tu unica tarea es REFINAR un
Test Plan JMX EXISTENTE segun la instruccion del usuario.

═══════════════════════════════════════════════════════════════════════════════
REGLA ABSOLUTA: PRESERVAR TODO LO EXISTENTE
═══════════════════════════════════════════════════════════════════════════════

Recibes un JMX COMPLETO. Debes devolver el JMX COMPLETO modificado.

OBLIGATORIO:
- Devuelve SIEMPRE el JMX ENTERO, desde <?xml...?> hasta </jmeterTestPlan>.
- Conserva TODOS los Thread Groups, HTTP Samplers, Header Managers,
  Response Assertions, Regex/JSON Extractors, Listeners, CSV Data Sets,
  User Defined Variables y configuraciones que ya existen.
- Aplica UNICAMENTE el cambio que el usuario pide. Todo lo demas queda IDENTICO,
  byte por byte cuando sea posible.

PROHIBIDO ABSOLUTAMENTE:
- NUNCA devuelvas un fragmento o solo la parte modificada.
- NUNCA borres samplers, thread groups o secciones que el usuario no pidio eliminar.
- NUNCA reemplaces el JMX por una version "nueva" mas corta.
- NUNCA uses comentarios placeholder como <!-- Samplers aqui -->,
  <!-- resto del script -->, <!-- ... -->, etc. Si un elemento existia
  en el JMX que recibes, debe aparecer COMPLETO en tu respuesta.
- NUNCA explanas que "omitiste para brevedad" — devuelve TODO.

═══════════════════════════════════════════════════════════════════════════════
PROCESO
═══════════════════════════════════════════════════════════════════════════════

1. Lee el JMX actual COMPLETO (te lo doy abajo, claramente delimitado).
2. Identifica EXACTAMENTE que pide cambiar el usuario.
3. Aplica solo ese cambio sobre el JMX completo.
4. Devuelve el JMX completo resultante.

Las reglas de calidad de generacion siguen aplicando para los cambios:
- Body POST/PUT dentro del sampler con postBodyRaw=true.
- Variables definidas en UDV/CSV/Extractor (nunca huerfanas).
- Funciones JMeter helper (${__time}, ${__UUID}, ${__Random}, etc.)
  cuando se piden datos dinamicos.

═══════════════════════════════════════════════════════════════════════════════
FORMATO DE SALIDA
═══════════════════════════════════════════════════════════════════════════════

Devuelve el XML completo dentro de un bloque ```xml ... ```. Puedes anteceder
con 1-2 lineas explicando que cambio aplicaste, pero el JMX que sigue debe
estar COMPLETO desde <?xml hasta </jmeterTestPlan>.
""".strip()


# Sprint 2.4-HF5.1 — system prompt para el refine quirurgico.
# La IA devuelve SOLO operaciones estructuradas en JSON; el backend las
# aplica a la AIScriptStructure y regenera el JMX localmente. Esto evita
# que la IA escupa el JMX completo (que se truncaba en JMX grandes).
REFINE_SURGICAL_SYSTEM_PROMPT = """
Eres un Arquitecto experto en Apache JMeter. Tu tarea es ANALIZAR un Test Plan
JMX existente y la instruccion del usuario, y devolver SOLO las OPERACIONES
ESTRUCTURADAS necesarias en formato JSON.

═══════════════════════════════════════════════════════════════════════════════
PROTOCOLO OBLIGATORIO
═══════════════════════════════════════════════════════════════════════════════

NO devuelvas XML. NO devuelvas el JMX. NO escribas explicaciones largas.
Devuelve UNICAMENTE un JSON con este shape:

{
  "operations": [ ...lista de operaciones... ],
  "explanation": "frase corta describiendo el cambio",
  "fallback_to_full_refine": false,
  "fallback_reason": null
}

═══════════════════════════════════════════════════════════════════════════════
OPERACIONES SOPORTADAS
═══════════════════════════════════════════════════════════════════════════════

1. update_test_plan
   { "op": "update_test_plan", "fields": { "name": "...", "comments": "...", "functional_mode": false, "serialize_threadgroups": false } }

2. update_thread_group  (modificar TG existente — usa el ID que aparece en la estructura)
   { "op": "update_thread_group", "id": "<id>", "fields": { "name": "...", "num_threads": 50, "ramp_time": 30, "loops": 1, "continue_forever": false, "on_sample_error": "continue", "enabled": true, "stepping": { "start_users_count": 1 } } }

   IMPORTANTE — KIND DEL THREAD GROUP (revisa el marcador STANDARD/STEPPING en la estructura):
   - Si el TG es STANDARD: usa los campos directamente en el root:
       { "num_threads": 50, "ramp_time": 30, "loops": 1, "on_sample_error": "continue" }
   - Si el TG es STEPPING: los campos de carga van DENTRO de "stepping":
       { "num_threads": 50, "stepping": { "initial_delay": 0, "start_users_count": 5, "start_users_period": 10, "ramp_up": 5, "flight_time": 60, "stop_users_count": 5, "stop_users_period": 10 } }
   - `ramp_time` SOLO aplica a TG standard. Para un TG stepping usa `stepping.ramp_up`.
   - Los campos `initial_delay`, `start_users_count`, `start_users_count_burst`, `start_users_period`, `ramp_up`, `flight_time`, `stop_users_count`, `stop_users_period` SOLO existen en stepping — usalos dentro de "stepping".
   - `num_threads` y `on_sample_error` viven en el root del TG en ambos kinds.

3. update_sampler  (modificar HTTPSampler — usa el ID del sampler)
   { "op": "update_sampler", "id": "<id>", "fields": { "name": "...", "method": "POST", "domain": "${host}", "port": "${port}", "protocol": "https", "path": "/api/x", "follow_redirects": true, "use_keepalive": true, "body": { "mode": "raw", "raw_text": "{...JSON...}" } } }

4. update_sampler_child  (modificar HeaderManager, Assertion, Extractor o Timer existente)
   { "op": "update_sampler_child", "sampler_id": "<id>", "child_id": "<id>", "fields": { ... } }

5. update_udvs  (REEMPLAZA TODA la lista de variables globales)
   { "op": "update_udvs", "udvs": [ {"name": "host", "value": "api.example.com"}, {"name": "scheme", "value": "https"} ] }

6. update_csv_dataset
   { "op": "update_csv_dataset", "id": "<id>", "fields": { "testname": "...", "filename": "data/users.csv", "variable_names": ["firstname","lastname"], "delimiter": ",", "share_mode": "shareMode.all" } }

7. update_http_defaults
   { "op": "update_http_defaults", "fields": { "protocol": "https", "domain": "${host}", "port": "${port}", "path": "/api" } }

8. set_enabled  (activar/desactivar)
   { "op": "set_enabled", "target_kind": "thread_group", "id": "<id>", "enabled": false }
   target_kind soportado: "thread_group", "sampler", "sampler_child" (requiere sampler_id), "csv_data_set", "listener", "cookie_manager" (sin id), "cache_manager" (sin id)

9. add_sampler  (agregar HTTPSampler a un Thread Group existente)
   { "op": "add_sampler", "thread_group_id": "<tg_id>", "sampler": { "name": "1. Login", "method": "POST", "path": "/auth", "body": { "mode": "raw", "raw_text": "{\\"u\\":\\"x\\"}" } }, "position": null }

10. add_sampler_child  (agregar HeaderManager, Assertion, Extractor o Timer a un sampler)
    { "op": "add_sampler_child", "sampler_id": "<sampler_id>", "child_kind": "header_manager|response_assertion|regex_extractor|json_extractor|constant_timer", "data": { ... } }

    Campos por child_kind (todos opcionales con defaults):
    - header_manager: { "headers": [{"name":"Content-Type","value":"application/json"}] }
    - response_assertion: { "test_field": "Assertion.response_code", "test_type": 2, "test_strings": ["200"] }
    - regex_extractor: { "refname": "token", "regex": "\\"token\\":\\"([^\\"]+)\\"", "template": "$1$", "match_number": "1", "default": "NOT_FOUND" }
    - json_extractor: { "refname": "id", "json_path": "$.id", "match_number": "1", "default": "NOT_FOUND" }
    - constant_timer: { "delay_ms": 500 }

11. add_udv  (agregar variable global)
    { "op": "add_udv", "name": "host", "value": "api.example.com" }

12. add_csv_dataset  (agregar CSV Data Set nuevo)
    { "op": "add_csv_dataset", "data": { "testname": "Datos", "filename": "data/users.csv", "variable_names": ["firstname","lastname"], "delimiter": "," } }

13. delete_element  (eliminar cualquier elemento)
    { "op": "delete_element", "target_kind": "sampler|sampler_child|thread_group|csv_data_set|listener|udv", "id": "<id>", "sampler_id": "<solo para sampler_child>", "udv_name": "<solo para udv>" }

14. add_listener  (agregar listener al test plan)
    { "op": "add_listener", "listener_kind": "view_results_tree|summary_report|aggregate_report|response_time_graph|backend_listener", "name": "<opcional, se autocompleta segun el kind>" }

    Tipos de listener disponibles:
    - view_results_tree: para debug en desarrollo.
    - summary_report: resumen agregado por sampler.
    - aggregate_report: percentiles y throughput detallados.
    - response_time_graph: grafico de tiempos en el tiempo.
    - backend_listener: envia metricas en tiempo real a InfluxDB del stack Kinetix (por defecto apunta a http://influxdb:8086, bucket=jmeter, org=performance).

    Para customizar el Backend Listener (otro InfluxDB/Graphite/etc.):
    { "op": "add_listener", "listener_kind": "backend_listener", "name": "Mi backend",
      "backend_listener_config": { "implementation": "...", "arguments": [{"name":"influxdbUrl","value":"..."}] } }

═══════════════════════════════════════════════════════════════════════════════
FALLBACK
═══════════════════════════════════════════════════════════════════════════════

Las operaciones de add/delete YA estan soportadas — emitelas directamente
con add_sampler / add_sampler_child / add_udv / add_csv_dataset / delete_element.

Solo emite fallback_to_full_refine=true si el cambio requiere algo que NINGUNA
operacion cubre, por ejemplo:
- Convertir un TG standard a stepping (cambio estructural del kind).
- Agregar un Thread Group nuevo (fuera del MVP).
- Mover elementos entre Thread Groups.
- Cambios masivos que reorganicen mas de la mitad del JMX.

Si necesitas fallback responde:
{ "operations": [], "explanation": "<razon>", "fallback_to_full_refine": true, "fallback_reason": "<motivo>" }

═══════════════════════════════════════════════════════════════════════════════
REGLAS
═══════════════════════════════════════════════════════════════════════════════

- Usa SIEMPRE los IDs reales que aparecen en la AIScriptStructure que recibes para targets de update/delete.
- Para add_*, los IDs los genera el backend — no los inventes en el payload.
- No inventes IDs sobre elementos existentes. Si no encuentras el elemento que el usuario menciona, usa fallback_to_full_refine=true.
- Devuelve SOLO el JSON. Sin markdown, sin ```json```, sin explicaciones antes ni despues.
- Si el usuario pide algo ambiguo, escoge la interpretacion mas conservadora y describela en "explanation".

═══════════════════════════════════════════════════════════════════════════════
EJEMPLOS
═══════════════════════════════════════════════════════════════════════════════

Usuario: "Cambia el ramp-up del primer TG a 45 segundos y deshabilita el listener View Results Tree"

Respuesta:
{
  "operations": [
    { "op": "update_thread_group", "id": "tg-abc-123", "fields": { "ramp_time": 45 } },
    { "op": "set_enabled", "target_kind": "listener", "id": "lst-xyz-789", "enabled": false }
  ],
  "explanation": "Ramp-up del TG a 45s y View Results Tree desactivado",
  "fallback_to_full_refine": false,
  "fallback_reason": null
}

Usuario: "Agrega un sampler POST /api/logout al primer TG y un Response Assertion que verifique status 204"

Respuesta:
{
  "operations": [
    { "op": "add_sampler", "thread_group_id": "tg-abc-123", "sampler": { "name": "Logout", "method": "POST", "path": "/api/logout" } },
    { "op": "add_sampler_child", "sampler_id": "<id del nuevo sampler retornado por el backend tras add>", "child_kind": "response_assertion", "data": { "test_strings": ["204"], "test_field": "Assertion.response_code" } }
  ],
  "explanation": "Sampler Logout y assertion de status 204 agregados",
  "fallback_to_full_refine": false,
  "fallback_reason": null
}

NOTA: cuando combines add_sampler + add_sampler_child sobre el mismo nuevo
sampler, emite SOLO el add_sampler. El backend tambien acepta secuencias en
las que el sampler_id se descubre tras aplicar el primero, pero si tienes
dudas, agrega el sampler con su HeaderManager/Assertion embebido pidiendolo
en el explanation y emitiendo en turnos separados.
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
    # Sprint 2.7a — set when the model hit its output ceiling mid-XML so the FE
    # can show a specific "truncated" hint instead of the generic "reformula".
    truncated: Optional[bool] = None
    partial_samplers: Optional[int] = None
    # Sprint 2.7b — True when the JMX was completed via a second auto-continuation
    # call after the first response was truncated.
    continued: Optional[bool] = None


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


def _detect_truncation(raw_text: str) -> tuple[bool, int, str]:
    """Detect a JMX response that the model cut off mid-XML (output ceiling hit).

    Sprint 2.7a — ported from the /refine path so /generate and
    /generate-from-file can give the same specific hint instead of the generic
    "reformula tu prompt".

    Returns (is_truncated, partial_samplers, message). When is_truncated is
    False the other two are (0, "").
    """
    is_truncated = "<?xml" in raw_text and "</jmeterTestPlan>" not in raw_text
    if not is_truncated:
        return False, 0, ""
    partial_samplers = raw_text.count("<HTTPSamplerProxy")
    message = (
        f"La IA genero una respuesta truncada por limite de tokens del modelo "
        f"(se alcanzaron {partial_samplers} samplers parciales sin cerrar el JMX). "
        "Soluciones: 1) usa un modelo con mayor capacidad de salida "
        "(gpt-4.1, gemini-2.5-flash); 2) reduce el HAR/archivo de referencia; "
        "3) pide solo las transacciones mas criticas."
    )
    return True, partial_samplers, message


# ===================== AUTO-CONTINUATION (Sprint 2.7b) =====================
#
# When the model cuts a JMX off mid-XML (finish_reason=length), 2.7a only
# reported it. 2.7b makes ONE follow-up call asking the model to continue from
# where it stopped, then stitches both halves into a complete JMX. This rescues
# the N samplers already generated (HAR / PeopleSoft-class scripts) instead of
# throwing them away. Max 1 continuation per generation.

# Tail of the partial JMX sent as continuation context (the model only needs the
# immediate cut point, not the whole truncated blob — keeps token usage bounded).
_CONTINUATION_CONTEXT_TAIL_CHARS = 2000


def _extract_partial_xml(raw_text: str) -> str:
    """Extract the XML block from a (possibly truncated) AI response.

    Starts at the first ``<?xml`` and returns to the end, dropping a trailing
    ```` ``` ```` fence if one is present. Returns "" when there is no XML.
    """
    if "<?xml" not in raw_text:
        return ""
    partial = raw_text[raw_text.find("<?xml"):]
    fence_end = partial.find("```")
    if fence_end > 0:
        partial = partial[:fence_end]
    return partial.strip()


def _build_continuation_messages(
    original_prompt: str,
    file_content: Optional[str],
    partial_xml: str,
    samplers_done: int,
) -> List[dict]:
    """Build the chat messages that ask the model to FINISH a truncated JMX.

    The model sees only the tail of the partial XML (the cut point) plus the
    original intent — not the whole reference file again, which already drained
    the first call's budget. It must return ONLY the missing fragment, fenced.
    """
    tail = (
        partial_xml[-_CONTINUATION_CONTEXT_TAIL_CHARS:]
        if len(partial_xml) > _CONTINUATION_CONTEXT_TAIL_CHARS
        else partial_xml
    )

    system_msg = (
        "Eres un asistente experto en Apache JMeter 5.6.3. Tu tarea ahora es "
        "CONTINUAR un JMX que quedo truncado por limite de tokens. Reglas "
        "estrictas:\n"
        "1. NO repitas el contenido ya generado.\n"
        "2. NO incluyas el preambulo <?xml, <jmeterTestPlan>, ni headers ya "
        "presentes.\n"
        "3. Continua EXACTAMENTE desde donde se corto.\n"
        "4. Cierra correctamente todos los elementos XML abiertos.\n"
        "5. Termina con los cierres apropiados: </hashTree> (los que falten) y "
        "</jmeterTestPlan>.\n"
        "6. Envuelve tu respuesta en un bloque ```xml ... ``` que contenga SOLO "
        "el fragmento de continuacion.\n"
        "7. No agregues explicaciones fuera del bloque XML."
    )

    parts: List[str] = [
        f"Prompt original del usuario:\n{original_prompt}",
        "",
    ]
    if file_content:
        parts.append(
            f"(Archivo de referencia ya analizado anteriormente, "
            f"{len(file_content)} chars)"
        )
        parts.append("")
    parts.extend([
        f"Hasta ahora se generaron {samplers_done} samplers parciales.",
        "El JMX se corto aqui (ultimos chars):",
        "",
        "```xml",
        tail,
        "```",
        "",
        "Continua el JMX desde EXACTAMENTE donde se corto. NO repitas el "
        "preambulo. Genera los samplers/elementos que faltan + listeners + "
        "cierres XML. Envuelve la continuacion en ```xml ... ```",
    ])

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _extract_continuation_xml(continuation_raw: str) -> str:
    """Extract the XML fragment from a continuation response.

    Prefers a fenced ```` ```xml ... ``` ```` block; falls back to the trimmed
    raw text when no fence is present.
    """
    fence_match = re.search(r"```(?:xml)?\s*(.*?)```", continuation_raw, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return continuation_raw.strip()


def _assemble_continued_jmx(partial_xml: str, continuation_xml: str) -> str:
    """Stitch the partial JMX and its continuation into one document.

    The continuation prompt forbids repeating the preamble, so a plain
    concatenation (newline-joined) yields a single <jmeterTestPlan> document.
    Well-formedness is validated downstream by _parse_jmx.
    """
    return f"{partial_xml}\n{continuation_xml}"


def _try_continue_truncated_generation(
    partial_raw_text: str,
    original_prompt: str,
    file_content: Optional[str],
    ai_conf: dict,
    samplers_done: int,
) -> tuple[str, bool, str]:
    """Attempt ONE continuation of a truncated JMX generation.

    Returns (final_jmx, success, error_message):
    - On success: (assembled_jmx_with_closing_tag, True, "").
    - On failure: ("", False, reason) — caller falls back to the 2.7a message.

    _call_ai is synchronous (blocking OpenAI/Gemini call), matching how the
    endpoints already invoke it; no await here.
    """
    partial_xml = _extract_partial_xml(partial_raw_text)
    if not partial_xml:
        return "", False, "No se pudo extraer XML parcial del raw_text"

    continuation_messages = _build_continuation_messages(
        original_prompt=original_prompt,
        file_content=file_content,
        partial_xml=partial_xml,
        samplers_done=samplers_done,
    )

    try:
        continuation_raw = _call_ai(continuation_messages, ai_conf)
    except Exception as e:  # noqa: BLE001 — any failure degrades to the 2.7a path
        return "", False, f"Error en llamada de continuacion: {str(e)[:200]}"

    if not continuation_raw or not continuation_raw.strip():
        return "", False, "Continuacion devolvio respuesta vacia"

    continuation_xml = _extract_continuation_xml(continuation_raw)
    if not continuation_xml:
        return "", False, "No se pudo extraer XML de la continuacion"

    assembled = _assemble_continued_jmx(partial_xml, continuation_xml)
    if "</jmeterTestPlan>" not in assembled:
        return "", False, "La continuacion tampoco completo el JMX (sigue truncado)"

    return assembled, True, ""


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
    system_prompt: Optional[str] = None,
) -> List[dict]:
    """Compose the message list for the chat completion."""
    messages: List[dict] = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
    ]
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


def _build_refine_messages(
    user_instruction: str,
    current_jmx: str,
    history: Optional[List[ChatMessage]],
    file_context: Optional[str] = None,
) -> List[dict]:
    """Compose messages for /refine.

    Layout choices (Sprint 2.4-HF5):
    - REFINE_SYSTEM_PROMPT replaces the generative SYSTEM_PROMPT so the model
      sees "preserve everything" as its primary directive.
    - The current JMX is the FIRST block in the user message, framed as an
      immutable base. The instruction comes AFTER and references it.
    - Optional reference file (Postman / Swagger) goes before the JMX so it
      stays available without diluting the JMX block.
    - Conversation history is included verbatim before the new turn so the
      model keeps prior context (and so the user can iterate naturally).
    """
    messages: List[dict] = [
        {"role": "system", "content": REFINE_SYSTEM_PROMPT}
    ]
    if history:
        for m in history:
            if m.role in ("user", "assistant", "system") and m.content:
                messages.append({"role": m.role, "content": m.content})

    parts: List[str] = []
    if file_context:
        parts.append(file_context)
    parts.append(
        "═══════════════════════════════════════════════════════════════\n"
        "JMX ACTUAL — este es el script COMPLETO que debes refinar.\n"
        "NO lo acortes, NO omitas samplers, NO uses placeholders.\n"
        "═══════════════════════════════════════════════════════════════\n"
        f"```xml\n{current_jmx}\n```"
    )
    parts.append(
        "═══════════════════════════════════════════════════════════════\n"
        "INSTRUCCION DEL USUARIO\n"
        "═══════════════════════════════════════════════════════════════\n"
        f"{user_instruction}\n\n"
        "Aplica SOLO ese cambio sobre el JMX completo de arriba. "
        "Conserva todo lo demas IDENTICO. "
        "Devuelve el JMX COMPLETO (desde <?xml hasta </jmeterTestPlan>) "
        "en un bloque ```xml ... ```."
    )
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


def _is_har_file(filename: str, content: str) -> bool:
    """Detect whether the uploaded file is a HAR (HTTP Archive).

    Looks first at the filename extension. As a fallback, inspects the first
    ~2KB of content for the canonical HAR shape: ``{"log": {"entries": [...]}}``.
    """
    if filename and filename.lower().endswith(".har"):
        return True
    sample = (content or "")[:2048]
    if not sample.strip().startswith("{"):
        return False
    try:
        # Try to parse a small prefix. If the full HAR is huge, we cant always
        # parse just 2KB cleanly; fall back to text matching as a last resort.
        data = json.loads(sample)
    except json.JSONDecodeError:
        return (
            '"log"' in sample
            and '"entries"' in sample
            and ('"version"' in sample or '"creator"' in sample)
        )
    if not isinstance(data, dict):
        return False
    log = data.get("log")
    return isinstance(log, dict) and "entries" in log


def _detect_and_format(raw: str, filename: str) -> tuple[str, str]:
    """Detect file kind and produce (kind_label, formatted_context).

    kind_label: 'postman' | 'openapi' | 'har' | 'text'
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


def _call_ai(
    messages: List[dict],
    ai_conf: dict,
    max_tokens_override: Optional[int] = None,
) -> str:
    """Dispatch to OpenAI or Gemini based on the stored config. Returns raw text.

    ``max_tokens_override`` lets callers (notably /refine) raise the output
    cap above the generation default of 8192 so a full JMX (~95KB ≈ 30K tokens)
    fits without truncation.
    """
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
        if max_tokens_override is not None:
            # Refine path: ride the model's actual ceiling instead of the
            # hardcoded 8192 used for first-shot generation.
            model_ceiling = OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)
            effective_max_tokens = min(max_tokens_override, model_ceiling)
        else:
            # Sprint 2.7a — without an override (generation paths), use the
            # model's real output ceiling instead of the legacy fixed 8192 cap.
            # gpt-4o supports 16384; the old 8192 truncated large JMX (HAR /
            # PeopleSoft). Matches the override branch's model_ceiling lookup.
            effective_max_tokens = OPENAI_MAX_TOKENS.get(model, OPENAI_DEFAULT_MAX_TOKENS)
        completion = client.chat.completions.create(
            model=model or "gpt-4o",
            messages=messages,
            temperature=0.4,
            max_tokens=effective_max_tokens,
        )
        if not completion.choices:
            raise HTTPException(status_code=502, detail="OpenAI devolvio respuesta vacia")
        logger.info(
            "AI Script Designer: OpenAI call model=%s max_tokens=%d finish_reason=%s",
            model, effective_max_tokens, completion.choices[0].finish_reason,
        )
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
        gemini_max_tokens = max_tokens_override if max_tokens_override is not None else 8192
        resp = model_obj.generate_content(
            prompt,
            generation_config={"max_output_tokens": gemini_max_tokens, "temperature": 0.4},
        )
        logger.info(
            "AI Script Designer: Gemini call model=%s max_output_tokens=%d",
            model, gemini_max_tokens,
        )
        return (resp.text or "") if resp else ""

    raise HTTPException(
        status_code=400,
        detail=f"Provider de IA no soportado para JMX: {provider!r}. Soportados: openai, gemini.",
    )


# ===================== REFINE SAFETY =====================


def _count_jmx_elements(jmx: str) -> tuple[int, int]:
    """Count thread groups and samplers in a JMX. Used to detect destructive refines.

    Falls back to lightweight string counting if the structured parser cannot
    parse the JMX (e.g. mid-refinement partial output).

    Returns (thread_groups_count, samplers_count).
    """
    try:
        structure = parse_jmx_to_structure(jmx)
    except Exception:
        # Lightweight fallback — tag count, not perfect but enough to detect
        # massive deletions.
        tg = jmx.count("<ThreadGroup ") + jmx.count("<SetupThreadGroup ") + jmx.count("<PostThreadGroup ")
        samplers = jmx.count("<HTTPSamplerProxy ") + jmx.count("<HTTPSampler ")
        return tg, samplers

    tg_count = len(structure.thread_groups)
    sampler_count = 0

    def walk_children(children):
        nonlocal sampler_count
        for ch in children:
            if ch.type == "sampler":
                sampler_count += 1
            elif ch.type == "controller" and ch.controller is not None:
                # Controllers have their own children list of TGChild
                nested = getattr(ch.controller, "children", None) or []
                walk_children(nested)

    for tg in structure.thread_groups:
        walk_children(tg.children)

    return tg_count, sampler_count


def _validate_refine_not_destructive(
    original_jmx: str, refined_jmx: str
) -> tuple[bool, str]:
    """Reject a refinement that lost more than half of the samplers or any TG.

    Returns (is_safe, error_message). When is_safe is False the caller should
    keep the original JMX and surface error_message to the frontend.
    """
    try:
        orig_tgs, orig_samplers = _count_jmx_elements(original_jmx)
        refined_tgs, refined_samplers = _count_jmx_elements(refined_jmx)
    except Exception as e:
        return False, f"No se pudo validar el JMX refinado ({e}). Se conserva el actual."

    if orig_tgs > 0 and refined_tgs < orig_tgs:
        return False, (
            f"El refinamiento eliminó Thread Groups ({orig_tgs} → {refined_tgs}). "
            f"Posible pérdida de contenido — se conserva el JMX actual."
        )
    if orig_samplers > 0 and refined_samplers < orig_samplers * 0.5:
        return False, (
            f"El refinamiento redujo los samplers de {orig_samplers} a {refined_samplers}. "
            f"Posible pérdida de contenido — se conserva el JMX actual."
        )

    return True, ""


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

    # Sprint 2.7c — pick standard vs conservative prompt by input size.
    selected_prompt, prompt_meta = _select_system_prompt(body.prompt, None)
    logger.info(
        "AI Script Designer /generate: prompt_mode=%s%s",
        prompt_meta["prompt_mode"],
        f" ({prompt_meta['large_input_reason']})" if prompt_meta["large_input_reason"] else "",
    )
    messages = _build_messages(
        body.prompt, body.conversation_history, system_prompt=selected_prompt
    )

    try:
        raw_text = _call_ai(messages, ai_conf)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /generate")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_text)
    continued = False
    if not jmx:
        # Sprint 2.7a — distinguish "model hit its output ceiling mid-XML"
        # from "no JMX at all"; the first needs a model/size hint, not a reprompt.
        is_truncated, partial_samplers, trunc_msg = _detect_truncation(raw_text)
        if is_truncated:
            # Sprint 2.7b — try ONE auto-continuation before surfacing the error.
            logger.info(
                "AI Script Designer /generate: JMX truncado, intentando "
                "auto-continuacion (samplers=%d)", partial_samplers,
            )
            assembled_jmx, cont_ok, cont_err = _try_continue_truncated_generation(
                partial_raw_text=raw_text,
                original_prompt=body.prompt,
                file_content=None,
                ai_conf=ai_conf,
                samplers_done=partial_samplers,
            )
            if cont_ok:
                logger.info(
                    "AI Script Designer /generate: auto-continuacion OK (%d chars)",
                    len(assembled_jmx),
                )
                jmx = assembled_jmx
                explanation = (
                    f"JMX generado en 2 pasos por limite de tokens "
                    f"({partial_samplers} samplers en la primera pasada, resto "
                    f"completado en la continuacion automatica)."
                )
                continued = True
            else:
                logger.warning(
                    "AI Script Designer /generate: auto-continuacion fallo: %s",
                    cont_err,
                )
                return AIResponse(
                    jmx_content="",
                    explanation=explanation or raw_text,
                    is_valid=False,
                    error=(
                        f"{trunc_msg} Intento automatico de continuacion tambien "
                        f"fallo: {cont_err}."
                    ),
                    components=[],
                    truncated=True,
                    partial_samplers=partial_samplers,
                )
        else:
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
        continued=True if continued else None,
    )


class FileGenerateResponse(AIResponse):
    file_kind: Optional[str] = None
    file_content: Optional[str] = None  # echoed back so the FE can persist for /refine
    file_name: Optional[str] = None
    # Sprint 2.4-HF6 — HAR compression stats so the FE can show the user
    # how much was reduced. Only populated when the uploaded file is a HAR.
    compression_stats: Optional[dict] = None


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

    # Sprint 2.4-HF6 — HAR detection + compression BEFORE sending to the AI.
    # Real HARs can be 30-50 MB; raw they blow the LLM context. The compressor
    # filters static assets + tracking, dedups by canonical URL + body hash,
    # and truncates oversized bodies, typically reducing size by 80-99%.
    compression_stats: Optional[dict] = None
    if _is_har_file(filename, raw_text):
        try:
            compressed_text, compression_stats = compress_har(raw_text)
            raw_text = compressed_text
            logger.info(
                "AI Script Designer: HAR comprimido %s: %s -> %s bytes "
                "(%.1f%% reduccion), entries %s -> %s",
                filename,
                compression_stats["original_size"],
                compression_stats["compressed_size"],
                compression_stats["reduction_ratio"],
                compression_stats["entries_original"],
                compression_stats["entries_unique"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"HAR invalido: {e}")

    kind, file_ctx = _detect_and_format(raw_text, filename)
    # If we compressed a HAR, hint to the IA explicitly — _detect_and_format
    # would fall into the generic "text" branch otherwise.
    if compression_stats is not None:
        kind = "har"
        file_ctx = (
            "CONTEXTO: el usuario adjunto un HAR (HTTP Archive) que se "
            "comprimio antes de mandarlo a ti — los assets estaticos y los "
            "duplicados ya fueron filtrados, solo quedan las transacciones "
            "logicas unicas. Usa los entries como base para los samplers JMX. "
            "Cuando veas _duplicate_count en un entry, significa que la misma "
            "transaccion aparecio varias veces durante la grabacion.\n\n"
            "--- HAR COMPRIMIDO ---\n"
            f"{raw_text}\n"
            "--- FIN ---"
        )
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

    # Sprint 2.7c — large HAR/PeopleSoft inputs use the token-economical prompt.
    # raw_text here is the (already compressed) reference payload.
    selected_prompt, prompt_meta = _select_system_prompt(effective_prompt, raw_text)
    logger.info(
        "AI Script Designer /generate-from-file: prompt_mode=%s%s",
        prompt_meta["prompt_mode"],
        f" ({prompt_meta['large_input_reason']})" if prompt_meta["large_input_reason"] else "",
    )
    messages = _build_messages(
        effective_prompt, history, file_context=file_ctx, system_prompt=selected_prompt
    )

    try:
        raw_response = _call_ai(messages, ai_conf)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /generate-from-file")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_response)
    continued = False
    if not jmx:
        # Sprint 2.7a — a truncated HAR/PeopleSoft generation is the common
        # failure here; give the size/model hint instead of "revisa el archivo".
        is_truncated, partial_samplers, trunc_msg = _detect_truncation(raw_response)
        if is_truncated:
            # Sprint 2.7b — try ONE auto-continuation before surfacing the error.
            logger.info(
                "AI Script Designer /generate-from-file: JMX truncado, "
                "intentando auto-continuacion (samplers=%d)", partial_samplers,
            )
            assembled_jmx, cont_ok, cont_err = _try_continue_truncated_generation(
                partial_raw_text=raw_response,
                original_prompt=effective_prompt,
                file_content=file_ctx,
                ai_conf=ai_conf,
                samplers_done=partial_samplers,
            )
            if cont_ok:
                logger.info(
                    "AI Script Designer /generate-from-file: auto-continuacion OK "
                    "(%d chars)", len(assembled_jmx),
                )
                jmx = assembled_jmx
                explanation = (
                    f"JMX generado en 2 pasos por limite de tokens "
                    f"({partial_samplers} samplers en la primera pasada, resto "
                    f"completado en la continuacion automatica)."
                )
                continued = True
            else:
                logger.warning(
                    "AI Script Designer /generate-from-file: auto-continuacion "
                    "fallo: %s", cont_err,
                )
                return FileGenerateResponse(
                    jmx_content="",
                    explanation=explanation or raw_response,
                    is_valid=False,
                    error=(
                        f"{trunc_msg} Intento automatico de continuacion tambien "
                        f"fallo: {cont_err}."
                    ),
                    components=[],
                    truncated=True,
                    partial_samplers=partial_samplers,
                    file_kind=kind,
                    file_content=_truncate(raw_text),
                    file_name=filename,
                    compression_stats=compression_stats,
                )
        else:
            return FileGenerateResponse(
                jmx_content="",
                explanation=explanation or raw_response,
                is_valid=False,
                error="La IA no devolvio un bloque JMX. Reformula tu prompt o revisa el archivo.",
                components=[],
                file_kind=kind,
                file_content=_truncate(raw_text),
                file_name=filename,
                compression_stats=compression_stats,
            )

    is_valid, components, errors = _parse_jmx(jmx)
    return FileGenerateResponse(
        jmx_content=jmx,
        explanation=explanation,
        is_valid=is_valid,
        error="; ".join(errors) if errors else None,
        components=components,
        continued=True if continued else None,
        file_kind=kind,
        file_content=_truncate(raw_text),
        file_name=filename,
        compression_stats=compression_stats,
    )


@router.post("/refine", response_model=AIResponse)
async def refine_jmx(
    body: RefineRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Refine an existing JMX based on a follow-up prompt.

    Sprint 2.4-HF5:
    - Uses REFINE_SYSTEM_PROMPT (preserve-everything directive) instead of
      the generative SYSTEM_PROMPT.
    - Raises max_tokens to the model ceiling so a full JMX fits without
      truncation (was hardcoded 8192, often clipped the response mid-sampler).
    - Validates the refined JMX against the original — rejects destructive
      refines (lost > 50% samplers or any Thread Group) and keeps the
      original instead.
    """
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

    messages = _build_refine_messages(
        user_instruction=body.prompt,
        current_jmx=body.current_jmx,
        history=body.conversation_history,
        file_context=file_ctx,
    )

    # Pick a max_tokens ceiling that allows the model to output a complete JMX.
    provider = (ai_conf.get("provider") or "").lower()
    if provider == "openai":
        max_tokens_refine = OPENAI_MAX_TOKENS.get(
            ai_conf.get("model_name") or "",
            REFINE_OPENAI_FALLBACK_MAX_TOKENS,
        )
    else:
        max_tokens_refine = REFINE_GEMINI_MAX_TOKENS

    logger.info(
        "AI Script Designer /refine: provider=%s model=%s current_jmx_chars=%d max_tokens=%d",
        provider, ai_conf.get("model_name"), len(body.current_jmx), max_tokens_refine,
    )

    try:
        raw_text = _call_ai(messages, ai_conf, max_tokens_override=max_tokens_refine)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI call failed in /refine")
        raise HTTPException(status_code=502, detail=f"Error llamando al proveedor de IA: {e}")

    jmx, explanation = _extract_jmx_and_explanation(raw_text)
    if not jmx:
        # No fenced JMX block — keep the current JMX and report.
        # If the response *started* a JMX but didn't close </jmeterTestPlan>,
        # the model hit its output ceiling mid-XML; give a more specific hint.
        truncated_xml = (
            "<?xml" in raw_text and "</jmeterTestPlan>" not in raw_text
        )
        if truncated_xml:
            err_msg = (
                "La respuesta de la IA quedo truncada (output incompleto). "
                "El JMX es demasiado grande para el modelo actual. "
                "Se conserva el JMX actual. Considera usar un modelo con "
                "mayor capacidad (gpt-4.1, gemini-2.5-flash) o pedir cambios "
                "mas localizados."
            )
        else:
            err_msg = "La IA no devolvio un bloque JMX actualizado. Se conserva el actual."
        return AIResponse(
            jmx_content=body.current_jmx,
            explanation=explanation or raw_text,
            is_valid=True,
            error=err_msg,
            components=_parse_jmx(body.current_jmx)[1],
        )

    # Anti-destructive guard: if the refined JMX lost massive content vs the
    # original (truncated mid-output, removed samplers, dropped a Thread Group),
    # reject the refinement and keep the original.
    is_safe, safety_error = _validate_refine_not_destructive(body.current_jmx, jmx)
    if not is_safe:
        logger.warning(
            "AI Script Designer /refine: destructive output rejected — %s", safety_error,
        )
        return AIResponse(
            jmx_content=body.current_jmx,
            explanation=explanation or "",
            is_valid=True,
            error=safety_error,
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


# =========================================================================
# Sprint 2.4-HF5.1 — Refine quirurgico (structured operations)
# =========================================================================


def _build_structure_summary(structure) -> str:
    """Build a textual summary of the AIScriptStructure so the AI can target
    elements by their real IDs without having to re-parse the JMX itself.
    """
    lines: List[str] = []
    lines.append(f"TestPlan: name='{structure.test_plan.name}'")

    if structure.user_defined_variables:
        lines.append(
            "UDVs ({}): {}".format(
                len(structure.user_defined_variables),
                ", ".join(
                    f"{v.name}={v.value}" for v in structure.user_defined_variables
                ),
            )
        )

    if structure.http_defaults:
        d = structure.http_defaults
        lines.append(
            f"HttpDefaults: protocol={d.protocol or '-'} domain={d.domain or '-'} "
            f"port={d.port or '-'} path={d.path or '-'}"
        )

    if structure.cookie_manager:
        lines.append(
            f"CookieManager: enabled={structure.cookie_manager.enabled} "
            f"clear_each_iteration={structure.cookie_manager.clear_each_iteration}"
        )
    if structure.cache_manager:
        lines.append(
            f"CacheManager: enabled={structure.cache_manager.enabled} "
            f"clear_each_iteration={structure.cache_manager.clear_each_iteration}"
        )

    for ds in structure.csv_data_sets:
        lines.append(
            f"CSV id={ds.id} testname='{ds.testname}' enabled={ds.enabled} "
            f"filename={ds.filename} vars={ds.variable_names}"
        )

    for tg in structure.thread_groups:
        lines.append("")
        # Sprint 2.4-HF5.2 — marca cada TG como STANDARD o STEPPING y lista
        # los campos que aplican en cada caso para que la IA escoja bien.
        kind_label = "STEPPING" if tg.kind == "stepping" else "STANDARD"
        lines.append(
            f"ThreadGroup id={tg.id} name='{tg.name}' kind={kind_label} "
            f"enabled={tg.enabled}"
        )
        if tg.kind == "standard":
            lines.append(
                f"  Campos standard: num_threads={tg.num_threads}, "
                f"ramp_time={tg.ramp_time}, loops={tg.loops}, "
                f"on_sample_error={tg.on_sample_error}"
            )
        elif tg.kind == "stepping" and tg.stepping is not None:
            s = tg.stepping
            lines.append(
                f"  Campos stepping: num_threads={tg.num_threads}, "
                f"initial_delay={s.initial_delay}, "
                f"start_users_count={s.start_users_count}, "
                f"start_users_period={s.start_users_period}, "
                f"ramp_up={s.ramp_up}, flight_time={s.flight_time}, "
                f"stop_users_count={s.stop_users_count}, "
                f"stop_users_period={s.stop_users_period}"
            )
        for ch in tg.children:
            if ch.type == "sampler" and ch.sampler is not None:
                s = ch.sampler
                lines.append(
                    f"  Sampler id={s.id} name='{s.name}' method={s.method} "
                    f"path={s.path or '-'} enabled={s.enabled} body.mode={s.body.mode}"
                )
                for sc in s.children:
                    child_name = getattr(sc.data, "name", "?")
                    child_id = getattr(sc.data, "id", "?")
                    lines.append(
                        f"    Child id={child_id} type={sc.type} name='{child_name}'"
                    )
            elif ch.type == "controller" and ch.controller is not None:
                lines.append(
                    f"  Controller id={ch.controller.id} "
                    f"name='{ch.controller.name}' kind={ch.controller.kind}"
                )

    for li in structure.listeners:
        lines.append(
            f"Listener id={li.id} kind={li.kind} name='{li.name}' enabled={li.enabled}"
        )

    return "\n".join(lines)


def _parse_ai_operations(raw_response: str) -> RefineOperationSet:
    """Extract the operations JSON from the AI response, tolerant to markdown."""
    text = (raw_response or "").strip()

    # Strip markdown fences if the AI used them despite being told not to
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl > 0:
            text = text[first_nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # As a last resort, try to extract the first JSON object from a noisy response
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start: end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"La IA no devolvio JSON valido: {e}")

    return RefineOperationSet(**data)


@router.post("/refine-surgical", response_model=RefineSurgicalResponse)
async def refine_jmx_surgical(
    payload: RefineSurgicalRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Surgical refine: ask the AI for structured operations only (not the
    full JMX), apply them to the parsed AIScriptStructure, and regenerate
    the JMX locally.

    If the change requires add/delete (not supported in MVP) the AI returns
    ``fallback_to_full_refine=true`` and the frontend falls back to the
    classic /refine endpoint from HF5.
    """
    # 1. Parse the current JMX
    try:
        structure = parse_jmx_to_structure(payload.current_jmx)
    except Exception as e:
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=False,
            error=f"El JMX actual no se pudo parsear: {e}",
        )

    # 2. Build the contextual prompt for the AI
    structure_summary = _build_structure_summary(structure)
    user_message = (
        "ESTRUCTURA ACTUAL DEL JMX (usa estos IDs reales en tus operaciones):\n\n"
        f"{structure_summary}\n\n"
        "═══════════════════════════════════════════════\n"
        "INSTRUCCION DEL USUARIO:\n"
        f"{payload.prompt}\n\n"
        "Devuelve SOLO el JSON con las operaciones."
    )

    # 3. Load AI config
    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )

    # 4. Build messages — reuse _build_messages with our surgical system_prompt.
    #    The conversation_history is passed verbatim (dicts → ChatMessage).
    history_msgs: List[ChatMessage] = []
    for m in payload.conversation_history or []:
        try:
            history_msgs.append(
                ChatMessage(
                    role=str(m.get("role", "user")),
                    content=str(m.get("content", "")),
                )
            )
        except Exception:
            continue

    messages = _build_messages(
        base_prompt=user_message,
        history=history_msgs or None,
        system_prompt=REFINE_SURGICAL_SYSTEM_PROMPT,
    )

    # 5. Call the AI. The operations JSON is small, 4096 is plenty.
    try:
        raw_response = _call_ai(messages, ai_conf, max_tokens_override=4096)
    except HTTPException:
        raise
    except Exception as e:
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=True,
            error=f"Error llamando a la IA: {e}",
        )

    logger.info(
        "AI Script Designer /refine-surgical: response_chars=%d",
        len(raw_response or ""),
    )

    # 6. Parse the operations JSON
    try:
        op_set = _parse_ai_operations(raw_response)
    except ValueError as e:
        # Bad JSON → signal fallback so the frontend retries with /refine
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=True,
            fallback_used=True,
            fallback_reason=f"La IA quirurgica no devolvio JSON valido: {e}",
            error="Fallback al refine clasico necesario",
        )

    # 7. AI itself requested a fallback (add/delete required)
    if op_set.fallback_to_full_refine:
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=True,
            fallback_used=True,
            fallback_reason=op_set.fallback_reason
            or "Requiere agregar/borrar elementos no soportado en MVP",
            explanation=op_set.explanation,
        )

    # 8. Apply the operations to the structure
    try:
        structure, applied = apply_operations(structure, op_set.operations)
    except OperationError as e:
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=True,
            error=f"No se pudo aplicar la operacion: {e}",
            explanation=op_set.explanation,
        )

    # 9. Regenerate the JMX locally from the mutated structure
    try:
        new_jmx = regenerate_jmx_from_structure(structure)
    except Exception as e:
        logger.exception("Error regenerando JMX en /refine-surgical")
        return RefineSurgicalResponse(
            jmx_content=payload.current_jmx,
            is_valid=False,
            error=f"Error regenerando JMX: {e}",
        )

    return RefineSurgicalResponse(
        jmx_content=new_jmx,
        is_valid=True,
        explanation=op_set.explanation,
        operations_applied=applied,
        fallback_used=False,
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


@router.get("/designs/{design_id}/export-bundle")
async def export_design_bundle(
    design_id: UUID,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """HF14b: descarga el diseno como bundle portable.

    - Sin CSVs → JMX puro (.jmx).
    - Con CSVs → ZIP con script.jmx (UDV ``Data`` reescrita a ``./Data``) +
      carpeta ``Data/`` con los CSV fisicos + README.

    El filename ({cliente}_{nombre}_{timestamp}.{ext}) viaja en Content-Disposition
    y en el header X-Filename (ambos expuestos via CORS expose_headers).
    """
    q = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    res = await db.execute(q)
    design = res.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Diseno no encontrado")

    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a este diseno")

    if not design.current_jmx:
        raise HTTPException(status_code=400, detail="El diseno no tiene JMX generado")

    # Archivos CSV fisicos asociados (leer bytes desde file_path; fallback a base+stored).
    q_csv = select(AIDesignDataFile).where(AIDesignDataFile.design_id == design.id)
    csv_res = await db.execute(q_csv)
    data_files = list(csv_res.scalars().all())

    uploads_base = f"/app/uploads/ai_data_files/{design.id}"
    csv_payload: list = []
    for df in data_files:
        src = df.file_path if (df.file_path and os.path.exists(df.file_path)) else \
            os.path.join(uploads_base, df.stored_filename)
        if not os.path.exists(src):
            continue
        try:
            with open(src, "rb") as f:
                csv_payload.append((df.original_filename, f.read()))
        except Exception:  # noqa: BLE001 — best-effort, omitir CSV ilegible
            continue

    payload, mime = build_export_bundle(
        jmx_content=design.current_jmx,
        csv_files=csv_payload,
    )

    # Resolver nombre del cliente (FK client_id → tabla clients; sin relationship).
    client_name = None
    if design.client_id:
        cres = await db.execute(select(Client.name).where(Client.id == design.client_id))
        client_name = cres.scalar_one_or_none()

    extension = "zip" if mime == "application/zip" else "jmx"
    filename = build_export_filename(
        design_name=design.name or "diseno",
        client_name=client_name,
        extension=extension,
    )

    return Response(
        content=payload,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Has-CSVs": "1" if csv_payload else "0",
            "X-Filename": filename,
        },
    )


# =========================================================================
# AI Script Design — Persistencia de sesiones
# =========================================================================


def _is_admin(user: User) -> bool:
    return str(getattr(user, "role", "")).lower() == "admin"


def _to_summary(design: AIScriptDesign) -> dict:
    """Convierte un AIScriptDesign a dict resumen (sin conversacion ni JMX completos)."""
    conv = design.conversation or []
    return {
        "id": design.id,
        "session_id": design.session_id,
        "name": design.name,
        "client_id": design.client_id,
        "user_id": design.user_id,
        "is_draft": design.is_draft,
        "message_count": len(conv) if isinstance(conv, list) else 0,
        "has_jmx": bool(design.current_jmx),
        "reference_file_name": design.reference_file_name,
        "reference_file_type": design.reference_file_type,
        "created_at": design.created_at,
        "updated_at": design.updated_at,
    }


@router.get("/designs", response_model=List[AIScriptDesignSummary])
async def list_ai_designs(
    client_id: Optional[UUID] = Query(None),
    include_drafts: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """List AI designs for the current user.

    Admin sees every design; analyst only their own. Filter by ``client_id``
    if provided. Drafts are excluded by default (``include_drafts=true`` to
    include them).
    """
    stmt = select(AIScriptDesign)

    if not _is_admin(current_user):
        stmt = stmt.where(AIScriptDesign.user_id == current_user.id)

    if client_id is not None:
        stmt = stmt.where(AIScriptDesign.client_id == client_id)

    if not include_drafts:
        stmt = stmt.where(AIScriptDesign.is_draft == False)  # noqa: E712

    stmt = stmt.order_by(AIScriptDesign.updated_at.desc())

    result = await db.execute(stmt)
    designs = result.scalars().all()
    return [_to_summary(d) for d in designs]


@router.get("/designs/last-draft", response_model=Optional[AIScriptDesignDetail])
async def get_last_draft(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Devuelve el borrador mas reciente del usuario actual (is_draft=True),
    o null si no tiene ninguno. Sirve para el modal "Continuar?" al entrar
    al disenador sin un designId especifico.

    IMPORTANTE: esta ruta debe declararse ANTES de /designs/{design_id}
    para que "last-draft" no sea interpretado como design_id.
    """
    stmt = (
        select(AIScriptDesign)
        .where(AIScriptDesign.user_id == current_user.id)
        .where(AIScriptDesign.is_draft == True)  # noqa: E712
        .order_by(AIScriptDesign.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()
    return design


@router.get("/designs/{design_id}", response_model=AIScriptDesignDetail)
async def get_ai_design(
    design_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Detalle completo: conversacion + JMX + archivo de referencia."""
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Diseno AI no encontrado")

    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")

    return design


@router.post("/designs/upsert", response_model=AIScriptDesignDetail)
async def upsert_ai_design(
    payload: AIScriptDesignUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Auto-save: UPSERT por session_id.

    - Si no existe: crea como borrador (``is_draft=True``, ``name=None``).
    - Si existe: actualiza conversacion, JMX y archivo de referencia. No
      resetea ``name``/``is_draft`` si ya estaban definidos por Save As.
    - Solo el creador (o admin) puede modificar una sesion existente.
    """
    stmt = select(AIScriptDesign).where(AIScriptDesign.session_id == payload.session_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    # Pydantic → lista de dicts para JSONB
    conv_payload = [
        m.model_dump() if hasattr(m, "model_dump") else dict(m)
        for m in payload.conversation
    ]

    if design is None:
        design = AIScriptDesign(
            session_id=payload.session_id,
            client_id=payload.client_id,
            user_id=current_user.id,
            is_draft=True,
            name=None,
            conversation=conv_payload,
            current_jmx=payload.current_jmx,
            reference_file_name=payload.reference_file_name,
            reference_file_content=payload.reference_file_content,
            reference_file_type=payload.reference_file_type,
        )
        db.add(design)
    else:
        if not _is_admin(current_user) and design.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")

        design.client_id = payload.client_id
        design.conversation = conv_payload
        design.current_jmx = payload.current_jmx
        design.reference_file_name = payload.reference_file_name
        design.reference_file_content = payload.reference_file_content
        design.reference_file_type = payload.reference_file_type

    await db.commit()
    await db.refresh(design)
    return design


@router.patch("/designs/{design_id}/save-as", response_model=AIScriptDesignDetail)
async def save_ai_design_as(
    design_id: UUID,
    payload: AIScriptDesignSaveAs,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Promueve un borrador a diseno guardado formalmente.

    - Asigna ``name`` definitivo (trim aplicado).
    - Marca ``is_draft=False``.
    - Opcionalmente cambia ``client_id``.
    """
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Diseno AI no encontrado")

    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")

    design.name = payload.name.strip()
    design.is_draft = False
    if payload.client_id is not None:
        design.client_id = payload.client_id

    await db.commit()
    await db.refresh(design)
    return design


@router.delete("/designs/{design_id}", status_code=204)
async def delete_ai_design(
    design_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Elimina un diseno AI. Solo el creador o admin."""
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Diseno AI no encontrado")

    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")

    await db.delete(design)
    await db.commit()
    return None


# =========================================================================
# AI Script Structure — Parse JMX a estructura editable
# =========================================================================


class ParseJmxRequest(BaseModel):
    """Payload para parsear un JMX a AIScriptStructure."""
    jmx_text: str = Field(..., min_length=10, description="Contenido raw del JMX a parsear")


@router.post("/parse-jmx", response_model=AIScriptStructure)
async def parse_jmx_endpoint(
    payload: ParseJmxRequest,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """
    Recibe un JMX como string y lo parsea a AIScriptStructure.
    No persiste nada: la estructura se deriva on-demand del JMX original.

    Errores:
    - 422: jmx_text vacio o demasiado corto (validacion Pydantic).
    - 400: JMX malformado o no parseable.
    """
    try:
        structure = parse_jmx_to_structure(payload.jmx_text)
        return structure
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"JMX invalido: {str(e)}")
    except Exception as e:
        logger.exception("Error inesperado en parse-jmx")
        raise HTTPException(status_code=500, detail=f"Error interno parseando JMX: {str(e)}")


# =========================================================================
# AI Script Structure — Regenerar JMX desde estructura editable
# =========================================================================


class RegenerateJmxResponse(BaseModel):
    """Respuesta del endpoint regenerate-jmx."""
    jmx_text: str = Field(..., description="JMX completo regenerado desde la estructura")
    size_chars: int = Field(..., description="Tamano del JMX en caracteres")


@router.post("/regenerate-jmx", response_model=RegenerateJmxResponse)
async def regenerate_jmx_endpoint(
    structure: AIScriptStructure,
    _current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """
    Recibe AIScriptStructure (con flags is_dirty marcando ediciones) y devuelve
    el JMX regenerado.

    Estrategia edit-preserving:
    - Elementos con is_dirty=False reusan raw_xml original.
    - Elementos con is_dirty=True se re-construyen desde campos.

    Errores:
    - 422: payload Pydantic-invalido.
    - 400: ValueError del regenerador (estructura semanticamente invalida).
    - 500: error inesperado del regenerador.
    """
    try:
        jmx_text = regenerate_jmx_from_structure(structure)
        return RegenerateJmxResponse(
            jmx_text=jmx_text,
            size_chars=len(jmx_text),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Estructura invalida: {str(e)}")
    except Exception as e:
        logger.exception("Error inesperado regenerando JMX")
        raise HTTPException(status_code=500, detail=f"Error interno regenerando JMX: {str(e)}")


# =========================================================================
# Sprint 2.5b — Smoke test (ejecucion real con JMeter subprocess)
# =========================================================================


def _read_log_tail(log_path: Optional[str], max_bytes: int = 3000) -> Optional[str]:
    """Lee los ultimos N bytes del log de JMeter (UTF-8 tolerante)."""
    if not log_path or not os.path.exists(log_path):
        return None
    try:
        size = os.path.getsize(log_path)
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # descartar linea parcial
            return f.read()
    except Exception:
        return None


def _parse_jtl_csv_for_smoke(jtl_path: str) -> List[dict]:
    """Lee el JTL CSV y devuelve lista de samples como dicts.

    Solo lee — no usa pandas porque para smoke los samples suelen ser
    decenas. Si el JTL no existe o no es CSV, devuelve [].
    """
    samples: List[dict] = []
    try:
        with open(jtl_path, "r", encoding="utf-8", newline="") as f:
            reader = csv_module.DictReader(f)
            for row in reader:
                samples.append(row)
    except Exception:
        pass
    return samples


def _build_smoke_result(run: JMeterRunResult) -> SmokeTestResult:
    """Construye el SmokeTestResult a partir del run de JMeter."""
    # Caso 1: JMeter ni siquiera arranco (timeout, FileNotFoundError, etc.)
    if run.error_message:
        return SmokeTestResult(
            status="error",
            duration_sec=run.duration_sec,
            total_samples=0,
            successful_samples=0,
            failed_samples=0,
            samplers=[],
            jmeter_log_tail=_read_log_tail(run.jmeter_log_path),
            error_message=run.error_message,
        )

    # Caso 2: JMeter arranco pero exit_code != 0 sin error_message
    # (raro — JMeter suele salir con 0 incluso si los samplers fallan).
    samples = _parse_jtl_csv_for_smoke(run.jtl_path) if run.jtl_path else []

    sampler_results: List[SmokeSamplerResult] = []
    successful = 0
    failed = 0
    for s in samples:
        is_success = (s.get("success", "").lower() == "true")
        if is_success:
            successful += 1
        else:
            failed += 1
        try:
            elapsed = int(s.get("elapsed", "0") or "0")
        except (ValueError, TypeError):
            elapsed = 0
        sampler_results.append(
            SmokeSamplerResult(
                label=s.get("label", "") or "",
                success=is_success,
                response_code=s.get("responseCode", "") or "",
                response_message=s.get("responseMessage", "") or "",
                elapsed_ms=elapsed,
                failure_message=(s.get("failureMessage") or None) or None,
            )
        )

    if not samples:
        # JMeter corrio pero no produjo samples — JMX sin samplers habilitados
        # o el subprocess fallo antes de escribir nada.
        status = "failed"
    elif failed == 0:
        status = "success"
    elif successful == 0:
        status = "failed"
    else:
        status = "partial"

    return SmokeTestResult(
        status=status,
        duration_sec=run.duration_sec,
        total_samples=len(samples),
        successful_samples=successful,
        failed_samples=failed,
        samplers=sampler_results,
        jmeter_log_tail=_read_log_tail(run.jmeter_log_path),
        error_message=None,
    )


@router.post(
    "/designs/{design_id}/smoke-test",
    response_model=SmokeTestResult,
)
async def run_smoke_test(
    design_id: UUID,
    num_threads: int = Query(1, ge=1, le=20, description="Usuarios concurrentes (1-20)"),
    loops: int = Query(1, ge=1, le=5, description="Iteraciones por usuario (1-5)"),
    timeout_sec: int = Query(60, ge=10, le=300, description="Timeout subprocess JMeter (10-300 s)"),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
) -> SmokeTestResult:
    """Ejecuta el JMX del diseno como smoke test (N users / M loops / no scheduler).

    Pasos:
    1. Carga el AIScriptDesign por id y verifica acceso.
    2. Patchea el JMX en memoria con ``patch_jmx_for_smoke``.
    3. Corre ``jmeter -n -t patched.jmx -l result.jtl -j jmeter.log``
       en un workdir temporal.
    4. Parsea el JTL CSV con ``csv.DictReader``.
    5. Devuelve ``SmokeTestResult`` con status/total/samplers + log tail.
    6. Limpia el workdir.
    """
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    res = await db.execute(stmt)
    design = res.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Diseno no encontrado")

    # ACL: admin ve todo, analyst solo lo suyo
    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a este diseno")

    jmx = design.current_jmx
    if not jmx or len(jmx) < 50:
        raise HTTPException(
            status_code=400,
            detail="El diseno no tiene un JMX valido para ejecutar",
        )

    # Sprint 2.5c.1-HF12 — Bug "0/0 samplers": JMeter FileServer no encuentra
    # ${Data}/<original_filename> porque en disco el archivo se llama por su
    # stored_filename (UUID), no por su original_filename. FIX: copiar cada Data
    # File al workdir del smoke usando su original_filename (el nombre que el JMX
    # referencia) y apuntar ${Data} al workdir local. JMeter resuelve y lee bien.
    q_files = select(AIDesignDataFile).where(
        AIDesignDataFile.design_id == design.id
    )
    res_files = await db.execute(q_files)
    data_files = res_files.scalars().all()

    workdir = create_smoke_workdir()
    uploads_base = f"/app/uploads/ai_data_files/{design.id}"

    copied_files: List[str] = []
    skipped_files: List[dict] = []
    for df in data_files:
        src = os.path.join(uploads_base, df.stored_filename)
        dst = os.path.join(workdir, df.original_filename)
        try:
            if os.path.exists(src):
                shutil.copy2(src, dst)
                copied_files.append(df.original_filename)
            else:
                skipped_files.append(
                    {"file": df.original_filename, "reason": f"no existe en {src}"}
                )
        except Exception as e:  # noqa: BLE001 — best-effort, seguir con el smoke
            skipped_files.append({"file": df.original_filename, "reason": str(e)})

    # ${Data} apunta al WORKDIR local (no a /app/uploads/), donde los archivos
    # ya tienen su original_filename.
    data_dir_resolver = {"Data": workdir}

    # HF14a: validar que todo CSV referenciado en el JMX tenga archivo físico
    # disponible (copiado al workdir). Si falta alguno → 400 guiado, no ejecutar.
    missing_csvs = find_missing_csv_files(
        jmx_content=jmx,
        workdir=workdir,
        data_dir_resolver=data_dir_resolver,
        available_filenames=set(copied_files),
    )
    if missing_csvs:
        cleanup_workdir(workdir)
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "csv_missing",
                "message": build_missing_csv_error_message(missing_csvs),
                "missing_csvs": [m["basename"] for m in missing_csvs],
            },
        )

    try:
        patched_jmx = patch_jmx_for_smoke(
            jmx,
            num_threads=num_threads,
            loops=loops,
            data_dir_resolver=data_dir_resolver,
        )
    except ValueError as e:
        cleanup_workdir(workdir)
        raise HTTPException(status_code=400, detail=f"JMX invalido o parametros: {e}")

    try:
        run = run_jmeter(patched_jmx, timeout_sec=timeout_sec, workdir=workdir)
        logger.info(
            "[smoke-test] design=%s threads=%s loops=%s exit=%s duration=%.2fs "
            "samples_will_parse=%s data_files_copied=%s skipped=%s",
            design_id, num_threads, loops, run.exit_code, run.duration_sec,
            bool(run.jtl_path), copied_files, skipped_files,
        )
        result = _build_smoke_result(run)

        # Anexar info de Data Files al log para diagnostico (no rompe el modelo).
        if copied_files or skipped_files:
            extra = (
                f"[HF12] Data Files: copiados={copied_files}, "
                f"omitidos={skipped_files}\n"
            )
            result.jmeter_log_tail = extra + (result.jmeter_log_tail or "")

        return result
    finally:
        cleanup_workdir(workdir)


# ---------------------------------------------------------------------------
# Sprint 2.5d.1 — Ejecucion FULL (no smoke) + historial
# ---------------------------------------------------------------------------

JTL_RESULTS_BASE = "/app/uploads/jtl_results"


@router.post("/designs/{design_id}/execute")
async def execute_full_run(
    design_id: UUID,
    timeout_sec: int = Query(3600, ge=30, le=14400, description="Timeout duro del subprocess JMeter (s)"),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta el JMX del diseno en modo FULL (NO smoke).

    - Respeta ``num_threads`` / ramp / duration del Thread Group.
    - Habilita el Backend Listener (metricas -> InfluxDB/Grafana).
    - Persiste el JTL en ``/app/uploads/jtl_results/{execution_id}/``.
    - Crea una fila en ``performance_executions`` con ``ai_design_id`` = diseno y
      ``scenario_id`` NULL (la ejecucion nacio del Editor IA, no de un Scenario).
    - Lanza un background task y devuelve el ``execution_id`` (int) de inmediato.
    """
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    res = await db.execute(stmt)
    design = res.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Diseno no encontrado")
    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a este diseno")

    jmx = design.current_jmx
    if not jmx or len(jmx) < 50:
        raise HTTPException(
            status_code=400,
            detail="El diseno no tiene un JMX valido para ejecutar",
        )

    # Data Files del diseno (se copiaran al execution_dir con su original_filename).
    q_files = select(AIDesignDataFile).where(AIDesignDataFile.design_id == design.id)
    res_files = await db.execute(q_files)
    data_files = res_files.scalars().all()

    design_name = design.name or "design"

    # 1) INSERT para obtener el id autoincrement (int). El workdir usa ese id.
    perf_exec = PerformanceExecution(
        scenario_id=None,
        user_id=current_user.id,
        ai_design_id=str(design.id),
        status="starting",
        output_filename=f"{design_name}",
        scenario_snapshot={
            "design_id": str(design.id),
            "design_name": design_name,
            "num_data_files": len(data_files),
            "source": "ai_editor",
        },
        started_at=datetime.utcnow(),
    )
    db.add(perf_exec)
    await db.flush()  # asigna perf_exec.id sin cerrar la transaccion
    execution_id = perf_exec.id  # INT

    # 2) Workdir persistente bajo el id de la ejecucion.
    execution_dir = os.path.join(JTL_RESULTS_BASE, str(execution_id))
    os.makedirs(execution_dir, exist_ok=True)

    jtl_path = os.path.join(execution_dir, "result.jtl")
    jmx_path = os.path.join(execution_dir, "test.jmx")
    log_path = os.path.join(execution_dir, "jmeter.log")

    # 3) Copiar Data Files al execution_dir usando su original_filename (mismo
    #    patron que el smoke HF12). ${Data} apuntara al execution_dir.
    copied_files: List[str] = []
    skipped_files: List[dict] = []
    for df in data_files:
        src = df.file_path  # ruta absoluta ya guardada en el modelo
        dst = os.path.join(execution_dir, df.original_filename)
        try:
            if src and os.path.exists(src):
                shutil.copy2(src, dst)
                copied_files.append(df.original_filename)
            else:
                skipped_files.append(
                    {"file": df.original_filename, "reason": f"no existe en {src}"}
                )
        except Exception as e:  # noqa: BLE001 — best-effort
            skipped_files.append({"file": df.original_filename, "reason": str(e)})

    # 4) ${Data} y ${Resultados} -> execution_dir (donde estan los CSV y el JTL).
    data_dir_resolver = {"Data": execution_dir, "Resultados": execution_dir}

    # HF14a: validar CSVs referenciados vs copiados antes de lanzar JMeter.
    # Evita el fallo silencioso "completed con 0 samples".
    missing_csvs = find_missing_csv_files(
        jmx_content=jmx,
        workdir=execution_dir,
        data_dir_resolver=data_dir_resolver,
        available_filenames=set(copied_files),
    )
    if missing_csvs:
        error_msg = build_missing_csv_error_message(missing_csvs)
        perf_exec.status = "error"
        perf_exec.error_message = error_msg
        perf_exec.completed_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "csv_missing",
                "message": error_msg,
                "missing_csvs": [m["basename"] for m in missing_csvs],
            },
        )

    # 5) Preparar JMX FULL (Backend Listener habilitado, sin reducir threads).
    try:
        prepared_jmx = prepare_full_run_jmx(jmx, data_dir_resolver=data_dir_resolver)
    except ValueError as e:
        perf_exec.status = "error"
        perf_exec.error_message = f"JMX invalido: {e}"
        perf_exec.completed_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=400, detail=f"JMX invalido: {e}")

    # 6) Escribir el JMX preparado y persistir rutas.
    with open(jmx_path, "w", encoding="utf-8") as f:
        f.write(prepared_jmx)

    perf_exec.jtl_file_path = jtl_path
    perf_exec.jmx_file_path = jmx_path
    await db.commit()

    logger.info(
        "[execute] design=%s execution_id=%s data_files_copied=%s skipped=%s",
        design_id, execution_id, copied_files, skipped_files,
    )

    # 7) Registrar en el tracker en memoria.
    execution_tracker.register(execution_id, {
        "status": "starting",
        "jtl_path": jtl_path,
        "log_path": log_path,
        "workdir": execution_dir,
        "user_id": str(current_user.id),
        "design_id": str(design.id),
        "start_time": datetime.utcnow().timestamp(),
        "latest_metrics": {},
        "elapsed_sec": 0,
        "pid": None,
    })

    # 8) Lanzar el background task (no await).
    asyncio.create_task(
        _run_full_execution_background(
            execution_id, jmx_path, jtl_path, log_path, execution_dir, timeout_sec
        )
    )

    return {
        "execution_id": execution_id,
        "status": "starting",
        "design_id": str(design.id),
        "execution_dir": execution_dir,
    }


async def _run_full_execution_background(
    execution_id: int,
    jmx_path: str,
    jtl_path: str,
    log_path: str,
    workdir: str,
    timeout_sec: int,
) -> None:
    """Background task: ejecuta JMeter async, actualiza status en DB y tracker.

    El progreso se publica en el tracker (el frontend lo lee por polling en
    ``/performance-executions/{id}/live-metrics``).
    """
    execution_tracker.update(execution_id, status="running")

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
        )
        perf_exec = res.scalar_one_or_none()
        if perf_exec and perf_exec.status not in ("stopping", "cancelled"):
            perf_exec.status = "running"
            await db.commit()

    async def emit_progress(elapsed_sec: float, jtl_size_bytes: int) -> None:
        summary = parse_jtl_summary(jtl_path)
        execution_tracker.update(
            execution_id,
            latest_metrics=summary,
            elapsed_sec=int(elapsed_sec),
        )

    def register_pid(pid: int) -> None:
        execution_tracker.update(execution_id, pid=pid)

    result = await run_jmeter_async(
        jmx_path=jmx_path,
        jtl_path=jtl_path,
        log_path=log_path,
        workdir=workdir,
        timeout_sec=timeout_sec,
        progress_callback=emit_progress,
        pid_callback=register_pid,
    )

    final_summary = parse_jtl_summary(jtl_path)

    # Si el usuario pidio stop, respetar 'cancelled'; si no, completed/error.
    # HF14a: aunque JMeter salga con exit 0, detectar fallos silenciosos
    # (CSV faltante, Test failed!, JTL vacio) y marcar 'error' en vez de 'completed'.
    tracker_data = execution_tracker.get(execution_id) or {}
    silent_failure_msg = ""
    if tracker_data.get("status") in ("stopping", "cancelled"):
        final_status = "cancelled"
    elif result["exit_code"] == 0 and not result.get("error"):
        has_failure, silent_failure_msg = _detect_silent_failure(workdir, jtl_path)
        final_status = "error" if has_failure else "completed"
    else:
        final_status = "error"

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PerformanceExecution).where(PerformanceExecution.id == execution_id)
        )
        perf_exec = res.scalar_one_or_none()
        if perf_exec:
            perf_exec.status = final_status
            perf_exec.completed_at = datetime.utcnow()
            perf_exec.summary_metrics = final_summary
            if result.get("error"):
                perf_exec.error_message = result["error"]
            elif silent_failure_msg:
                perf_exec.error_message = silent_failure_msg
            await db.commit()

    execution_tracker.update(
        execution_id, status=final_status, latest_metrics=final_summary
    )
    logger.info(
        "[execute] execution_id=%s finished status=%s exit=%s duration=%.1fs",
        execution_id, final_status, result.get("exit_code"), result.get("duration_sec", 0),
    )

    # Mantener en el tracker un rato por si el frontend pide el estado final.
    await asyncio.sleep(300)
    execution_tracker.unregister(execution_id)


@router.get("/designs/{design_id}/executions")
async def list_design_executions(
    design_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Historial de ejecuciones FULL de un diseno (mas reciente primero)."""
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    res = await db.execute(stmt)
    design = res.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Diseno no encontrado")
    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sin acceso a este diseno")

    q = (
        select(PerformanceExecution)
        .where(PerformanceExecution.ai_design_id == str(design_id))
        .order_by(PerformanceExecution.started_at.desc().nullslast())
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "execution_id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "summary_metrics": r.summary_metrics,
            "error_message": r.error_message,
        }
        for r in rows
    ]
