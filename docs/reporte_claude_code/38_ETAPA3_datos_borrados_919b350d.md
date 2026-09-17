fba3e98 · 2026-09-16

# ETAPA 3 — Los datos borrados en `919b350d`: qué eran y qué se pudo recuperar

**Llamadas reales a la IA: 0.** Todo el trabajo de recuperación fue de solo
lectura sobre la base. La única escritura fue instalar y desinstalar la
extensión `pageinspect` (§3.4), que se dejó como estaba.

Este reporte responde al reporte 32 §6.

---

## 1. Qué ejecución es

| Campo | Valor |
|---|---|
| Id | `919b350d-61f5-4c74-bd51-bf812f48f7e0` |
| Nombre | **prueba final 2** |
| Cliente | **popular** (`dec0459a-1e19-4996-812c-f23689113a51`) |
| Proyecto | prueba final 2 |
| Tipo | estrés |
| Fecha de la prueba | 2021-03-19 18:10 |
| Cargada en Kinetix | 2026-04-01 14:35 |
| Muestras | 251.299 |
| JTL | `resultados_general 19-mar-2021-181050.jtl` |

No es una ejecución de las etapas 1, 2 o 3: es un informe de Fredy de abril.

## 2. Qué se perdió exactamente y qué no

Lo que escribió y borró la prueba con stubs fueron **dos claves** de
`capacity_analysis_json`: `monitoring_ai_analysis` y `evidence_ai_analysis`, o
sea los **análisis globales** de Monitoreo y de Evidencias.

**Lo que NO se tocó, y está verificado:**

| Qué | Estado |
|---|---|
| Los **7 análisis por imagen** (5 de monitoreo, 2 de evidencias) | **Intactos**, con su `ai_analysis_updated_at` original del 2026-04-02 |
| Las 7 imágenes adjuntas | Intactas |
| Los análisis del informe (`ai_analysis_*`, conclusiones, recomendaciones) | Intactos |
| El informe integrado `d863ef7b` que usa esta ejecución | Intacto, con su consolidado editado a mano por Fredy |
| Cualquier otra ejecución | Ninguna se vio afectada |

### ¿Eran generados por IA o editados a mano?

**No se puede saber.** `capacity_analysis_json` es un `TEXT` con un JSON suelto:
no tiene marca `is_edited` ni `updated_at` propios, a diferencia de los análisis
por imagen (`execution_attachments.ai_analysis_updated_at`) y de las secciones
por transacción (`transaction_chart_analyses.is_edited`). Los dos análisis
globales son las **únicas** salidas de IA del producto sin marca de edición.

---

## 3. El intento de recuperación

Cinco frentes, todos de solo lectura.

### 3.1 Copias en `integrated_reports`

La ejecución aparece en dos informes integrados
(`d863ef7b-…` y `2893fd5d-…`). En ninguno de los dos hay copia:

- **`sections[].overrides`**: no existe la clave. Ninguna de las dos secciones
  de monitoreo o evidencias fue editada desde el integrado.
- **`consolidated_analysis`** de `d863ef7b`: existe y está **editado a mano**
  (`"edited": true`), pero es una **síntesis**, no una copia. El texto global
  original entraba en su prompt marcado como `[Global]:` y salía refundido.
- Comprobado además que el HTML de la sección de monitoreo del integrado
  **nunca** incluye el análisis global: `_build_att_html` se llama con `""` en
  ese parámetro (`integrated_report.py:1537`). El global solo viajaba a las
  conclusiones unificadas, que **no se persisten**.

### 3.2 Exportados en disco

`/app/uploads` tiene 197 archivos y **ninguno** es PDF ni HTML: los exportados
se devuelven por HTTP, no se guardan. Y aunque se hubieran guardado no
serviría: ni `export_pdf.py` ni `export_html.py` leen
`monitoring_ai_analysis` — el análisis global **no sale en el informe
individual exportado**.

### 3.3 Resto de la base

Se buscó la cadena `monitoring_ai_analysis` en las 18 tablas. Aparece en
**cuatro** ejecuciones (`prueba m`, `prueba 5`, `prueba 23423`, `prueba 2000`) y
en ninguna otra parte. No hay tabla de auditoría, ni histórico, ni copia.

### 3.4 Forense sobre las páginas de PostgreSQL

Este era el único camino que quedaba. La base **no ha pasado nunca por
`VACUUM`** (`last_vacuum` y `last_autovacuum` vacíos en `test_executions` y en
su tabla TOAST), así que las versiones antiguas de las filas podían seguir en
las páginas. Se instaló `pageinspect`, se leyó y se desinstaló.

**Lo que se encontró en el heap:** de la fila de `919b350d` sobrevive **una
sola** versión muerta, en la página 14, creada por la transacción 1848 y
borrada por la 1850. Su contenido es **el texto del stub**:

```
{"monito\000ring_ai_\000analysis\000": "[STUB 	 ] 1.\000677 mues\000tras pro\000mediaron\000 108 ms. …
```

Es decir: sobrevive la versión que **yo** escribí, no la anterior. Las
versiones previas —incluida la original— fueron **podadas** (HOT pruning) al
tocarse la página. En las páginas del heap hay **3 punteros `LP_DEAD`**, que son
exactamente eso: versiones cuyo dato ya no está.

**Lo que se buscó en la tabla TOAST:** si la versión original hubiera tenido los
dos análisis completos (entre 1,3 y 2,6 KB comprimidos, como los de las cuatro
ejecuciones que sí los conservan), habría estado **fuera de línea**, en la tabla
TOAST, y al borrarse habría dejado allí sus fragmentos muertos. En las 89
páginas TOAST hay **un solo fragmento muerto**, y no es este: es de la
verificación de esta misma noche sobre `E3-estilo-pruebakinetix`
(`«El 90% del tiempo que espera una persona…»`). **Pero también hay 8 punteros
`LP_DEAD`**, ya podados.

**Conclusión honesta: los textos no se pueden recuperar, y la evidencia forense
no permite afirmar ni negar que existieran.** Los 8 punteros podados de la tabla
TOAST dejan la puerta abierta a que uno de ellos fuera el original. Lo único
que se puede decir con certeza es que **no queda ni un byte legible de ellos en
ninguna parte**.

### 3.5 Un indicio, que no es prueba

Los siete análisis por imagen que sobreviven contienen **todos** los detalles
que el consolidado de `d863ef7b` atribuye al monitoreo y a las evidencias: los
`0.1 vCores` del worker de Mule, el heap entre 200 y 250 MB, el conteo de
hilos, el error 500 de `Habeas Data` y la conexión cerrada contra
`172.28.67.161`. El consolidado se explica entero con esos siete textos más los
KPI de la ejecución: **no hay en él ningún dato que exija un análisis global
que ya no está**. Es un indicio de que quizá nunca existió, no una prueba.

---

## 4. Cómo quedó, verificado

Por `SELECT`:

```
capacity_analysis_json                                   | {}
análisis por imagen con texto                            | 7
```

Y en pantalla (Playwright, sobre `/performance/monitoring` y
`/performance/evidence`, seleccionando «prueba final 2»):

```
API monitoring-analysis  -> analisis='' avisos=[]
API evidence-analysis    -> analisis='' avisos=[]
API image-analyses (monitoring) -> 5 imagenes, 5 con analisis
API image-analyses (evidence)   -> 2 imagenes, 2 con analisis
pantalla /monitoring  -> caja de analisis global: 0 · boton para generarlo: 1 ·
                         analisis por imagen en pantalla: 5
pantalla /evidence    -> caja de analisis global: 0 · boton para generarlo: 1 ·
                         analisis por imagen en pantalla: 2
```

La ejecución está **exactamente como si nunca se hubiera generado el análisis
global**: sin caja, con el botón para generarlo y con sus siete análisis por
imagen a la vista. No hay texto falso ni residuo del stub en ninguna parte.

---

## 5. Cómo regenerarlos (2 llamadas)

1. Menú **Performance → Monitoreo**. Seleccionar **«prueba final 2 — popular»**.
   Bajar y pulsar **Generar Analisis Global**. *(1 llamada)*
2. Menú **Performance → Evidencias**. Misma ejecución. **Generar Analisis
   Global**. *(1 llamada)*

Saldrán con el estilo nuevo de la Etapa 3 —cifras en español, percentiles en
personas, sin jerga—, no con el de abril.

---

## 6. Lo que se cambió para que no se repita

Ya estaba hecho en `9c2bacb` y se deja anotado aquí: la prueba con stubs
**desactiva `commit` y hace `rollback`** mientras construye los prompts de
monitoreo, evidencias y consolidado. Verificado: la segunda pasada no dejó
rastro en base.

La causa de fondo, dicha claramente: **llamé a un endpoint que persiste para
construir un prompt**, en datos reales, sin comprobar antes si escribía. Es lo
que hay que mirar antes de invocar cualquier endpoint desde una prueba.
