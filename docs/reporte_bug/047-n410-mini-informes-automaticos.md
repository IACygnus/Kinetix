# 047 — N4.10: generacion automatica de los mini-informes al generar el reporte

**Fecha:** 2026-08-20
**Branch:** `backup-trabajo-local`
**Commit:** `302e484` — "N4.10: generacion automatica de mini-informes al generar el reporte"
**Cierra el sprint N4.**

**Archivos de codigo tocados:** 3
- `backend/app/api/v1/endpoints/upload.py`
- `backend/app/services/ai/transaction_report.py`
- `frontend/src/components/dashboard/TransactionReportSection.tsx`

**Backups:** `.bak_n410_20260820_084015` de los tres
**Llamadas de IA:** 0 — validado con stub (ver §5)
**Ciclo Docker:** `py_compile` + `tsc --noEmit` + `docker restart`, sin build

---

## 1. Lo que pidio Fredy desde el principio

Marcar transacciones en el panel, pulsar **Generar Reporte**, y al terminar tener
el informe general **mas** los mini-informes de las marcadas. Sin botones
adicionales. Modo automatico completo, decision del CTO.

---

## 2. El problema del timeout y como se resolvio

### 2.1 La aritmetica

El upload sincrono ya tarda ~2 min. Cada transaccion suma ~90 s. Con 3 marcadas
son ~7 min contra un timeout de axios de 600 s: no cabe, y aunque cupiera seria
una peticion HTTP abierta 7 minutos, que ningun proxy ni balanceador aguanta.

### 2.2 El precedente: F3.1

Se reviso `docs/reports/repo/sprint-3.0-f3.1-background-status.md` (Sprint 3.0,
generacion por chunks del Diseñador IA). **Encaja y se reusa entero**, incluidas
sus tres lecciones:

| Leccion de F3.1 | Como se aplica aqui |
|---|---|
| `asyncio.create_task`, no `BackgroundTasks` | `BackgroundTasks` corre dentro del ciclo de vida de la peticion: la sesion del `Depends(get_db)` seguiria viva atada a un trabajo de minutos. La task suelta corta ese vinculo y abre su propia sesion |
| Referencias **fuertes** a las tareas | `asyncio` solo guarda una referencia debil: sin un `set` de modulo, una generacion larga puede ser recolectada a mitad de camino y desaparecer. `_MINI_INFORME_TASKS` + `add_done_callback` |
| Desbloquear el event loop | ver 2.3 — **era obligatorio** |

### 2.3 La adaptacion obligatoria: `_generate` bloqueaba el loop

`analyzer._generate` es **sincrono**. Llamado tal cual desde una corrutina
bloquea el event loop entero. Con el POST manual eso ya pasaba pero era
invisible (la peticion estaba bloqueada de todas formas). En background es
letal: el backend no atenderia **nada** durante los ~90 s por transaccion,
incluido el sondeo del progreso, que es justo lo que la pantalla necesita.

Unica linea de `transaction_report.py` que se toco — la misma adaptacion que
hizo F3.1 con `_call_ai`:

```diff
-                texto = analyzer._generate(prompts[section], section_name=f"txreport_{section}")
+                texto = await asyncio.to_thread(
+                    analyzer._generate, prompts[section], section_name=f"txreport_{section}"
+                )
```

Medido con el stub (§5, caso B): durante los 5,1 s de trabajo el latido de
control dio **99 ticks**. Sin el `to_thread` habrian sido 0.

Efecto lateral bueno: el POST manual de N4.6 tambien deja de bloquear el
backend durante 90 s. Era un fallo latente.

### 2.4 El estado NO vive en memoria

En produccion el backend corre con `--workers 2`. Un diccionario de proceso lo
veria solo uno de los dos y el sondeo daria una respuesta distinta segun a quien
le tocara la peticion. **El estado se DERIVA de las filas de
`transaction_chart_analyses`** — misma razon por la que N4.6 cuenta el progreso
leyendo la base, y sin tocar el esquema (regla 10: no hay Alembic).

Funciona porque N4.6 escribe **siempre las 8 filas**, con `ai_analysis` en NULL
para la seccion que fallo. Eso deja cuatro estados legibles sin columna nueva:

| Filas | Estado | Significado |
|---|---|---|
| 0 | `pendiente` | en cola, aun no ha empezado |
| 1..7 | `generando` | a medias |
| 8, todas con texto | `completo` | listo |
| 8, alguna sin texto | `parcial` | fallo alguna seccion — se ve cual |

**Limite conocido y declarado:** si el worker se cae, una label se queda en
`pendiente` o `generando` para siempre. No se inventa un timeout: el boton
manual es la via de recuperacion, que es exactamente lo que pide la tolerancia
del punto (4).

---

## 3. Los cambios

### 3.1 `upload.py` — el disparo

```python
def _lanzar_mini_informes(execution_id, acceptance_criteria) -> List[str]:
    labels = list((acceptance_criteria or {}).get("critical_transactions") or [])[:MAX_TRANSACTIONS]
    if not labels:
        return []
    tarea = asyncio.create_task(_generar_mini_informes_bg(execution_id, labels))
    _MINI_INFORME_TASKS.add(tarea)
    tarea.add_done_callback(_MINI_INFORME_TASKS.discard)
    return labels
```

Se llama despues de guardar la ejecucion y de N3.4. **Sin transacciones marcadas
no se crea tarea ninguna** y el upload se comporta exactamente como hoy.

`_generar_mini_informes_bg` abre su **propia** sesion (`AsyncSessionLocal`),
recarga la ejecucion por id, parsea el JTL por el mismo camino que el POST
manual (`_parse_execution_df`) y llama a `generate_transaction_report` de N4.6
**sin duplicar logica**: es el mismo servicio que invoca el endpoint POST.

Tolerancia **por transaccion**: un `try/except` alrededor de cada label, de modo
que si una falla la siguiente se intenta igual. Y un `try/except` exterior que
garantiza que nada de esto puede propagarse hacia la ejecucion.

La respuesta del upload incorpora `auto_transaction_reports` con las labels
lanzadas, para que la pantalla sepa que tiene que sondear sin esperar al primer
tick.

De paso, las metricas que consume el mini-informe (`METRIC_KEYS`) pasan a estar
escritas **una sola vez**: estaban a mano en el POST y ahora las comparten las
dos rutas, para que la IA reciba exactamente lo mismo por las dos vias.

### 3.2 `upload.py` — el estado

`GET /executions/{id}/transaction-reports/status`:

```json
{
  "execution_id": "...",
  "requested": ["token", "Adapter SendCode"],
  "status": "in_progress",
  "labels": [
    {"label": "token", "state": "generando", "done": 3, "total": 8, "failed_sections": []}
  ],
  "done_labels": 0, "total_labels": 2
}
```

### 3.3 `TransactionReportSection.tsx` — la pantalla

Sondea ese estado cada 4 s (`POLL_MS`, el mismo que ya usaba N4.7) mientras
`status === 'in_progress'`, muestra **"Generando token — 3 de 8"** con el
contador de transacciones, y al terminar recarga sola la que este abierta. Las
marcadas entran en la lista aunque todavia no tengan ni una fila, para que se
vean desde el primer segundo.

Si el sondeo falla, se corta y la pantalla queda usable con el boton manual: no
se deja un spinner eterno (mismo criterio que N4.7).

**El boton manual SE CONSERVA**, para regenerar o para una transaccion que no se
marco al inicio. Y una barra ambar lista las que quedaron `parcial`, con el
nombre de la transaccion, para que se sepa cual reintentar.

Regla 16 verificada: todos los hooks (incluido el `cargarRef` nuevo) van antes
de `if (!labels.length) return null`.

---

## 4. Tamaño

```
 backend/app/api/v1/endpoints/upload.py               | 179 ++++++++-
 backend/app/services/ai/transaction_report.py        |  10 +-
 .../dashboard/TransactionReportSection.tsx           |  88 ++++++
 3 files changed, 274 insertions(+), 3 deletions(-)
```

274 lineas insertadas, de las cuales 30 en blanco, 33 de comentario y 40 de
docstring: **171 de codigo efectivo**, dentro del presupuesto de 120-180. Las 3
lineas sustituidas son el import de N3.4 (ampliado), la lista de metricas
(extraida a `METRIC_KEYS`) y la llamada a `_generate`.

---

## 5. Validacion — con stub, coste de IA CERO

Se sustituyo el analizador por uno falso que tarda 0,3 s **bloqueantes** por
seccion (igual que el `_generate` real) y que hace fallar todas las secciones de
la **segunda** transaccion. Se ejercitaron las funciones reales: el disparo, la
tarea de fondo, la escritura en base y el endpoint de estado.

Se uso la ejecucion de Coomeva (tiene el JTL en disco) sobre las transacciones
`Adapter VerifMethod` y `Adapter SendCode` — **nunca sobre `token`**, cuyas 8
filas reales alimentan la validacion de N4.8 y N4.9. Todo lo creado se borro al
final.

### A. Upload SIN transacciones marcadas — igual que hoy

```
criterios=None                             -> labels=[]  tareas creadas=0
criterios={}                               -> labels=[]  tareas creadas=0
criterios={'response_time': 2500}          -> labels=[]  tareas creadas=0
criterios={'critical_transactions': []}    -> labels=[]  tareas creadas=0
```

Ni tarea, ni escrituras, ni coste.

### B. Upload CON 2 marcadas — background sin bloquear

```
labels lanzadas       : ['Adapter VerifMethod', 'Adapter SendCode']
el disparo devuelve en: 0.0 ms  (la respuesta del upload no espera)
tarea viva en el set  : 1
duracion del trabajo  : 5.1 s
latidos durante ese rato: 99  (0 = event loop bloqueado)
-> el loop siguio libre : True
llamadas al analizador  : 16 (8 secciones x 2 labels)
```

El disparo devuelve en **0,0 ms**: la respuesta del upload no espera nada. Y los
**99 latidos** durante los 5,1 s demuestran que el event loop siguio atendiendo
— que es lo que hace posible el sondeo.

### C. Un fallo no arrastra al resto

```
Adapter VerifMethod    filas=8/8  con texto=8  sin texto=0
Adapter SendCode       filas=8/8  con texto=0  sin texto=8

-> la que fallo NO impidio la otra: True
-> la que fallo dejo sus 8 filas vacias (visible, no silenciosa): True
```

### D. La ejecucion y su informe general, intactos

```
updated_at / total_requests / conclusiones / recomendaciones iguales: True
filas de token intactas: True | con texto: 8
```

### E. El estado derivado

Con el trabajo terminado:

```
status      : completed        done/total: 2/2
  Adapter VerifMethod    state=completo   done=8/8  fallidas=0
  Adapter SendCode       state=parcial    done=0/8  fallidas=8
```

Simulando estados intermedios (borrando filas):

```
status: in_progress
  Adapter VerifMethod    state=generando  done=3/8
  Adapter SendCode       state=pendiente  done=0/8
```

### F. El endpoint por HTTP

```
GET .../transaction-reports/status              -> 200  {"status":"idle","requested":[],...}
GET .../00000000-.../transaction-reports/status -> 404  {"detail":"Ejecucion no encontrada"}
GET sin autenticar                              -> 401  {"detail":"No se pudieron validar las credenciales"}
```

### G. Limpieza y regresion

```
filas por label: {'token': 8}
estado identico al inicial: True
ejecucion intacta: True
```

Y las salidas de N4.8/N4.9 siguen igual:

```
export/pdf  = 200 / 1.315.819 bytes
export/html = 200 /   909.003 bytes
GET mini-informe de token = 200
```

### Lo que falta: un ciclo real

**El stub no gasta IA, pero tampoco la prueba.** Queda pendiente que Fredy haga
**un upload real con 2 transacciones marcadas**, que costara: los 12+2 analisis
del informe general (como siempre) **mas 8 llamadas por transaccion marcada**.
Con 2 marcadas son 16 llamadas adicionales, ~3 min de trabajo en background.

---

## 6. Dos correcciones que se hicieron sobre el propio test

Se dejan escritas porque las dos primeras lecturas del test daban un falso
resultado:

1. **El stub fallaba las dos transacciones.** Discriminaba por
   `if 'Adapter SendCode' in prompt`, pero el SYSTEM_PROMPT compartido **nombra
   a esa transaccion en sus ejemplos**, asi que aparecia en el prompt de
   cualquiera. Se cambio a contar vueltas (cada seccion `summary` abre una
   transaccion nueva).
2. **"ejecucion intacta: False"** al final. No era del codigo: el propio test
   escribia dos veces en `acceptance_criteria_json` para ejercitar el endpoint
   de estado, y eso movia `updated_at` por el `onupdate` del modelo. Se restaura
   explicitamente.

Y una del codigo, cazada antes de arrancar: `MAX_TRANSACTIONS` se usaba en
`upload.py` **sin importarlo**. `py_compile` pasaba igual — es la leccion del
reporte 046 — asi que se comprobo la resolucion real de nombres con `symtable`
contra el modulo importado:

```
upload.py            -> globales sin resolver: ninguno
transaction_report.py -> globales sin resolver: ninguno
```

---

## 7. Comprobaciones

| Check | Resultado |
|---|---|
| `py_compile` de los dos ficheros Python | OK |
| Resolucion de nombres globales | sin pendientes |
| `tsc --noEmit` | limpio, exit 0 |
| Ciclo Docker | `docker restart jmeter_backend`, sin build |
| Archivos de codigo tocados | 3 — bajo el limite de 4 |
| Codigo efectivo | 171 lineas (presupuesto 120-180) |
| Backups | `.bak_n410_20260820_084015` de los tres |
| Llamadas de IA | 0 (stub) |
| Estado fuera de memoria (`--workers 2`) | si — derivado de la base |
| Regla 16 (hooks antes de returns) | verificada |
| Regla 10 (sin Alembic, sin columnas nuevas) | respetada — el estado se deriva |
| Datos de Fredy | restaurados; `token` intacto |
| `origin` (Azure DevOps) | **no tocado** |
| Push | remoto `github` |

---

## 8. Estado final del sprint N4

| Paso | Que dejo | Commit |
|---|---|---|
| N4.1-N4.2 | Diagnostico de datos del mini-informe | — |
| N4.3 | `transaction_series.py` — las 5 series de una transaccion | — |
| N4.4 | `GET /transaction-charts` — las series bajo demanda | — |
| N4.5 | Tabla `transaction_chart_analyses` — los 8 textos, una fila cada uno | — |
| N4.6 | `generate_transaction_report` — las 8 secciones IA | — |
| N4.6b | Latencia, formato numerico y repeticion del pico | `8245bff` |
| N4.7 | La pantalla del mini-informe por transaccion | `7a5e95a` |
| — | **Fix de leyenda**: 3 entradas por transaccion, no 6 | `5bcf796` |
| N4.8 | El bloque en el **PDF individual** | `f6f1a97` |
| N4.9 | El bloque en el **HTML individual** y en el **informe integrado** | `a499653` |
| **N4.10** | **Generacion automatica al generar el reporte** | **`302e484`** |

El ciclo completo queda cerrado: se marcan transacciones en el panel, se pulsa
Generar Reporte, y el usuario acaba con el informe general y los mini-informes
de las marcadas — en pantalla, en el PDF individual, en el HTML individual y en
el informe integrado.

---

## 9. Pendiente de Fredy

1. **Validacion visual** del bloque de progreso: subir un JTL con 2
   transacciones marcadas y ver que, al abrirse el reporte, aparece
   "Generando <transaccion> — N de 8" y se completa solo.
2. Confirmar que el boton manual sigue sirviendo para regenerar y para una
   transaccion que no se marco al inicio.
3. Si alguna queda en `parcial`, comprobar que la barra ambar la nombra y que el
   boton la rehace.
