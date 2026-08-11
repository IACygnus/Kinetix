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
from app.services.ai.har_flow_analyzer import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    HarAnalysisError,
    analyze_har_flow,
    extract_entries,
    response_body_coverage,
    source_fingerprint,
)
from app.services.ai.har_chunk_router import (
    CHUNK_COMPLETED,
    CHUNK_FAILED,
    CHUNK_PENDING,
    CHUNK_SPLIT,
    GENERATION_COMPLETED,
    GENERATION_FAILED,
    GENERATION_IN_PROGRESS,
    GENERATION_PARTIAL,
    MODE_CHUNKED,
    MODE_SINGLE,
    build_first_chunk_prompt,
    build_next_chunk_prompt,
    can_split_chunk,
    digests_for_chunk,
    get_dependencies_for_chunk,
    group_entries_into_chunks,
    next_free_chunk_id,
    should_use_chunked_generation,
    split_chunk,
    variables_available_from,
)
from app.services.ai.jmx_chunk_assembler import (
    assemble_chunk_into_jmx,
    count_samplers,
    sanitize_generated_jmx,
    # Alias obligatorio: este modulo ya define un endpoint llamado validate_jmx
    # (POST /validate), que ensombreceria el import.
    validate_jmx as validate_assembled_jmx,
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
# HF6: subido a 50 MB para HARs reales (Croydonistas-class ~45 MB). HAR
# detectado se comprime antes de mandarlo a la IA con el modulo har_compressor.
# HF21: subido a 500 MB para HARs enterprise (qa_pideky_com5.har y similares).
MAX_FILE_BYTES = 500 * 1024 * 1024  # 500 MB (Sprint HF21, antes 50 MB en HF6)

# HF21: el tope de CONTEXTO para la IA se separa del tope de UPLOAD. Antes ambos
# eran MAX_FILE_BYTES; subir el upload a 500 MB sin separarlos habria dejado que
# un archivo no-HAR de 500 MB entrara entero al prompt (coste/OOM). El upload
# ahora acepta 500 MB, pero lo que ve el modelo sigue topado en 50 MB — igual
# que antes de HF21.
MAX_CONTEXT_CHARS = 50 * 1024 * 1024  # 50 MB de texto hacia el prompt

# Sprint 2.9 — multi-HAR: tope de archivos por request de /generate-from-file.
_MAX_UPLOAD_FILES = 5

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

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE CORRELACION Y AUTENTICACION (CRITICAS)
═══════════════════════════════════════════════════════════════════════════════

Si el HAR o archivo de referencia muestra cualquiera de estos patrones, DEBES
generar los extractores correspondientes. Un script sin correlacion NO sirve:
los samplers posteriores fallan por usar tokens/IDs vencidos.

1. Tokens JWT / Bearer:
   - Si un response contiene "access_token":"...", "token":"...", "authToken":"..."
     o similar, crea un JSONPostProcessor (o RegexExtractor) en el sampler que
     devuelve el token.
   - Nombra la variable segun la key JSON: ${authToken}, ${access_token}.
   - Usala en samplers posteriores: header Authorization: Bearer ${authToken}.

2. Tokens de transaccion / IDs dinamicos:
   - Si un response trae tokenIdCliente, tokenIdMotor, sessionId, transactionId,
     csrf_token, crea un extractor en el sampler origen.
   - Usa la variable en los samplers posteriores que la necesiten.

3. Cookies de sesion:
   - Si hay Set-Cookie en responses, usa HTTP Cookie Manager (clearEachIteration=true).
   - JMeter maneja las cookies automaticamente: NO crees extractores para cookies.

4. Headers de autenticacion que cambian:
   - Si un sampler envia Authorization: Bearer XXX donde XXX cambia entre requests,
     SIEMPRE crea el extractor del request previo que genero el token y usa
     Authorization: Bearer ${authToken} en un Header Manager local.

EJEMPLO de RegexExtractor para un token JSON:
```xml
<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="Extract authToken" enabled="true">
  <stringProp name="RegexExtractor.useHeaders">false</stringProp>
  <stringProp name="RegexExtractor.refname">authToken</stringProp>
  <stringProp name="RegexExtractor.regex">"access_token"\s*:\s*"([^"]+)"</stringProp>
  <stringProp name="RegexExtractor.template">$1$</stringProp>
  <stringProp name="RegexExtractor.default">NOT_FOUND</stringProp>
  <stringProp name="RegexExtractor.match_number">1</stringProp>
</RegexExtractor>
```

REGLA ABSOLUTA (post HF17) — LOS EXTRACTORES SON OBLIGATORIOS, NO OPCIONALES:
- Si el flujo tiene un endpoint de auth (login/oauth/token, incluido Cognito con
  AccessToken/IdToken en el AuthenticationResult), DEBES generar AL MENOS 1 extractor.
  Un JMX con auth y CERO extractores es INEJECUTABLE: RECHAZA emitirlo asi.
- Usa un JSONPostProcessor (referenceNames + jsonPathExprs) o RegexExtractor (refname +
  regex) en el sampler que devuelve el token, y consume la variable con
  Authorization: Bearer ${AccessToken} en los samplers posteriores.
- Por cada ID dinamico (userId, orderId, sellerId, sessionId) que aparezca en URLs
  posteriores al login, genera 1 extractor por cada ID unico.
- PROHIBIDO hardcodear el token o dejar el header Authorization ausente. PROHIBIDO
  emitir >3 samplers post-auth sin ningun extractor.
- Ante la duda, PREFIERE menos samplers CON extractores que muchos samplers SIN
  correlacion: un script correlacionado corto sirve; uno largo sin correlacion no.

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE MULTI-DOMINIO Y UDV (CRITICAS)
═══════════════════════════════════════════════════════════════════════════════

Si el HAR tiene requests a MULTIPLES dominios:

1. NUNCA hardcodees el dominio en HTTPSampler.domain.
2. CREA una UDV por cada dominio unico, con nombre descriptivo segun su funcion:
   - ${host} o ${host_main} para el dominio principal.
   - ${host_auth} para servicios de autenticacion.
   - ${host_user} para servicios de usuarios.
   - ${host_products}, ${host_pagos}, etc. segun la funcion observable.
3. Cada sampler usa el ${host_xxx} del dominio al que apunta.
4. Detecta el rol del dominio mirando el path:
   - /auth/, /login, /oauth        -> host_auth
   - /users, /user-module          -> host_user
   - /products, /multi_product     -> host_products
   - /orders, /payments, /pagos    -> host_pagos
   - Si no es claro                -> host_1, host_2, ...

EJEMPLO: si el HAR llama a api.banco.com/login, auth-svc.banco.com/oauth/token y
users-api.banco.com/profile, genera 3 UDV (host_main, host_auth, host_user) y usa
${host_main}, ${host_auth}, ${host_user} en los samplers correspondientes.

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE BODIES REALES (CRITICAS)
═══════════════════════════════════════════════════════════════════════════════

- Los cuerpos (bodies) de POST/PUT/PATCH DEBEN ser reales y completos, nunca vacios
  ni placeholders.
- Si usas ${BODY_SAMPLER_N} en un sampler, la UDV BODY_SAMPLER_N DEBE tener
  Argument.value con el body real completo. Una UDV BODY_SAMPLER_N con valor vacio
  ("", "...", "PLACEHOLDER") deja el script INEJECUTABLE: JMeter no resuelve el body,
  el sampler se cuelga y la ejecucion termina con 0 samples.

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE COBERTURA DEL FLUJO (CRITICAS)
═══════════════════════════════════════════════════════════════════════════════

1. Incluye TODOS los requests funcionales del HAR; no resumas ni recortes el flujo.
2. Solo OMITE assets estaticos (.css, .js, .png, .jpg, .woff, .ico) y tracking
   (analytics, telemetry).
3. Cubre el flujo end-to-end COMPLETO: login -> operaciones -> logout. No te
   detengas a la mitad.
4. Si el HAR muestra logout / cerrarSesion, INCLUYELO al final del flujo.
5. Si hay patrones repetidos (mismo endpoint con bodies distintos), genera UN
   sampler parametrizado, no duplicados.
6. NUMERA los samplers en orden cronologico del flujo:
   "1. Login", "2. GetUserInfo", "3. EjecutarMotor", "4. CerrarSesion".

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE MULTI-HAR (cuando el contexto trae varios archivos)
═══════════════════════════════════════════════════════════════════════════════

Si el contexto incluye el marcador "=== FLUJO DIVIDIDO EN N ARCHIVOS ===":
1. Procesa TODOS los archivos como un SOLO flujo continuo (multi-HAR).
2. Si el archivo 1 hace login y extrae authToken, ese mismo authToken se usa en
   los samplers del archivo 2.
3. NO generes 2 JMX separados — genera UN JMX con la secuencia completa.
4. El orden de los samplers es: todos los del archivo 1, luego los del archivo 2,
   etc.
5. Numera los samplers en orden cronologico global: "1. Login (archivo 1)",
   "2. GetUser (archivo 1)", "3. EjecutarOp (archivo 2)", etc.
6. Si el ultimo sampler del archivo N y el primero del archivo N+1 son el mismo
   (la captura se corto y reinicio), genera SOLO uno (deduplicacion).

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

### JERARQUÍA DE REGLAS (cuando dos reglas parezcan competir):

P1 (mas alta): Bodies con valor REAL. Un JMX con UDV vacia es basura. Si tienes
  que elegir entre UDV vacia o body inline truncado, ELIGE inline truncado.

P2: Extractores para tokens/IDs dinamicos. Un flujo autenticado sin extractores
  es un script INEJECUTABLE. Si tienes que elegir entre menos samplers CON extractores
  o mas samplers SIN extractores, ELIGE menos samplers con extractores.

P3: Cobertura del flujo funcional. Cubre TODOS los endpoints del HAR excluyendo
  assets/tracking. Si tienes que sacrificar cobertura por P1 o P2, sacrifica cobertura
  al FINAL del flujo (los samplers menos criticos), no en el medio.

P4: Multi-dominio parametrizado en UDV. NUNCA hardcodees dominios.

P5 (mas baja): Economia de tokens. Reduce verbosidad SOLO si no viola P1-P4.

Si te encuentras eligiendo entre P5 y P1-P4, ELIGE SIEMPRE P1-P4.

Si tu output va a truncarse antes de completar P1+P2+P3, PRIORIZA COMPLETAR
CORRECTAMENTE los primeros 60% de samplers con TODOS sus extractores antes que
enumerar todos superficialmente.

REGLAS DE ECONOMÍA DE TOKENS (estrictas):
1. Bodies grandes — REGLA ABSOLUTA (POST/PUT/PATCH):
   - Si un body tiene <=300 caracteres: PON el body INLINE en el sampler dentro de
     <stringProp name="Argument.value">... el body real ...</stringProp>. NO uses UDV para esto.
   - Si un body tiene >300 caracteres: usa UDV `BODY_SAMPLER_N` PERO el
     <stringProp name="Argument.value"> de esa UDV DEBE contener el body COMPLETO y REAL
     tal como aparece en el HAR/archivo de referencia.
   - PROHIBIDO: crear UDV con Argument.value="" (vacio), "..." (elipsis),
     "PLACEHOLDER", o cualquier stub. Si vas a usar UDV, DEBE tener el valor real completo.
   - Si el body original excede 2000 caracteres y no puedes replicarlo completo por tokens,
     PREFIERE dejar el body inline (truncado si es necesario) antes que usar UDV vacia.
   - Si NO tienes el body real disponible, NO crees el sampler o pon el body como comentario
     XML explicando que falta. Un sampler con body ${BODY_X} y BODY_X="" es INEJECUTABLE:
     JMeter no resuelve el body y el sampler se cuelga sin ejecutarse (timeout con 0 samples).
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

REGLAS CRITICAS NO NEGOCIABLES (aplican AUN en modo conservador):

### REGLA ABSOLUTA #2 (post HF17): EXTRACTORES DE TOKENS

Si el HAR/archivo de referencia muestra CUALQUIERA de estos patrones en un response,
DEBES generar el extractor correspondiente en el sampler que devuelve el valor:

Patrones que EXIGEN extractor:
1. Response con "access_token": "..." o "AccessToken": "..." (Cognito, OAuth)
2. Response con "token": "...", "authToken": "...", "jwt": "..."
3. Response con "IdToken": "...", "RefreshToken": "..." (Cognito)
4. Response con "sessionId": "...", "transactionId": "...", "tokenId": "..."
5. Response con "csrf_token": "...", "xsrf_token": "..."
6. Response con IDs en JSON que se usan en URLs posteriores (/users/{id}, /orders/{id})

CASO INCORRECTO (PROHIBIDO):
Sampler POST /login -> response {"AccessToken":"eyJhbG..."} -> NO crear extractor ->
siguiente sampler usa Authorization: Bearer HARDCODED o falta el header.
Esto es INEJECUTABLE. RECHAZA generar asi.

CASO CORRECTO (OBLIGATORIO):
```xml
<HTTPSamplerProxy testname="1. Login Cognito">
  <!-- ... configuracion del POST ... -->
</HTTPSamplerProxy>
<hashTree>
  <JSONPostProcessor testname="Extract AccessToken">
    <stringProp name="JSONPostProcessor.referenceNames">AccessToken</stringProp>
    <stringProp name="JSONPostProcessor.jsonPathExprs">$.AuthenticationResult.AccessToken</stringProp>
    <stringProp name="JSONPostProcessor.match_numbers">1</stringProp>
    <stringProp name="JSONPostProcessor.defaultValues">NOT_FOUND</stringProp>
  </JSONPostProcessor>
</hashTree>
<!-- Luego, en el sampler siguiente: -->
<HeaderManager>
  <collectionProp name="HeaderManager.headers">
    <elementProp name="Authorization" elementType="Header">
      <stringProp name="Header.name">Authorization</stringProp>
      <stringProp name="Header.value">Bearer ${AccessToken}</stringProp>
    </elementProp>
  </collectionProp>
</HeaderManager>
```

NUMERO MINIMO DE EXTRACTORES:
Si el HAR muestra un flujo con autenticacion (login/auth/token endpoint), DEBES
generar AL MENOS 1 extractor. Si ademas ves IDs dinamicos (userId, orderId, sellerId,
sessionId) en URLs posteriores al login, DEBES generar 1 extractor por cada ID unico.

PROHIBIDO: emitir un JMX con mas de 3 samplers despues de un endpoint de auth
sin ningun extractor. Si vas a hacer eso, DETENTE y anade extractores primero.
Es preferible emitir un JMX con MENOS samplers CON extractores que uno con muchos
samplers SIN correlacion: ELIGE siempre menos samplers con extractores.

MULTI-DOMINIO: si hay >=2 dominios distintos, define una UDV por dominio
(host_main, host_auth, host_user, host_pagos, ...). NUNCA hardcodees dominios en
los samplers; cada sampler usa su ${host_xxx}.

COBERTURA: incluye TODOS los requests funcionales del HAR (omite solo assets y
tracking). Incluye el logout/cerrarSesion si existe en el flujo.

### CHECKPOINT PRE-EMISIÓN (revisa cada punto antes de emitir el JMX):

[ ] 1. Todos los BODY_SAMPLER_N declarados en UDV tienen Argument.value con contenido real (no vacio).
[ ] 2. Todos los BODY_SAMPLER_N declarados en UDV son referenciados por algun sampler con ${BODY_SAMPLER_N}.
     -> Si BODY_SAMPLER_2 esta en UDV pero NO hay ${BODY_SAMPLER_2} en ningun sampler, ELIMINA la UDV.
        Estas desperdiciando tokens con una UDV huerfana.
[ ] 3. Hay al menos 1 extractor por cada endpoint de auth del flujo.
     -> Si el HAR tiene POST /login o /auth y NO hay JSONPostProcessor o RegexExtractor
        que capture el token, DETENTE y anadelo.
[ ] 4. Los headers Authorization posteriores al auth usan ${AccessToken} (o el nombre del extractor).
     -> Si usan un valor hardcodeado o el header esta ausente, EL SCRIPT NO SIRVE.
[ ] 5. Todos los dominios distintos estan parametrizados en UDV.
[ ] 6. El JMX cierra con </jmeterTestPlan>.

Si CUALQUIER check falla, corrige antes de emitir. Es preferible emitir un JMX con
5 samplers bien hechos + extractores que un JMX con 20 samplers sin correlacion.

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


def _truncation_hint_message(partial_samplers: int) -> str:
    """User-facing hint shown when auto-continuation cannot rescue a truncated JMX.

    Split out of _detect_truncation in HF18a so the detector can return a
    machine-readable truncation_type while callers still rebuild this message
    on the failure path (behavior identical to Sprint 2.7a).
    """
    return (
        f"La IA genero una respuesta truncada por limite de tokens del modelo "
        f"(se alcanzaron {partial_samplers} samplers parciales sin cerrar el JMX). "
        "Soluciones: 1) usa un modelo con mayor capacidad de salida "
        "(gpt-4.1, gemini-2.5-flash); 2) reduce el HAR/archivo de referencia; "
        "3) pide solo las transacciones mas criticas."
    )


def _detect_truncation(
    raw_text: str,
    finish_reason: str | None = None,
) -> tuple[bool, int, str]:
    """Detect a JMX response that the model cut off mid-XML.

    Sprint 2.7a — ported from the /refine path so /generate and
    /generate-from-file can give the same specific hint instead of the generic
    "reformula tu prompt". Original detection: raw has ``<?xml`` but no
    ``</jmeterTestPlan>``.

    HF18a — extended to weigh ``finish_reason`` so we also catch the "stop
    mentiroso" failure mode: gpt-4o returns finish_reason="stop" (claims it
    finished) yet cuts the JMX before the closing tag. 2.7b only fired on
    finish_reason="length", so this case slipped through and the frontend
    showed "XML invalido".

    Returns (is_truncated, partial_samplers, truncation_type):
      - is_truncated: True when auto-continuation should be attempted.
      - partial_samplers: count of ``<HTTPSamplerProxy`` in the raw text.
      - truncation_type: "length" | "stop_mentiroso" | "unknown_no_close" |
        "no_truncation" | "no_xml".

    The user-facing hint lives in _truncation_hint_message (callers rebuild it
    from partial_samplers on the failure path).
    """
    if "<?xml" not in raw_text:
        # No JMX started at all — this is not a truncation, it's a non-XML reply.
        return False, 0, "no_xml"

    partial_samplers = raw_text.count("<HTTPSamplerProxy")
    has_closing = "</jmeterTestPlan>" in raw_text

    if has_closing:
        return False, partial_samplers, "no_truncation"

    # JMX started but never closed → truncated. Classify by finish_reason.
    if finish_reason == "length":
        # Classic Sprint 2.7a case: model hit its output-token ceiling.
        return True, partial_samplers, "length"
    if finish_reason == "stop":
        # HF18a: model claims it finished but cut the XML mid-stream (known
        # gpt-4o failure mode with dense prompts / large HARs).
        return True, partial_samplers, "stop_mentiroso"
    # Unknown/absent finish_reason but XML is incomplete → treat as truncated
    # defensively (also preserves the Sprint 2.7a call signature: without a
    # finish_reason an unclosed JMX still activates auto-continuation).
    return True, partial_samplers, "unknown_no_close"


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
        continuation_raw, _ = _call_ai(continuation_messages, ai_conf)
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


def _truncate(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
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
) -> tuple[str, str]:
    """Dispatch to OpenAI or Gemini based on the stored config.

    Returns (raw_text, finish_reason). HF18a — finish_reason is surfaced so
    _detect_truncation can tell "length" (model hit its ceiling) from
    "stop mentiroso" (model claims done but cut the XML). OpenAI reports it
    directly; Gemini's enum is mapped to "length"/"stop"/lowercased-name.

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
        # HF18b — flag any model not in OPENAI_MAX_TOKENS. Without this, a model
        # missing from the dict silently falls back to OPENAI_DEFAULT_MAX_TOKENS
        # (4096) and truncates long JMX with no visible cause (the class of bug
        # that made gpt-4.1 look like a low-coverage model). Warn loudly so the
        # dict gets the entry instead of us chasing phantom truncation.
        if model and model not in OPENAI_MAX_TOKENS:
            logger.warning(
                "AI Script Designer: model '%s' NOT in OPENAI_MAX_TOKENS; "
                "usando default %d (posible truncacion). Agregalo al dict.",
                model, OPENAI_DEFAULT_MAX_TOKENS,
            )
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
        finish_reason = completion.choices[0].finish_reason or "unknown"
        logger.info(
            "AI Script Designer: OpenAI call model=%s max_tokens=%d finish_reason=%s",
            model, effective_max_tokens, finish_reason,
        )
        return completion.choices[0].message.content or "", finish_reason

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
        # HF18a — map Gemini's finish_reason enum to the OpenAI vocabulary so
        # _detect_truncation classifies both providers the same way.
        finish_reason = "stop"
        try:
            if resp and getattr(resp, "candidates", None):
                fr = resp.candidates[0].finish_reason
                fr_name = getattr(fr, "name", str(fr)).upper()
                if "MAX_TOKEN" in fr_name:
                    finish_reason = "length"
                elif fr_name in ("STOP", "1"):
                    finish_reason = "stop"
                else:
                    finish_reason = fr_name.lower()
        except Exception:  # noqa: BLE001 — finish_reason is best-effort metadata
            finish_reason = "stop"
        logger.info(
            "AI Script Designer: Gemini call model=%s max_output_tokens=%d finish_reason=%s",
            model, gemini_max_tokens, finish_reason,
        )
        return ((resp.text or "") if resp else ""), finish_reason

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
        raw_text, finish_reason = _call_ai(messages, ai_conf)
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
        # HF18a — finish_reason also catches the "stop mentiroso" case.
        is_truncated, partial_samplers, truncation_type = _detect_truncation(
            raw_text, finish_reason=finish_reason,
        )
        trunc_msg = _truncation_hint_message(partial_samplers)
        if is_truncated:
            # Sprint 2.7b — try ONE auto-continuation before surfacing the error.
            logger.info(
                "AI Script Designer /generate: JMX truncado (tipo=%s), intentando "
                "auto-continuacion (samplers=%d)", truncation_type, partial_samplers,
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
    # Sprint 2.9 — for multiple files this is the aggregate across all HARs.
    compression_stats: Optional[dict] = None


def _process_uploaded_file(
    filename: str, raw_bytes: bytes
) -> tuple[str, str, str, Optional[dict]]:
    """Decode + (HAR compress) + format ONE uploaded reference file.

    Sprint 2.9 — extracted from the endpoint so multiple files share the exact
    same per-file pipeline. Returns (kind, file_context, raw_reference_text,
    compression_stats). raw_reference_text is the compressed HAR / file text
    (echoed back for /refine); file_context is what the AI sees.
    """
    try:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo {filename}: {e}")

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
            raise HTTPException(status_code=400, detail=f"HAR invalido ({filename}): {e}")

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
    return kind, file_ctx, raw_text, compression_stats


def _build_unified_file_context(processed_files: list) -> str:
    """Build a single AI context from one or more processed files (Sprint 2.9).

    - One file  -> its content verbatim (backward compatible, identical to pre-2.9).
    - N files   -> markers framing the files as ONE continuous business flow so
      the model correlates across them (tokens from file 1 used in file 2, etc.)
      and emits a single JMX covering all of them in order.
    """
    if len(processed_files) == 1:
        return processed_files[0]["content"]

    n = len(processed_files)
    parts = [
        f"=== FLUJO DIVIDIDO EN {n} ARCHIVOS ===",
        "",
        "INSTRUCCION CRITICA: estos archivos representan UN SOLO FLUJO DE NEGOCIO "
        "dividido en partes por limitaciones de captura. Debes procesarlos como una "
        "secuencia continua, MANTENIENDO CORRELACION entre ellos:",
        "  - Tokens extraidos en el archivo 1 se usan en el archivo 2.",
        "  - El ultimo request del archivo N suele conectar con el primer request del archivo N+1.",
        "  - Genera UN SOLO JMX que cubra TODOS los archivos en orden.",
        "",
    ]
    for pf in processed_files:
        parts.append(f"--- ARCHIVO {pf['index']}: {pf['filename']} (kind={pf['kind']}) ---")
        parts.append("")
        parts.append(pf["content"])
        parts.append("")
    parts.append("=== FIN DEL FLUJO ===")
    parts.append("")
    parts.append(
        f"Recuerda: UN solo JMX que cubra los {n} archivos como flujo continuo. "
        "Numera los samplers en orden cronologico (1. ..., 2. ..., ..., N. ...)."
    )
    return "\n".join(parts)


def _aggregate_compression_stats(processed_files: list) -> Optional[dict]:
    """Sum the HAR compression stats across files for the FE banner (Sprint 2.9).

    Returns None when no file was a HAR.
    """
    har_stats = [p["compression_stats"] for p in processed_files if p.get("compression_stats")]
    if not har_stats:
        return None
    orig = sum(s["original_size"] for s in har_stats)
    comp = sum(s["compressed_size"] for s in har_stats)
    return {
        "original_size": orig,
        "compressed_size": comp,
        "reduction_ratio": round((1 - comp / orig) * 100, 1) if orig > 0 else 0,
        "entries_original": sum(s["entries_original"] for s in har_stats),
        "entries_unique": sum(s["entries_unique"] for s in har_stats),
        "entries_static_filtered": sum(s["entries_static_filtered"] for s in har_stats),
        "entries_tracking_filtered": sum(s["entries_tracking_filtered"] for s in har_stats),
        "files": len(processed_files),
    }


@router.post("/generate-from-file", response_model=FileGenerateResponse)
async def generate_jmx_from_file(
    # NOTE: the list MUST NOT be Optional — FastAPI only uses form.getlist() (so a
    # single `files` part becomes a 1-element list) when the annotation is a bare
    # List. Optional[List[...]] makes it treat one part as a scalar and 422s.
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(default=None),
    prompt: str = Form(""),
    conversation_history: str = Form(""),
    _current_user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Generate a JMX from one or more uploaded reference files (HAR / Postman /
    Swagger / text) plus an optional natural-language prompt.

    Sprint 2.9 — accepts MULTIPLE files via the ``files`` field. The legacy
    singular ``file`` field still works (backward compatible). Multiple HARs are
    compressed independently and stitched into one continuous-flow context.

    conversation_history is a JSON-encoded list of {role, content} (multipart can't
    nest arrays cleanly, so we serialize it on the FE side).
    """
    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )

    # Normalize singular/plural inputs into one list (backward compat).
    upload_list: List[UploadFile] = list(files) if files else ([file] if file else [])
    if not upload_list:
        raise HTTPException(
            status_code=400,
            detail="Adjunta al menos un archivo (campo 'files' o 'file').",
        )
    if len(upload_list) > _MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximo {_MAX_UPLOAD_FILES} archivos por request.",
        )

    # Process each file independently (decode + HAR compression + format).
    processed: List[dict] = []
    for idx, up in enumerate(upload_list):
        raw_bytes = await up.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo {up.filename or idx + 1} esta vacio",
            )
        if len(raw_bytes) > MAX_FILE_BYTES:
            logger.warning(
                "AI Script Designer: file %s is %d bytes, will be truncated to %d",
                up.filename, len(raw_bytes), MAX_FILE_BYTES,
            )
        fname = up.filename or f"archivo_{idx + 1}"
        kind_i, ctx_i, raw_i, stats_i = _process_uploaded_file(fname, raw_bytes)
        processed.append({
            "index": idx + 1,
            "filename": fname,
            "kind": kind_i,
            "content": ctx_i,
            "raw": raw_i,
            "compression_stats": stats_i,
        })

    # Downstream code is unchanged: reuse the legacy variable names with
    # multi-aware values (single file => identical behavior to pre-2.9).
    single = len(processed) == 1
    file_ctx = _build_unified_file_context(processed)
    raw_text = processed[0]["raw"] if single else file_ctx
    kind = (
        processed[0]["kind"] if single
        else ("har" if all(p["kind"] == "har" for p in processed) else "mixed")
    )
    filename = (
        processed[0]["filename"] if single
        else ", ".join(p["filename"] for p in processed)
    )
    compression_stats = (
        processed[0]["compression_stats"] if single
        else _aggregate_compression_stats(processed)
    )
    logger.info(
        "AI Script Designer: file upload count=%d kind=%s name=%s",
        len(processed), kind, filename,
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
        raw_response, finish_reason = _call_ai(messages, ai_conf)
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
        # HF18a — finish_reason also catches the "stop mentiroso" case.
        is_truncated, partial_samplers, truncation_type = _detect_truncation(
            raw_response, finish_reason=finish_reason,
        )
        trunc_msg = _truncation_hint_message(partial_samplers)
        if is_truncated:
            # Sprint 2.7b — try ONE auto-continuation before surfacing the error.
            logger.info(
                "AI Script Designer /generate-from-file: JMX truncado (tipo=%s), "
                "intentando auto-continuacion (samplers=%d)",
                truncation_type, partial_samplers,
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
        raw_text, _ = _call_ai(messages, ai_conf, max_tokens_override=max_tokens_refine)
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
        raw_response, _ = _call_ai(messages, ai_conf, max_tokens_override=4096)
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


class HarAnalysisResponse(BaseModel):
    """Resumen del analisis multi-fase del HAR de un diseno (Sprint 3.0 F1)."""

    design_id: UUID
    status: str  # completed | skipped | failed
    total_entries: int = 0
    analyzed_entries: int = 0
    counts: dict = Field(default_factory=dict)
    dependencies_found: int = 0
    reused: bool = False
    error: Optional[str] = None


@router.post("/designs/{design_id}/analyze-har", response_model=HarAnalysisResponse)
async def analyze_design_har(
    design_id: UUID,
    force: bool = Query(False, description="Re-analiza aunque ya haya un analisis vigente"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Analisis multi-fase del HAR de un diseno (Sprint 3.0 — Fundacion 1).

    Design-aware a proposito: ``/generate-from-file`` y ``/refine`` son
    stateless y no tienen donde persistir el resultado. Aca el HAR se lee de la
    fila, se analiza en dos llamadas al modelo (clasificacion + dependencias) y
    las tres columnas ``har_analysis_*`` quedan escritas.

    Nada de esto bloquea la generacion de JMX: un analisis fallido persiste
    ``status='failed'`` y devuelve 200 con el detalle en ``error``, para que un
    fire-and-forget del frontend no explote en la cara del usuario.
    """
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Diseno AI no encontrado")

    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")

    if (design.reference_file_type or "").lower() != "har":
        raise HTTPException(
            status_code=400,
            detail=(
                "El analisis multi-fase solo aplica a disenos con archivo de "
                f"referencia HAR (este es '{design.reference_file_type or 'ninguno'}')."
            ),
        )

    # Idempotencia: el auto-save dispara upsert en cada turno de la conversacion.
    # Sin esta guarda, un fire-and-forget gastaria 2 llamadas al modelo por
    # turno. El hash del HAR vive dentro del JSON de clasificacion para no
    # sumar una cuarta columna a la tabla.
    fingerprint = source_fingerprint(design.reference_file_content)
    previous = design.har_analysis_classification or {}
    if (
        not force
        and design.har_analysis_status == STATUS_COMPLETED
        and isinstance(previous, dict)
        and previous.get("source_sha1") == fingerprint
    ):
        deps_blob = design.har_analysis_dependencies or {}
        return HarAnalysisResponse(
            design_id=design.id,
            status=design.har_analysis_status,
            total_entries=previous.get("total_entries", 0),
            analyzed_entries=previous.get("analyzed_entries", 0),
            counts=previous.get("counts", {}),
            dependencies_found=len(deps_blob.get("dependencies", []) or []),
            reused=True,
        )

    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )
    if not ai_conf.get("api_key"):
        raise HTTPException(
            status_code=503,
            detail="No hay API key de IA configurada. Configurala en Administracion > Configuracion IA.",
        )

    def _analysis_call_ai(messages: List[dict]) -> str:
        # Igual que el resto de los endpoints de este modulo: _call_ai es
        # sincrono y se invoca directo (no hay wrapper a threadpool en el repo).
        text, _finish = _call_ai(messages, ai_conf, max_tokens_override=8192)
        return text

    try:
        outcome = analyze_har_flow(design.reference_file_content, _analysis_call_ai)
    except HarAnalysisError as e:
        # HAR ilegible: se registra el fallo, no se rompe el flujo del usuario.
        logger.warning("analyze-har: HAR ilegible en diseno %s — %s", design_id, e)
        design.har_analysis_status = STATUS_FAILED
        await db.commit()
        return HarAnalysisResponse(
            design_id=design.id, status=STATUS_FAILED, error=str(e)
        )

    design.har_analysis_status = outcome["status"]
    if outcome["classification"] is not None:
        design.har_analysis_classification = outcome["classification"]
    if outcome["dependencies"] is not None:
        design.har_analysis_dependencies = outcome["dependencies"]
    await db.commit()

    classification = outcome["classification"] or {}
    dependencies = outcome["dependencies"] or {}
    logger.info(
        "analyze-har: diseno %s status=%s counts=%s deps=%d",
        design_id,
        outcome["status"],
        classification.get("counts"),
        len(dependencies.get("dependencies", []) or []),
    )

    return HarAnalysisResponse(
        design_id=design.id,
        status=outcome["status"],
        total_entries=classification.get("total_entries", 0),
        analyzed_entries=classification.get("analyzed_entries", 0),
        counts=classification.get("counts", {}),
        dependencies_found=len(dependencies.get("dependencies", []) or []),
        error=outcome.get("error"),
    )


# ===================== GENERACION POR CHUNKS (Sprint 3.0 F2) =====================


class ChunkSummary(BaseModel):
    chunk_id: int
    name: str
    status: str  # pending | completed | failed | split
    entries: int
    is_skeleton: bool = False
    failure_reason: Optional[str] = None
    # F2.1 — linaje del auto-split.
    split_depth: int = 0
    parent_chunk_id: Optional[int] = None


class ChunkedGenerationResponse(BaseModel):
    """Contrato compartido por /generate-chunked y /retry-failed-chunks."""

    design_id: UUID
    mode: str  # chunked | single
    generation_status: Optional[str] = None  # completed | partial
    reason: Optional[str] = None
    total_chunks: int = 0
    chunks_completed: int = 0
    samplers_total: int = 0
    chunks: List[ChunkSummary] = Field(default_factory=list)
    error: Optional[str] = None


# ===================== ESTADO POLLABLE (Sprint 3.0 F3.1) =====================


class ChunkStatusItem(BaseModel):
    """Un bloque visto desde el endpoint de polling.

    Deliberadamente NO trae ``entry_idxs``: en un HAR de 106 requests esa lista
    multiplica el payload por nada, y la UI solo necesita el conteo.
    """

    chunk_id: int
    name: str
    status: str  # pending | completed | failed | split
    n_entries: int
    is_skeleton: bool = False
    split_depth: int = 0
    parent_chunk_id: Optional[int] = None
    failure_reason: Optional[str] = None  # truncado, ver _FAILURE_REASON_POLL_LIMIT


class HarBodyCoverage(BaseModel):
    """Cuantos requests del HAR traen el body de la respuesta (hallazgo F1)."""

    entries_with_response_body: int
    total_entries: int
    ratio: float  # 0.0 - 1.0; 0 si el HAR esta vacio


class GenerationStatusResponse(BaseModel):
    """Contrato de GET /designs/{id}/generation-status — lo consume F3.2.

    Barato a proposito: sin JMX, sin entry_idxs, sin conversacion. Pensado para
    un poll cada 3-5s mientras ``generation_status == 'in_progress'``.
    """

    design_id: UUID
    generation_mode: Optional[str] = None  # single | chunked | None (nunca generado)
    generation_status: Optional[str] = None  # in_progress | completed | partial | failed
    chunks_completed_count: int = 0
    # Semantica F2.1: los bloques 'split' NO cuentan (sus entries viven en los
    # hijos), asi que chunks_completed_count == total_chunks significa terminado.
    total_chunks: int = 0
    samplers_total: int = 0
    generation_started_at: Optional[str] = None  # ISO-8601 UTC del ultimo lanzamiento
    chunks: List[ChunkStatusItem] = Field(default_factory=list)
    har_body_coverage: Optional[HarBodyCoverage] = None  # None si no se pudo calcular


# El motivo de fallo completo puede traer el XML que el modelo corto a mitad.
# En un endpoint que se consulta cada 3s eso no viaja.
_FAILURE_REASON_POLL_LIMIT = 400


# Techo de salida por chunk. Un bloque de ~15 samplers completos entra holgado;
# se topa igual contra el maximo real del modelo dentro de _call_ai.
_CHUNK_MAX_TOKENS = 32768


def _chunk_summaries(plan: List[dict]) -> List[ChunkSummary]:
    return [
        ChunkSummary(
            chunk_id=c.get("chunk_id", 0),
            name=c.get("name", ""),
            status=c.get("status", CHUNK_PENDING),
            entries=len(c.get("entry_idxs") or []),
            is_skeleton=bool(c.get("is_skeleton")),
            failure_reason=c.get("failure_reason"),
            split_depth=int(c.get("split_depth") or 0),
            parent_chunk_id=c.get("parent_chunk_id"),
        )
        for c in plan
    ]


def _plan_copy(plan: List[dict]) -> List[dict]:
    """Copia superficial por chunk.

    SQLAlchemy detecta el cambio de una columna JSONB solo si se le ASIGNA un
    objeto nuevo; mutar la lista en su lugar no marca la fila como sucia y el
    plan no se persistiria.
    """
    return [dict(c) for c in plan]


async def process_pending_chunks(
    design: AIScriptDesign,
    db: AsyncSession,
    call_ai,
) -> dict:
    """Procesa los chunks pendientes en orden, uno por llamada al modelo.

    Contrato:

    - **Secuencial y no concurrente**: el chunk N puede necesitar variables que
      extrajo el chunk N-1.
    - **Persiste despues de CADA chunk exitoso**: si el proceso se cae en el
      chunk 5, los 4 anteriores ya estan en la base.
    - **Corta al primer fallo** y deja los siguientes en ``pending``, con el
      motivo en ``failure_reason`` del chunk que fallo. **Unica excepcion
      (F2.1):** si el fallo fue por truncacion del modelo, el chunk se parte en
      dos y las mitades se procesan en el mismo ciclo — ver ``_try_auto_split``.
    - **Nunca persiste un JMX invalido**: si el ensamblado no valida, el JMX
      previo queda intacto y el chunk se marca ``failed``.

    Devuelve ``{plan, generation_status, error}``.
    """
    classification = design.har_analysis_classification or {}
    dependencies = design.har_analysis_dependencies or {}
    plan = _plan_copy(design.chunks_plan or [])

    try:
        entries = extract_entries(design.reference_file_content)
    except HarAnalysisError as e:
        return {"plan": plan, "generation_status": GENERATION_PARTIAL, "error": str(e)}

    plan_name = design.name or "Plan de carga generado desde HAR"
    failure: Optional[str] = None

    # Indice explicito en vez de `for ... in plan`: un split inserta los hijos
    # dentro del plan mientras se lo recorre, y iterar una lista que crece por
    # el medio con un for es una fuente clasica de saltos silenciosos.
    i = 0
    while i < len(plan):
        chunk = plan[i]
        if chunk.get("status") in (CHUNK_COMPLETED, CHUNK_SPLIT):
            i += 1
            continue

        chunk_id = chunk.get("chunk_id", 0)
        total = _generable_chunks(plan)
        digests = digests_for_chunk(entries, chunk, classification)
        if not digests:
            chunk["status"] = CHUNK_COMPLETED
            chunk["failure_reason"] = None
            logger.info("chunked gen: chunk %d sin entries utiles, se omite", chunk_id)
            i += 1
            continue

        deps = get_dependencies_for_chunk(chunk, dependencies)
        is_skeleton = bool(chunk.get("is_skeleton"))

        if is_skeleton:
            messages = build_first_chunk_prompt(
                chunk, digests, deps, plan_name=plan_name, total_chunks=total
            )
        else:
            available = variables_available_from(plan, dependencies, chunk_id)
            messages = build_next_chunk_prompt(
                chunk, digests, deps, available, total_chunks=total
            )

        raw: Optional[str] = None
        new_jmx: Optional[str] = None
        failed_reason: Optional[str] = None

        try:
            # F3.1 — `call_ai` es SINCRONO (todo el modulo llama a `_call_ai`
            # directo). Invocarlo sin ceder el hilo bloquea el event loop entero
            # durante los ~40s que tarda cada bloque, y con la generacion movida
            # a background eso dejaria al backend sin atender NADA —incluido el
            # polling de /generation-status, que es justo lo que la UI necesita
            # mientras esto corre. El offload al threadpool es lo unico que hace
            # viable el modo de fondo. El contrato del callback no cambia: sigue
            # siendo un sync `messages -> str`, asi que los dobles de los tests
            # funcionan igual y `last_finish_reason` se lee despues del await.
            raw = await asyncio.to_thread(call_ai, messages)
        except Exception as e:  # noqa: BLE001 — el proveedor falla de mil formas
            logger.warning("chunked gen: chunk %d fallo la llamada a la IA — %s", chunk_id, e)
            failed_reason = f"Fallo la llamada a la IA: {e}"

        if failed_reason is None:
            if is_skeleton:
                jmx, _explanation = _extract_jmx_and_explanation(raw or "")
                # Mismo saneo de '&' sin escapar que reciben los fragmentos.
                jmx = sanitize_generated_jmx(jmx)
                ok, reason = validate_assembled_jmx(jmx)
                if ok:
                    new_jmx = jmx
                else:
                    failed_reason = _enrich_failure_reason(
                        f"El esqueleto generado no es un JMX valido: {reason}", call_ai
                    )
            else:
                ok, assembled, reason = assemble_chunk_into_jmx(
                    design.current_jmx, raw, chunk_id
                )
                if ok:
                    new_jmx = assembled
                else:
                    failed_reason = _enrich_failure_reason(reason, call_ai)

        if failed_reason is not None:
            # F2.1 — la truncacion es el unico fallo que NO corta el flujo.
            absorbido, failed_reason = _try_auto_split(
                plan, i, chunk, failed_reason, call_ai
            )
            if absorbido:
                design.chunks_plan = _plan_copy(plan)
                design.chunks_completed_count = _completed_chunks(plan)
                await db.commit()
                # Sin i += 1: la guarda de arriba salta al padre (ahora
                # 'split') y aterriza en el primer hijo.
                continue

            chunk["status"] = CHUNK_FAILED
            chunk["failure_reason"] = failed_reason
            failure = failed_reason
            break

        design.current_jmx = new_jmx
        chunk["status"] = CHUNK_COMPLETED
        chunk["failure_reason"] = None

        # Persistencia incremental: lo ganado hasta aca ya no se pierde.
        design.chunks_plan = _plan_copy(plan)
        design.chunks_completed_count = _completed_chunks(plan)
        await db.commit()
        logger.info(
            "chunked gen: chunk %d OK (%d/%d bloques) — %d samplers acumulados",
            chunk_id, _completed_chunks(plan), _generable_chunks(plan),
            count_samplers(design.current_jmx),
        )
        i += 1

    generation_status = GENERATION_PARTIAL if failure else GENERATION_COMPLETED
    design.chunks_plan = _plan_copy(plan)
    design.chunks_completed_count = _completed_chunks(plan)
    design.generation_status = generation_status
    await db.commit()

    return {"plan": plan, "generation_status": generation_status, "error": failure}


async def _load_design_for_chunking(
    design_id: UUID, db: AsyncSession, current_user: User
) -> AIScriptDesign:
    """Carga + guardas de acceso comunes a los dos endpoints de chunking."""
    stmt = select(AIScriptDesign).where(AIScriptDesign.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Diseno AI no encontrado")
    if not _is_admin(current_user) and design.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este diseno")
    return design


async def _build_chunk_call_ai(db: AsyncSession):
    """Callback sincrono hacia el proveedor de IA, igual patron que F1."""
    ai_conf = await load_ai_config_from_db(db)
    if ai_conf.get("limit_reached"):
        raise HTTPException(
            status_code=429,
            detail=f"Limite {ai_conf['limit_reached']} de uso de IA alcanzado.",
        )
    if not ai_conf.get("api_key"):
        raise HTTPException(
            status_code=503,
            detail="No hay API key de IA configurada. Configurala en Administracion > Configuracion IA.",
        )

    def _call(messages: List[dict]) -> str:
        # F2.1 — limpiar ANTES de llamar. Si _call_ai levanta, el
        # finish_reason de la llamada anterior no puede quedar colgado y
        # hacer pasar un error de red por una truncacion.
        _call.last_finish_reason = None
        text, finish = _call_ai(messages, ai_conf, max_tokens_override=_CHUNK_MAX_TOKENS)
        # El contrato del callback sigue siendo messages -> str (asi el modulo
        # se testea con un doble trivial). El finish_reason se deja adjunto
        # para que un fallo de ensamblado pueda distinguir "el modelo se quedo
        # sin tokens" de "el modelo genero XML mal formado": los dos llegan
        # como un ParseError identico, pero se resuelven distinto.
        _call.last_finish_reason = finish
        return text

    _call.last_finish_reason = None
    return _call


def _completed_chunks(plan: List[dict]) -> int:
    return sum(1 for c in plan if c.get("status") == CHUNK_COMPLETED)


def _generable_chunks(plan: List[dict]) -> int:
    """Bloques que producen samplers.

    Los chunks con status ``split`` quedan en el plan solo como rastro de
    linaje: sus entries ya viven en los hijos, asi que contarlos duplicaria el
    total y haria ver como 'partial' una generacion completa.
    """
    return sum(1 for c in plan if c.get("status") != CHUNK_SPLIT)


def _is_truncation_failure(reason: Optional[str], call_ai) -> bool:
    """True si el fallo fue porque el modelo se quedo sin tokens de salida.

    Dos fuentes, en ese orden: el ``finish_reason`` que dejo adjunto el
    callback, y el marcador que ``_enrich_failure_reason`` ya escribe en el
    texto (util cuando el motivo viaja desde un plan persistido).
    """
    if getattr(call_ai, "last_finish_reason", None) == "length":
        return True
    return bool(reason) and "finish_reason=length" in reason


def _try_auto_split(
    plan: List[dict], position: int, chunk: dict, failed_reason: str, call_ai
) -> tuple[bool, str]:
    """Sprint 3.0 F2.1 — parte en dos un chunk que trunco y sigue.

    Reintentar un bloque truncado tal cual es matematicamente inutil: el
    modelo va a volver a quedarse sin tokens sobre la misma entrada. Partirlo
    es lo unico que cambia el resultado.

    Muta ``plan`` en su lugar: marca al padre como ``split`` e inserta los dos
    hijos JUSTO DESPUES de el, para que el orden del HAR —y por lo tanto el
    orden de los samplers en el JMX— no se altere.

    Returns:
        ``(absorbido, motivo)``. Si ``absorbido`` es True el caller sigue el
        ciclo; si es False hay que cortar y ``motivo`` es el texto —quiza
        ampliado con el limite de split— que va al ``failure_reason``.
        El motivo se DEVUELVE en vez de escribirse aca: el caller lo asigna
        despues, y escribirlo en los dos lados hacia que el suyo lo pisara.
    """
    if not _is_truncation_failure(failed_reason, call_ai):
        return False, failed_reason

    children = split_chunk(chunk, next_free_chunk_id(plan))
    if children is None:
        # Trunco, pero ya no se puede partir mas: el motivo del limite se suma
        # al del fallo para que quede claro por que no se reintenta.
        _ok, why = can_split_chunk(chunk)
        logger.warning(
            "chunked gen: chunk %s trunco y no es divisible — %s",
            chunk.get("chunk_id"), why,
        )
        return False, f"{failed_reason} {why}"

    child_a, child_b = children
    chunk["status"] = CHUNK_SPLIT
    chunk["failure_reason"] = (
        f"{failed_reason} Se partio automaticamente en los bloques "
        f"C{child_a['chunk_id']} ({len(child_a['entry_idxs'])} requests) y "
        f"C{child_b['chunk_id']} ({len(child_b['entry_idxs'])} requests)."
    )
    plan[position + 1 : position + 1] = [child_a, child_b]

    logger.info(
        "chunked gen: chunk %s trunco -> auto-split en C%s (%d) + C%s (%d), nivel %s",
        chunk.get("chunk_id"),
        child_a["chunk_id"], len(child_a["entry_idxs"]),
        child_b["chunk_id"], len(child_b["entry_idxs"]),
        child_a["split_depth"],
    )
    return True, chunk["failure_reason"]


def _enrich_failure_reason(reason: str, call_ai) -> str:
    """Agrega la causa real cuando el fragmento se corto por limite de tokens."""
    if getattr(call_ai, "last_finish_reason", None) != "length":
        return reason
    return (
        f"{reason}. Causa: el modelo agoto su limite de tokens de salida y "
        f"corto el XML a mitad (finish_reason=length). Reintentar tal cual "
        f"probablemente falle igual: conviene un bloque mas chico o un modelo "
        f"con mayor capacidad de salida."
    )


# ---------------------------------------------------------------------------
# F3.1 — ejecucion en background
# ---------------------------------------------------------------------------

# asyncio guarda solo una referencia DEBIL a las tasks: sin este set, una
# generacion de 400s puede ser recolectada a mitad de camino y desaparecer sin
# dejar rastro (el diseno quedaria in_progress hasta que lo rescate el
# `finally`). Mantener la referencia fuerte es lo que hace que la tarea viva.
_CHUNK_TASKS: set = set()


def _stamp_run_start(plan: List[dict]) -> str:
    """Marca el inicio del run en el plan y devuelve el timestamp ISO.

    ``chunks_plan`` es un ARRAY JSON, no un objeto: no hay donde colgar un
    bloque de metadatos sin cambiarle la forma y romper a los consumidores de
    F2 (``_generable_chunks``, ``_chunk_summaries``, el ciclo de
    ``process_pending_chunks``) y a las filas ya persistidas. Por eso el sello
    va como una clave mas de cada chunk, repetida: cuesta ~30 bytes por bloque
    y evita una migracion. Se pisa en cada lanzamiento — es diagnostico, no
    historial.
    """
    started = datetime.utcnow().isoformat() + "Z"
    for chunk in plan:
        chunk["run_started_at"] = started
    return started


def _run_started_at(plan: List[dict]) -> Optional[str]:
    """Sello de inicio del plan. Los hijos de un split nacen sin el."""
    for chunk in plan:
        value = chunk.get("run_started_at")
        if value:
            return str(value)
    return None


async def _ensure_terminal_generation_status(
    design_id: UUID,
    error: Optional[str],
    session_factory=AsyncSessionLocal,
) -> None:
    """Red de seguridad: ningun diseno se queda en ``in_progress`` colgado.

    Corre en el ``finally`` de la tarea de fondo y SIEMPRE con una sesion nueva:
    si la tarea murio por una excepcion, la sesion que traia puede estar en una
    transaccion abortada y cualquier commit sobre ella fallaria tambien.

    No pisa un estado ya terminal — el camino feliz lo escribe
    ``process_pending_chunks`` y este metodo no tiene nada que corregir.
    """
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(AIScriptDesign).where(AIScriptDesign.id == design_id)
            )
            design = result.scalar_one_or_none()
            if design is None or design.generation_status != GENERATION_IN_PROGRESS:
                return

            plan = _plan_copy(design.chunks_plan or [])
            if error:
                # El motivo se deja en el primer bloque no terminado: es el que
                # estaba en curso cuando todo se cayo.
                for chunk in plan:
                    if chunk.get("status") not in (CHUNK_COMPLETED, CHUNK_SPLIT):
                        chunk["status"] = CHUNK_FAILED
                        chunk["failure_reason"] = f"La tarea de fondo aborto: {error}"
                        break

            completed = _completed_chunks(plan)
            design.chunks_plan = _plan_copy(plan)
            design.chunks_completed_count = completed
            # Con algo generado el trabajo es recuperable por /retry-failed-chunks;
            # sin nada generado no hay parcial que reanudar.
            design.generation_status = (
                GENERATION_PARTIAL if completed else GENERATION_FAILED
            )
            await db.commit()
            logger.error(
                "chunked gen: diseno %s rescatado de in_progress -> %s (%d bloques ok)",
                design_id, design.generation_status, completed,
            )
    except Exception:  # noqa: BLE001 — la red de seguridad no puede levantar
        logger.exception(
            "chunked gen: fallo el rescate de estado terminal del diseno %s", design_id
        )


async def _run_chunked_generation_background(
    design_id: UUID,
    session_factory=AsyncSessionLocal,
) -> None:
    """Tarea de fondo que corre la generacion por bloques completa.

    Abre **su propia sesion de DB**: la de la request se cierra en el teardown
    del ``Depends(get_db)`` en cuanto el endpoint responde, y esta tarea vive
    varios minutos despues de eso. Por lo mismo recarga el diseno por id en vez
    de recibir el objeto ORM del endpoint, que ya estaria desligado.

    La logica de negocio NO se duplica: reusa ``process_pending_chunks`` tal
    cual. Lo unico que agrega es el ciclo de vida.

    ``session_factory`` esta parametrizado para que los tests inyecten un doble
    y puedan ejercitar esta funcion en sincronico, sin base de datos.
    """
    error: Optional[str] = None
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(AIScriptDesign).where(AIScriptDesign.id == design_id)
            )
            design = result.scalar_one_or_none()
            if design is None:
                logger.error(
                    "chunked gen bg: el diseno %s ya no existe; se aborta", design_id
                )
                return

            call_ai = await _build_chunk_call_ai(db)
            outcome = await process_pending_chunks(design, db, call_ai)
            logger.info(
                "chunked gen bg: diseno %s termino con status=%s (%d/%d bloques, %d samplers)",
                design_id,
                outcome["generation_status"],
                _completed_chunks(outcome["plan"]),
                _generable_chunks(outcome["plan"]),
                count_samplers(design.current_jmx),
            )
    except Exception as e:  # noqa: BLE001 — nada puede escaparse de una task suelta
        error = str(e)
        logger.exception("chunked gen bg: diseno %s aborto por excepcion", design_id)
    finally:
        # Se ejecuta SIEMPRE, incluso en el camino feliz (donde no encuentra
        # nada que corregir y sale de inmediato).
        await _ensure_terminal_generation_status(design_id, error, session_factory)


def _launch_chunked_generation(design_id: UUID) -> None:
    """Dispara la tarea de fondo y vuelve en el acto.

    Se eligio ``asyncio.create_task`` sobre ``BackgroundTasks`` de FastAPI por
    dos razones concretas de este repo:

    1. Es el patron que el modulo ya usa para lo mismo (``/designs/{id}/execute``
       -> ``_run_full_execution_background``). Una segunda mecanica para el
       mismo problema seria deuda gratis.
    2. ``BackgroundTasks`` corre DENTRO del ciclo de vida de la request: se
       ejecuta despues de emitir la respuesta pero antes de cerrar las
       dependencias, con lo cual la sesion del ``Depends(get_db)`` seguiria
       viva y atada a una request de 400s. La task suelta corta ese vinculo por
       completo, que es lo que un trabajo de varios minutos necesita.

    Seam de test: los tests reemplazan esta funcion y evitan crear tasks reales.
    """
    task = asyncio.create_task(_run_chunked_generation_background(design_id))
    _CHUNK_TASKS.add(task)
    task.add_done_callback(_CHUNK_TASKS.discard)


def _in_progress_response(design: AIScriptDesign) -> ChunkedGenerationResponse:
    """Rechazo del guard anti-concurrencia.

    200 con el estado actual, NO 409: F2 fijo que los errores de negocio de este
    flujo viajan en el cuerpo (``mode='single'``, ``generation_status='partial'``)
    y solo acceso y configuracion usan codigos HTTP. Un 409 aca obligaria a la UI
    a tener dos caminos de lectura para la misma informacion.
    """
    plan = design.chunks_plan or []
    return ChunkedGenerationResponse(
        design_id=design.id,
        mode=design.generation_mode or MODE_CHUNKED,
        generation_status=GENERATION_IN_PROGRESS,
        reason=(
            "Ya hay una generacion por bloques en curso para este diseno. "
            "Segui su avance en GET /designs/{id}/generation-status; no se "
            "lanzo una segunda."
        ),
        total_chunks=_generable_chunks(plan),
        chunks_completed=_completed_chunks(plan),
        samplers_total=count_samplers(design.current_jmx),
        chunks=_chunk_summaries(plan),
    )


@router.post("/designs/{design_id}/generate-chunked", response_model=ChunkedGenerationResponse)
async def generate_jmx_chunked(
    design_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Genera el JMX de un HAR grande en bloques (Sprint 3.0 — Fundacion 2).

    Requiere que ``/analyze-har`` haya corrido con exito: el plan de chunks se
    arma sobre la clasificacion y las dependencias que dejo la Fundacion 1.

    Contrato de codigos, alineado con ``/analyze-har``:

    - **404 / 403** acceso; **429 / 503** configuracion de IA.
    - **400** precondicion estructural: sin analisis completado no hay nada que
      partir (equivalente al 400 de analyze-har ante un archivo no-HAR).
    - **200 con ``mode='single'``** cuando el HAR no llega al umbral: no es un
      error, es la respuesta correcta — el flujo normal lo cubre.
    - **200 con ``generation_status='partial'``** cuando un bloque falla. Los
      bloques ya generados quedan persistidos y ``/retry-failed-chunks``
      reanuda desde ahi.

    **F3.1 — este endpoint ya NO espera a que la generacion termine.** Valida,
    persiste el plan, lanza la tarea de fondo y responde en el acto con
    ``generation_status='in_progress'``. El avance se sigue por
    ``GET /designs/{id}/generation-status``. El motivo es medido, no teorico:
    una corrida real sobre un HAR de 106 requests tarda 327-412s, muy por
    encima de lo que cualquier browser o proxy mantiene abierto.
    """
    design = await _load_design_for_chunking(design_id, db, current_user)

    # Guard anti-concurrencia ANTES de cualquier otra validacion: si ya hay una
    # corrida en curso, nada de lo que siga tiene sentido evaluarlo — el plan
    # que leeriamos lo esta mutando la tarea de fondo en este mismo instante.
    if design.generation_status == GENERATION_IN_PROGRESS:
        return _in_progress_response(design)

    if design.har_analysis_status != STATUS_COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=(
                "El diseno no tiene un analisis de HAR completado "
                f"(status actual: '{design.har_analysis_status or 'ninguno'}'). "
                "Corre POST /designs/{id}/analyze-har primero."
            ),
        )

    use_chunks, reason = should_use_chunked_generation(design.har_analysis_classification)
    if not use_chunks:
        # No es un error: el flujo clasico de 1 llamada es la via correcta.
        design.generation_mode = MODE_SINGLE
        await db.commit()
        return ChunkedGenerationResponse(
            design_id=design.id, mode=MODE_SINGLE, reason=reason
        )

    plan = group_entries_into_chunks(
        design.har_analysis_classification, design.har_analysis_dependencies
    )
    if not plan:
        raise HTTPException(
            status_code=400,
            detail="La clasificacion del HAR no produjo ningun bloque generable.",
        )

    # Pre-vuelo de la configuracion de IA. Se hace ACA, con la sesion de la
    # request, para que un 429/503 le llegue al usuario como codigo HTTP en vez
    # de morir sin testigos dentro de la tarea de fondo. La tarea vuelve a
    # construir su propio callback con su propia sesion.
    await _build_chunk_call_ai(db)

    design.generation_mode = MODE_CHUNKED
    design.chunks_plan = _plan_copy(plan)
    started_at = _stamp_run_start(design.chunks_plan)
    design.chunks_completed_count = 0
    design.generation_status = GENERATION_IN_PROGRESS
    await db.commit()

    # El commit va ANTES del lanzamiento: la tarea de fondo lee el diseno de la
    # base en su propia sesion, y si arrancara antes del commit no encontraria
    # el plan.
    _launch_chunked_generation(design.id)
    logger.info(
        "chunked gen: diseno %s lanzado en background — %d bloques, inicio %s",
        design_id, _generable_chunks(plan), started_at,
    )

    return ChunkedGenerationResponse(
        design_id=design.id,
        mode=MODE_CHUNKED,
        generation_status=GENERATION_IN_PROGRESS,
        reason=(
            f"{reason} Generacion lanzada en segundo plano; segui el avance en "
            f"GET /designs/{{id}}/generation-status."
        ),
        total_chunks=_generable_chunks(plan),
        chunks_completed=0,
        samplers_total=count_samplers(design.current_jmx),
        chunks=_chunk_summaries(plan),
    )


@router.post("/designs/{design_id}/retry-failed-chunks", response_model=ChunkedGenerationResponse)
async def retry_failed_chunks(
    design_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Reanuda una generacion por chunks que quedo ``partial``.

    Pasa los chunks ``failed`` de vuelta a ``pending``, **recalcula
    ``chunks_completed_count`` desde el plan** (no confia en el contador
    guardado) y reanuda desde el primer pendiente. Los chunks ya completados
    no se re-generan ni se re-cobran.

    **F3.1 — igual que ``/generate-chunked``, responde de inmediato** con
    ``generation_status='in_progress'`` y deja el trabajo a la tarea de fondo.
    """
    design = await _load_design_for_chunking(design_id, db, current_user)

    if design.generation_status == GENERATION_IN_PROGRESS:
        return _in_progress_response(design)

    if design.generation_mode != MODE_CHUNKED or not design.chunks_plan:
        raise HTTPException(
            status_code=400,
            detail=(
                "El diseno no tiene una generacion por chunks en curso. "
                "Corre POST /designs/{id}/generate-chunked primero."
            ),
        )

    plan = _plan_copy(design.chunks_plan)
    reset = 0
    for chunk in plan:
        if chunk.get("status") == CHUNK_FAILED:
            chunk["status"] = CHUNK_PENDING
            chunk["failure_reason"] = None
            reset += 1

    # Los chunks con status 'split' (F2.1) no son pendientes: sus entries ya
    # viven en los hijos. Contarlos dejaria el retry en un bucle sin trabajo.
    pending = sum(
        1 for c in plan if c.get("status") not in (CHUNK_COMPLETED, CHUNK_SPLIT)
    )
    completed = _completed_chunks(plan)

    # Recalculo explicito: el contador se deriva del plan, nunca al reves.
    design.chunks_plan = _plan_copy(plan)
    design.chunks_completed_count = completed
    await db.commit()

    if not pending:
        return ChunkedGenerationResponse(
            design_id=design.id,
            mode=MODE_CHUNKED,
            generation_status=design.generation_status or GENERATION_COMPLETED,
            reason="No hay bloques pendientes ni fallidos; nada que reintentar.",
            total_chunks=_generable_chunks(plan),
            chunks_completed=completed,
            samplers_total=count_samplers(design.current_jmx),
            chunks=_chunk_summaries(plan),
        )

    # Mismo pre-vuelo que /generate-chunked: 429/503 en la request, no en la task.
    await _build_chunk_call_ai(db)

    design.chunks_plan = _plan_copy(plan)
    started_at = _stamp_run_start(design.chunks_plan)
    design.generation_status = GENERATION_IN_PROGRESS
    await db.commit()

    _launch_chunked_generation(design.id)
    logger.info(
        "retry chunks: diseno %s lanzado en background — %d failed->pending, "
        "%d pendientes en total, inicio %s",
        design_id, reset, pending, started_at,
    )

    return ChunkedGenerationResponse(
        design_id=design.id,
        mode=MODE_CHUNKED,
        generation_status=GENERATION_IN_PROGRESS,
        reason=(
            f"{reset} bloque(s) fallido(s) reintentado(s). Reanudacion lanzada "
            f"en segundo plano; segui el avance en "
            f"GET /designs/{{id}}/generation-status."
        ),
        total_chunks=_generable_chunks(plan),
        chunks_completed=completed,
        samplers_total=count_samplers(design.current_jmx),
        chunks=_chunk_summaries(plan),
    )


def _body_coverage_for(design: AIScriptDesign) -> Optional[HarBodyCoverage]:
    """Cobertura de response bodies del HAR, con fallback on-demand.

    Preferencia 1: la clave que ``/analyze-har`` deja dentro de
    ``har_analysis_classification`` (F3.1). Preferencia 2 —para los disenos ya
    analizados ANTES de F3.1, que no la tienen— recalcularla leyendo el HAR
    persistido: es puro parseo de JSON, **no re-corre la IA** ni escribe nada.

    Devuelve ``None`` (nunca levanta) si el diseno no tiene HAR o el HAR es
    ilegible: este endpoint se consulta cada 3s y un aviso ausente no puede
    tumbar el polling del progreso.
    """
    blob = design.har_analysis_classification
    raw = blob.get("response_body_coverage") if isinstance(blob, dict) else None

    if not isinstance(raw, dict) or "entries_with_response_body" not in raw:
        try:
            raw = response_body_coverage(extract_entries(design.reference_file_content))
        except Exception:  # noqa: BLE001 — HarAnalysisError incluido; dato opcional
            return None

    try:
        total = int(raw.get("total_entries") or 0)
        with_body = int(raw.get("entries_with_response_body") or 0)
    except (TypeError, ValueError):
        return None

    return HarBodyCoverage(
        entries_with_response_body=with_body,
        total_entries=total,
        ratio=round(with_body / total, 4) if total else 0.0,
    )


@router.get(
    "/designs/{design_id}/generation-status",
    response_model=GenerationStatusResponse,
)
async def get_generation_status(
    design_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Estado de la generacion por bloques (Sprint 3.0 — F3.1).

    Endpoint de **polling**: pensado para que la UI lo consulte cada 3-5s
    mientras ``generation_status == 'in_progress'``. Por eso NO devuelve el
    JMX, ni los ``entry_idxs`` de cada bloque, ni la conversacion: solo lo que
    hace falta para dibujar una barra de progreso y una lista de bloques.

    Codigos: **404/403** de acceso, igual que el resto del modulo. Un diseno que
    nunca paso por ``/generate-chunked`` NO es un error — responde 200 con los
    campos en ``None`` y ``total_chunks=0``, que es lo que la UI necesita para
    decidir que no muestra el panel.

    Estados posibles de ``generation_status``:

    - ``None``     — nunca se genero por bloques.
    - ``in_progress`` — hay una tarea de fondo corriendo (unico NO terminal).
    - ``completed``   — todos los bloques generables terminaron OK.
    - ``partial``     — al menos un bloque quedo failed/pending; recuperable con
      ``/retry-failed-chunks``.
    - ``failed``      — la corrida aborto sin ningun bloque completado.
    """
    design = await _load_design_for_chunking(design_id, db, current_user)
    plan = design.chunks_plan or []

    chunks = [
        ChunkStatusItem(
            chunk_id=c.get("chunk_id", 0),
            name=c.get("name", ""),
            status=c.get("status", CHUNK_PENDING),
            n_entries=len(c.get("entry_idxs") or []),
            is_skeleton=bool(c.get("is_skeleton")),
            split_depth=int(c.get("split_depth") or 0),
            parent_chunk_id=c.get("parent_chunk_id"),
            failure_reason=_truncate(
                c["failure_reason"], _FAILURE_REASON_POLL_LIMIT
            ) if c.get("failure_reason") else None,
        )
        for c in plan
    ]

    return GenerationStatusResponse(
        design_id=design.id,
        generation_mode=design.generation_mode,
        generation_status=design.generation_status,
        # Se cuenta desde el plan en vez de leer la columna: F2 ya fijo que el
        # contador se deriva del plan y nunca al reves.
        chunks_completed_count=_completed_chunks(plan),
        total_chunks=_generable_chunks(plan),
        samplers_total=count_samplers(design.current_jmx),
        generation_started_at=_run_started_at(plan),
        chunks=chunks,
        har_body_coverage=_body_coverage_for(design),
    )


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
