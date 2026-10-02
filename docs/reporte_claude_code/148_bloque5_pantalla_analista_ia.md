Pendiente de validación visual de Fredy · commit `523cdd1` · 2 de octubre de 2026 · Bloque 5 — la pantalla «Analista IA» (reporte 148)

# La pantalla «Analista IA»

Hecha según el diseño aprobado y el contrato del reporte 147. **No se tocó ningún protegido** (ni `Dashboard.tsx` ni
los exportadores) ni la pantalla de Nuevo Reporte (`UploadJTL.tsx`), que sigue en el menú. La aplicación estaba
cerrada (regla 31).

## 1. Lo que hay

**Menú:** Análisis → **Analista IA**, justo debajo de Nuevo Reporte (admin y analista).

| Ruta | Pantalla |
|---|---|
| `/performance/analista` | La ventana inicial **«Nueva prueba»** |
| `/performance/analista/<id>` | La pantalla única: chat a la izquierda (40 %) y **«Ficha del informe»** a la derecha (60 %) |

La conversación vive en la URL: **recargar la página la recupera tal cual**, y la ventana inicial ofrece
«Retomar una conversación» con las cinco últimas abiertas.

### 1.1 «Nueva prueba»

Cliente (los asignados), proyecto (obligatorio), tipo de prueba (seis botones) y la zona de los JTL (1 a 5,
`.jtl`/`.csv`/`.xml`). **Los JTL se pueden soltar en cualquier parte de la ventana**: al arrastrar, toda la ventana se
marca con «Suelta aquí los JTL». Un aviso en azul dice que los criterios de aceptación **no se escriben aquí**: se le
cuentan a la IA en la conversación. «Leer la prueba y conversar» crea la sesión (con el bloqueo «Leyendo la prueba…»)
y abre la conversación.

### 1.2 La pantalla única

- **Cabecera:** cliente · proyecto, el tipo, la unidad y los JTL; **«Cambiar datos de la prueba»** (cliente,
  proyecto, tipo y unidad; los JTL no se cambian: otra prueba es otra conversación) y **«Nueva conversación»**.
- **Chat:** los mensajes de la IA (el fijo de Kinetix lleva el rótulo «Mensaje de Kinetix (sin IA)»; el turno fallido
  sale en rojo), los avisos de la IA en ámbar, los **botones rápidos** («Ambiente y versión», «Objetivo de la prueba»
  e «Incidentes» escriben una plantilla en la caja; «No sé, sigue sin eso» se envía directo), la caja de texto
  (2.000 caracteres, **Ctrl+Enter** envía) y **«Adjuntar archivo»** para el CSV o XML de errores.
- **Ficha del informe:**
  - Título con **«Listo para generar: N de M»** (en verde) o **«Falta 1 dato obligatorio»** (en rojo), barra de
    avance, el detalle obligatorios/opcionales y **«Generar informe»**.
  - **La prueba:** seis cifras (peticiones, errores, P90, promedio, duración, usuarios), el **mini gráfico** de
    usuarios activos (línea) y fallos (barras) con la subida y la bajada sombreadas, las fases y la concentración de
    fallos.
  - **Criterios de aceptación:** cada uno con las palabras del analista, su alcance y su resultado (**Cumple · No
    cumple · No evaluado · Lo confirma el analista**) con el texto del servidor, la nota y el motivo. Se puede quitar
    uno; en los «lo confirma el analista», «Sí, cumple / No cumple». **Sin declarar: tarjeta en rojo con «obligatorio»**
    y el botón «No se acordó ninguno».
  - **Lo que contaste:** ambiente y versión, y las líneas del relato, cada una editable y con su «quitar».
  - **Detalle de errores** (solo con adjunto): por archivo, errores y grupos, el cruce con el JTL (verde si cuadra,
    ámbar si no) y los cuatro grupos mayores.
  - **Transacciones con informe propio:** casillas, con los errores y la marca «crítica»; dice por qué están
    marcadas (las que tienen errores, o las críticas según los criterios) y el tope de 10.
  - **Pendientes opcionales, en ámbar**, cada uno con «Sigue sin eso».

### 1.3 Generar

- **Sin criterios:** no genera. Aparece en el chat la pregunta que los pide (con ejemplos) y la etiqueta «obligatorio»
  de la tarjeta de criterios parpadea.
- **Con criterios (o «no se acordó ninguno»):** antes se comprueba la IA sin caché, como en Nuevo Reporte (F2). Si no
  está disponible, se abre el mismo panel rojo de Nuevo Reporte (no generar todavía · o aceptar generar sin IA).
  Después, el mismo bloqueo **«Procesando N archivo(s) JTL y generando análisis...»** y, al terminar, el informe. Si
  alguna sección cayó al respaldo, primero el aviso de F2 «tras generar», como hoy.

### 1.4 Errores visibles

| Caso | Lo que se ve |
|---|---|
| **IA caída** | Una franja roja bajo la cabecera, «La IA no está disponible: …», si `/ai-config/estado` falla. Si un turno falla, el mensaje en rojo en el chat y un aviso: «Tu mensaje quedó guardado y la ficha no cambió» |
| **Adjunto rechazado** | Aviso rojo en el chat: «Adjunto rechazado: » + el motivo del servidor (formato, tope, XML con DOCTYPE, CSV que no es de JMeter…) |
| **Sesión que no es tuya** (404) | Una ventana «Esta conversación no existe o no es tuya» con «Empezar una nueva» |
| Límites (429), sesión ya generada (409), datos inválidos (422) | El texto del servidor, en el aviso del chat |

## 2. Lo que se añadió al backend

Pequeño y aditivo; el contrato del 147 sigue valiendo:

- **`ficha.serie`**: `{"paso_s": 3, "puntos": [[segundo, usuarios | null, fallos], …]}`, como mucho 120 puntos, para el
  mini gráfico. Las sesiones creadas antes no la tienen: la tarjeta lo dice en lugar del gráfico.
- **`PUT /analista/sesiones/{id}/prueba`** `{proyecto, tipo, client_id, unidad}`: «Cambiar datos de la prueba». Si
  cambian el tipo o la unidad, rehace el bloque de la ejecución que recibe el chat. Mismos permisos que crear.

## 3. Pruebas

### 3.1 La IA sustituida en el 8002

`reiniciar_8002.sh --ia-falsa` levanta la MISMA app (`app_ia_falsa.py`) con la IA **del chat** leyendo un guion de
`/tmp/b5_ia_guion.json`: cada llamada toma la primera entrada (un objeto = la respuesta; `null` = la IA se cae). **Sin
guion se comporta igual que el 8002 sin IA**, así que las otras suites corren igual contra él. El informe, al generar,
no pasa por ahí: sin clave, sale con el respaldo. El script `reiniciar_8002.sh` mata ahora cualquier `uvicorn` del
8002 (antes buscaba solo `app.main:app`).

**Ojo, corrección del 147:** en el 147 levanté el 8002 con `--reload`. El arranque oficial es el de
`reiniciar_8002.sh`, **sin** `--reload` (por el corte de R1.1 del reporte 143). Ahora vuelve a estar así.

### 3.2 La suite de pantalla

`b5_pantalla.py` (Playwright, 5173 con `localhost:8001` resuelto al 8002, `/ai-config/estado` simulado «ok» salvo en
el paso de la IA caída): **42 comprobaciones, TODO PASA**.

1. Ventana inicial: la entrada en el menú (y Nuevo Reporte sigue), el aviso, el botón desactivado, **el JTL soltado
   sobre el título, fuera de la zona**.
2. Ficha inicial: cabecera, «Falta 1 dato obligatorio», criterios en rojo con «obligatorio», mini gráfico, cifras, 6
   transacciones con 3 marcadas, pendientes en ámbar, el primer mensaje.
3. Generar sin criterios → la pregunta en el chat, la tarjeta resaltada, ninguna ejecución.
4. Mensaje (Ctrl+Enter) → dos criterios con el resultado del servidor (Cumple, No cumple), «Listo para generar», la
   línea del relato, la caja vacía.
5. Adjunto CSV → tarjeta de errores con «Cuadra con el JTL» y aviso; un `.txt` → «Adjunto rechazado».
6. Casillas · «Cambiar datos de la prueba».
7. **Recargar**: misma URL, criterios, errores, mensajes y casilla como se dejaron.
8. IA caída: el turno en rojo con el mensaje conservado; la franja «La IA no está disponible».
9. Un analista abre la sesión de otro → «Esta conversación no existe o no es tuya».
10. Generar con criterios → «Procesando…», el aviso de F2 (el 8002 no tiene IA), el informe; la ejecución lleva el
    nombre, el tipo y los criterios de la ficha. **Sin errores de JavaScript.**

### 3.3 Regresión y compilación

- `cierre_r1.sh` → **CIERRE R1: TODO PASA**.
- `cierre_b5.sh` → **CIERRE B5: TODO PASA** (el backend del 147).
- `tsc --noEmit` → **sin errores**.

### 3.4 Capturas

`C:\proyectos\Kinetix_pruebas\mockups\analista\`: `01_ventana_inicial` · `02_ficha_inicial` · `03_faltan_criterios` ·
`04_ficha_con_criterios` · `05_adjunto` · `06_ia_caida` · `07_no_es_tuya` · `08_procesando` · `09_informe`.

**Huella**, toda en la base de pruebas: sesiones y ejecuciones «ZZTEST-B5 pantalla…», «ZZTEST-B5 ajena».

## 4. Lo que no se comprobó

- **Con la IA real.** La pantalla se probó con la IA del chat sustituida por un guion. La conversación real con
  gpt-5.5 es la del 147 (en proceso, sin pantalla).
- **Arrastrar con el ratón de verdad.** El arrastre se simuló con eventos `drop` sobre el título; un arrastre desde el
  Explorador de Windows no se ha probado.
- **Pantallas estrechas.** Probada a 1.440 × 900; por debajo de 1.024 px el chat y la ficha se apilan, sin revisar.
- **El informe con las tres secciones nuevas escrito por la IA real** sigue sin medirse (147 §9).
