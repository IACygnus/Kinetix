6052cfe · 2026-09-16

# ETAPA 2 — CIERRE

**Llamadas reales a la IA en toda la etapa: 30 / 50** — 1 de `POST /ai-config/test` (2.2),
28 de la corrida de validacion y 1 del consolidado de su informe integrado (reporte 28).
Rama `backup-trabajo-local`, todo empujado a `github`.

Este reporte sustituye al 19 como punto de entrada: para retomar, basta este más la
especificación `docs/ESPECIFICACION-informe.md`.

---

## 1. Qué se entregó

| Dec. | Qué pedía | Estado | Dónde quedó |
|---|---|---|---|
| **D13 / D14** | `reasoning_effort` configurable | **Hecha** (2.2) | modelo, schema, endpoint, `gemini.py`, `AIConfigPage.tsx` |
| **D15** | Las 5 gráficas por transacción **y la tabla resumen filtrada** en cada bloque | Gráficas: ya existían. **Tabla resumen filtrada: hecha** (`5323705` + `c957047`, reporte 27) | `transaction_series.py`, `SummaryTable.tsx` |
| **D16** | El título es el nombre de la transacción y nada más | **Hecha** en las 4 salidas | 2.6b, 2.7b, 2.8b |
| **D17** | General → transacciones → conclusiones al final | **Hecha** en las 4 salidas | 2.6f, 2.7b, 2.8b, heredada en el integrado |
| **D18** | Active Threads solo en el general | **Hecha** | `ReportBody.tsx`, `GENERAL_ONLY_CHARTS`, `HTML_GENERAL_ONLY` |
| **D19** | Throughput Over Time fuera del producto | **Hecha** en backend, IA, pantalla, PDF, HTML, integrado y `chartConfig.ts` | 2.3, 2.6b, 2.7b, 2.8b, 2.9, 2.9b |
| **D20** | 6 secciones por transacción, no 8 | **Hecha** | 2.4 + filtro por `SECTIONS_GENERADAS` en las tres salidas |
| **D21** | Un solo render por alcance, no plantillas paralelas | **Hecha** | `ReportBody` (pantalla), `report_body_html` (PDF), `_bloque_grafica_html` (HTML) |
| **D22** | La palabra «mini-informe» no se ve | **Hecha**, incluidos los comentarios que viajan dentro del HTML entregado | identificadores (`txreport_*`) conservados |
| **D23** | Overrides de secciones retiradas: ignorar, no borrar | **Hecha** en el prompt del consolidado (2.5) y al renderizar (2.9) | ninguna fila borrada |
| **D24** | Página nueva por transacción en el PDF | Ya estaba, **verificada** | 2.7b |
| **D25** | No se tocan los textos de los prompts | Respetada; una excepción razonada | reporte 17 §3 |
| **D26** | Retrocompatibilidad probada contra datos reales | Aplicada en cada sub-paso | — |

### Además, sin estar pedido pero necesario

- La carga de los bloques por transacción pasó a ser **en serie** y el parseo del JTL salió
  del event loop (`asyncio.to_thread`): el peor latido de `/auth/me` durante la carga bajó
  de **200 ms a 6-11 ms** (reporte 20 §3).
- Dos defectos de cuenta que quedaban de D20: «8 de 6 secciones» y la barra «Generando N de 8».

---

## 2. Lo que cuesta y lo que ahorra

Medido en una corrida real, `E2-validacion`, con el mismo JTL y los mismos parámetros que la
línea base (reporte 28):

| | Línea base (Etapa 1) | **E2-validacion** | |
|---|---|---|---|
| Llamadas de IA por informe (3 transacciones) | 35 | **28** | −20 % |
| T1 − T0 (bloque general) | 112-119 s | **55,9 s** | −50 % |
| **T2 − T0 (lo que espera el usuario)** | 354-357 s | **141,0 s** | **−61 %** |
| Latencia media por llamada | 10,0-10,2 s | **4,9 s** | −52 % |
| Razonamiento por llamada | 569 tokens | **113 tokens** | −80 % |
| Texto visible por llamada | 244 tokens | **226 tokens** | −7 % |
| Peor latido de `/auth/me` durante la generación | 21 ms / 54.922 ms | **10,7 ms** | |
| Peso del HTML exportado | 513.405 bytes | **497.252 bytes** | |

**De casi 6 minutos a 2 minutos y 21 segundos.** La mitad del recorte lo puso esta etapa
(menos llamadas) y la otra mitad `reasoning_effort=low`, de 2.2.

El **texto visible solo baja un 7 %**: el informe no se queda corto. Si se ha quedado más
pobre es un juicio de lectura, y está en el guion de pruebas.

---

## 3. Archivos protegidos — lo que costaron (C3, cambios reales)

| Archivo | Cambios reales | Estimación revisada (reporte 18) |
|---|---|---|
| `Dashboard.tsx` | 300 (2.6a, en su mayoría movidos) + 11 (2.6f) + 6 (2.9b) + 40 (2.13, de los que 40 de 64 eliminadas son la tabla movida a `SummaryTable.tsx`) | ~120-160, revisada al alza tras la parada del reporte 18 |
| `report_generator.py` | **188** | 240-320 |
| `export_html.py` | **177** | 190-260 |
| `export_pdf.py` | **19** | 50-65 |

Los otros protegidos (`jtl_parser.py`, `virtual_user.py`, `services/engine/`,
`ScriptDesigner.tsx`) **no se tocaron**, como se declaró en el reporte 13 §7.

Cada refactor de los protegidos se hizo en dos pasos (C1) con su equivalencia demostrada:
pantalla 0,000 % de píxeles, PDF `diff` vacío, HTML idéntico salvo un comentario que cambia
de sitio.

---

## 4. Verificación

`verificar_etapa2.py` — **diez pasos**, más de sesenta comprobaciones sobre datos reales; las
**cuatro salidas pasan**, tanto sobre `ff186cc7` (reporte 24) como sobre la ejecución nueva
`E2-validacion` (reporte 28 §6). Se vuelve a correr con un comando.

Los **tres canales de texto** están probados con Playwright sobre la pantalla real:

| Canal | Dónde guarda | Prueba |
|---|---|---|
| Informe general | columnas `ai_analysis_*` de `test_executions` | `cableado_c2.py` |
| Informe por transacción | `transaction_chart_analyses` | `cableado_c2.py` |
| Informe integrado | `integrated_reports.sections[].overrides.analysis` (JSONB) | `cableado_c2_integrado.py` |

En los tres casos se comprueba también que **la edición no toca a los otros dos**, y que al
recargar la página el texto sigue ahí.

---

## 5. Pendiente — NO es de esta etapa

| Qué | Dónde está escrito |
|---|---|
| **Panel de selección**: columnas Transacción · Muestras · Promedio · TPS · Errores, y criterios por fila dentro de la tabla | v1.2 §2 |
| **Control de capas** avg/max y tooltip de una sola capa | v1.2 §3 |
| **Estilo de los textos de IA** (§4): ningún prompt se tocó, porque D25 lo prohíbe en esta etapa | v1.2 §4 |
| **Selector «qué incluir»** al exportar PDF/HTML | v1.2 §6 |
| Lo que queda del tiempo: `SYSTEM_PROMPT` duplicado (la caché vuelve al 7,8 %), secuencialidad de las 28 llamadas | reportes 10 y 28, Etapa 4 |

---

## 6. Antes de desplegar

1. **Ejecutar `docs/sql/etapa2_reasoning_effort.sql`** en la base del servidor. Es idempotente
   (`ADD COLUMN IF NOT EXISTS`). **No es opcional:** `create_all` no altera tablas existentes,
   y sin esa columna la primera lectura de `ai_config` revienta, el error se degrada a
   *warning* y **todos los informes salen con texto de `FallbackAnalyzer` sin aviso ninguno**.
   Comprobación posterior: `GET /ai-config` responde 200 y trae `reasoning_effort`.
2. Rebuild de los contenedores, que lo controla Fredy (regla 7).
3. Dejar `reasoning_effort` en el valor que Fredy decida tras leer los análisis: la etapa
   queda en **`low`**, que es con lo que se midieron los 141 s.

---

## 7. Lo que falta de verdad para dar la etapa por buena

**La validación visual de Fredy** (regla 9), sobre las cuatro salidas:

- **Pantalla**: que cada bloque por transacción se lea como el informe general y que las
  conclusiones queden al final.
- **PDF**: que cada transacción abra página y que el bloque se lea como el general.
- **HTML**: lo mismo, y que las gráficas por transacción respondan a sus controles.
- **Integrado**: que no aparezcan conclusiones repetidas ni bloques vacíos.

Nada de lo anterior sustituye eso. Compilación verde y 40 comprobaciones en verde no son
una feature funcional.
