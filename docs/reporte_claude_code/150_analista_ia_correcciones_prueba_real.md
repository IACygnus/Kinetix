Commit base `442ee24` · 2 de octubre de 2026 · Reporte 150 — el Analista IA tras la primera prueba real de Fredy

# El Analista IA, corregido tras la prueba real de Fredy

**Pendiente de la validación de Fredy.** Sesión real: «prueba avianca · proyecto de prueba» (`ea4cdd73`), JTL
`resultados_general_carga 30-sept.-2026-162610`, ejecución generada `9b27f1a6`. **No se tocó ningún protegido** ni
el menú. Nada se escribió en la base de Fredy: todo lo suyo se leyó con conexiones de solo lectura.

| Parte | Commit | Qué |
|---|---|---|
| 1 · adjunto de errores | `bfb24d2` | El formato por el contenido; la causa por orden; enmascarado ampliado |
| 3 · criterios | `2d2b75d` | Alcance por servicio, tiempo con su medida, volumen calculado, «Así los entendí», correcciones que reemplazan |
| 2 · pantalla | `31e698c` | Soltar el archivo sobre el chat; criterios agrupados por transacción |
| 4 · el informe usa los criterios | `e578050` | Veredicto desde los criterios; resumen, conclusiones, recomendaciones y gráficas atados a ellos |
| 5-6 · coste y comprobación con IA real | `442ee24` | La corrida antes/ahora y el arreglo del resumen que salió de ella |

La parte 3 va antes que la 2 porque la pantalla pinta lo que la 3 calcula.

---

## 1. Lo que se encontró al mirar la prueba real

- **El archivo de errores no estaba en `Kinetix_pruebas\muestras_errores\`** (la carpeta no existe). Estaba en
  Descargas: `resultados_log_carga_error_General 30-sept.-2026-162610.csv`. **Nunca llegó a la sesión:** era XML con
  extensión `.csv`, y la versión anterior detectaba el formato por la extensión y lo rechazaba («no parece un CSV de
  JMeter»). Lo leí para diseñar el lector. **No se versionó ni se copió al repositorio ni a este reporte.** Para las
  pruebas se copió al contenedor en `/tmp` y se borró al terminar cada corrida.
- **Fredy desmarcó las tres casillas** de transacciones con informe propio (`informe_origen = analista`). Por eso la
  ejecución no tiene informes por transacción. No es un fallo.
- **La configuración de IA pasó de `medium` a `low` a las 17:51 UTC (12:51 en Colombia)**, cinco minutos después de su
  generación. El cambio vino del navegador (172.18.0.1, `POST /api/v1/ai-config`), desde la pantalla de configuración.
  Lo menciono porque condiciona el §7: **hoy todo se genera ya con razonamiento bajo.**

## 2. Diagnóstico de la parte 4

1. **El bloque de criterios sí llegó** a las 10 llamadas: la ejecución guarda `acceptance_criteria_json["analista"]`
   y el bloque se reconstruye igual (comprobado en solo lectura).
2. **Llegó con los resultados equivocados:** «5 s» se evaluó contra el **P90 de toda la prueba** (4.451 ms, «CUMPLE»,
   con una nota de que SaveFunds no lo cumplía por su cuenta); los 64.000 quedaron como «lo confirma el analista»; y
   la concurrencia, contra la prueba entera (35). Es decir, **tres de cuatro decían «CUMPLE»**.
3. **A las conclusiones les llegó «RESULTADO CALCULADO FRENTE A LOS CRITERIOS: APTO»**, de `compute_verdict`, que
   compara el **promedio global** (1.197 ms) con el umbral. El panel decía NO APTO (por transacción). Las conclusiones
   escribieron «apto para avanzar».
4. **El resumen no podía dictaminar:** la regla 7 de la guía («SIN DICTAMEN FUERA DE SU SITIO») y la falta del permiso
   al final del mensaje. Su instrucción pedía fallos y cuello de botella, no criterios, y con el tope de 4 cifras por
   párrafo.
5. **Las conclusiones tenían el dictamen «al final» y «sin repetir las cifras»**, y no recibían la lista de criterios
   incumplidos.

## 3. Parte 1 — el adjunto de errores

- **El formato se decide por el contenido** (`errores.detectar_formato`: `<` al principio es XML). Se admiten `.csv`,
  `.xml` y `.jtl`. Un XML llamado `.csv` se lee como XML, y un CSV llamado `.xml`, como CSV.
- **Cada grupo es transacción + código + CAUSA.** La causa sale, por este orden:
  1. el `failureMessage` de las aserciones (todas, unidas);
  2. el mensaje de error del `responseData` (JSON: `errors[].errorMessage`, `errors[].message`, `errorMessage`,
     `message`, `error_description`…);
  3. el `rm`.

  De una traza de Java, la primera línea y el último «Caused by» (la causa raíz).
- **Enmascarado ampliado** (`enmascarar.py`):
  - `Authorization` y cualquier Bearer, Basic o Digest;
  - el valor de cualquier clave JSON, etiqueta XML o parámetro de URL cuyo nombre contenga token, password, secret,
    key, doc, account, login, user, customer o name (además de las de antes);
  - IP v4 y v6, y MAC;
  - cuerpos en base64 o cifrados («[cuerpo cifrado, N caracteres]»: 40 o más caracteres seguidos con mayúsculas,
    minúsculas y dígitos);
  - números largos y correos.
- **El ejemplo de petición pone primero el método y la URL, luego las cabeceras y al final el cuerpo.** Se recorta a
  400 caracteres, y en el archivo real el cuerpo de más de 1.100 caracteres dejaba fuera las cabeceras.
- **Con el archivo real:** se lee como XML, salen sus 2 errores, la causa es la de la aserción y el `Authorization`
  sale tapado.

## 4. Parte 3 — los criterios

**Alcance** (`criterios_libres.normalizar`):

- Si el analista nombra servicios, el criterio se evalúa sobre ESAS transacciones: cada una por separado
  (`transacciones`) o sumadas (`suma`: «N entre A y B»).
- Sin servicios, los tiempos, errores y caudal valen **para cada transacción**. El volumen, el proceso y la
  concurrencia quedan **«no evaluado: falta saber a qué servicio se refiere»**, y la IA tiene orden de preguntarlo.
- **Toda la prueba, solo si el analista lo dice** (`toda_la_prueba`).
- Los nombres se resuelven con tolerancia: «asegurar fondos» → `1. SaveFunds_AsegurarFondos`, «originador» →
  `3. Webhook_Originator`. Lo ambiguo («webhook») no se asigna.

**Tiempo:** por transacción y con su medida. Sin medida, la IA la pregunta una vez; si no se sabe, P90, y la ficha dice
«medida supuesta». Si alguna transacción del alcance no cumple, el criterio es **no_cumple y nombra cuáles**. **Ya no
hay «Cumple» con una nota debajo.**

**Volumen** (tipo nuevo `volumen`): peticiones correctas de la transacción en la prueba o en la ventana que se diga
(«en 30 minutos»), **calculado**. El proceso que no llega a los registros pasa de «lo confirma el analista» a
**no_cumple**. «Lo confirma el analista» queda solo para lo que el JTL no puede medir (`otro`).

**Concurrencia de un servicio:** el máximo de usuarios de **su grupo de hilos** (`grpThreads`), no el de la prueba
entera. En la prueba de Fredy: 28 para SaveFunds y Originator; la prueba entera daba 35.

**Confirmación y correcciones:**

- Cuando la IA interpreta criterios, **el servidor añade «Así los entendí»**, con la lista por servicio: qué, cuánto,
  sobre qué medida y qué salió.
- **Una corrección REEMPLAZA.** Si la IA manda `reemplaza: [ids]`, se quitan esos criterios. Si no, el servidor
  reemplaza solo un criterio del mismo tipo y medida con **el mismo alcance**, o una **suma** de esas transacciones
  («es por servicio, no el total»).
- Un criterio general no se traga a uno concreto, y una misma tanda no se corrige a sí misma.

**El veredicto sale de los criterios** (`criterios_libres.veredicto`): NO APTO si alguno no se cumple (también los
confirmados como no cumplidos por el analista); APTO CON RESERVAS si queda alguno sin poder medirse; APTO si se cumplen
todos. Por transacción, según los criterios que la tocan. La ficha marca como críticas las transacciones que los
incumplen.

**Arreglos de paso:** `a_motor` dejaba un `{}` suelto en `per_transaction` (se veía en la ejecución de Fredy), y
`para_ejecucion` no copiaba la ventana ni la medida supuesta.

## 5. Parte 2 — la pantalla

- **Soltar un archivo sobre el chat lo adjunta**, igual que el botón, con el aviso «Suelta aquí el archivo de errores
  de JMeter».
- **La tarjeta de criterios:**
  - arriba, «Según tus criterios: NO APTO»;
  - debajo, **los criterios agrupados por transacción**, con lo medido en cada una y su resultado;
  - al final, «Tal como lo dijiste», con las acciones de siempre.

## 6. Parte 4 — el informe usa los criterios

Solo con criterios del Analista IA declarados. **Nuevo Reporte y «no se acordó ninguno» quedan como estaban**
(`estructura_prompts.py` y la sección 5 de `b5_g_informe_criterios.py` lo comprueban).

| Dónde | Qué recibe ahora |
|---|---|
| Veredicto guardado (`analysis_pipeline`) | El de los criterios, global y por transacción. Sale aunque el motor no entienda el criterio (un volumen o un máximo) |
| Bloque común | El resultado frente a los criterios y cuáles no se cumplen, fuera de las marcas (lo arma Kinetix) |
| Resumen | **Todos** los criterios con su medida, la instrucción de abrir con el dictamen servicio por servicio, sin tope de 4 cifras (hasta ~220 palabras), y **el permiso de dictamen** |
| Conclusiones | «RESULTADO CALCULADO FRENTE A LOS CRITERIOS DE ACEPTACIÓN» (ya no el del promedio), la lista de incumplidos, primera viñeta = dictamen con la cadena de causa (relato y errores), una viñeta por criterio incumplido |
| Recomendaciones | Al menos una por criterio incumplido: qué lograr, en qué servicio y sobre qué medida |
| Gráficas | Los criterios que toca su dato: tiempos (tiempo), errores y códigos (errores), TPS (caudal, volumen y proceso), usuarios (concurrencia) |
| Cada transacción | **Sus** criterios con **su** medida, en lugar del bloque de los tres fijos del motor |

**Guía de estilo:**

- El tope de 4 cifras no aplica al resumen ni a las conclusiones cuando hay criterios.
- Con criterios, el dictamen va primero.
- El resumen entra en las secciones con permiso de dictamen del detector.
- **Los dos modelos de Fredy** están en la guía con Servicio A, B y C. **Un cambio sobre su texto:** «percentil 95 de
  8.108 ms» pasó a «1 de cada 20 usuarios esperando más de 8,1 segundos (P95: 8.108 ms)». La regla 3 de la guía obliga
  a contar los percentiles en personas, y con la frase literal el detector marcaba el propio modelo y cada resumen que
  lo imitara. **Si Fredy prefiere su forma, hay que cambiar la regla 3, no el modelo.**

**El veredicto coherente no necesitó tocar ningún protegido.** `Dashboard.tsx` pinta `verdict` y
`verdicts_per_transaction`, y ahora traen los de los criterios. **Lo que sigue incoherente en pantalla:** la columna de
umbral de la tabla por transacción (`Dashboard.tsx:687`, protegido) muestra el `response_time` del motor o 2.000 ms. Con
un criterio de tiempo máximo, el motor no tiene umbral (solo entiende P90), y la columna dice 2.000. Arreglarlo exige
tocar `Dashboard.tsx`: **decisión de Fredy**.

## 7. Coste y tiempo

Telemetría E1.2 (`AI_TELEMETRY`, por intento).

| | Llamadas | Entrada | En caché | Salida | Razonamiento | Segundos | Por llamada |
|---|---|---|---|---|---|---|---|
| **Informe de Fredy** (9b27f1a6, medio, solo general) | 10 | 50.501 | 33.536 (66,4 %) | 8.817 | 6.325 | 122,1 | 5.050 ent. · 882 sal. · 12,2 s |
| **El 140** (2.5, medio) | 96 | 484.537 | 292.096 (60,3 %) | 78.071 | 57.215 | 1.191,3 | 5.047 ent. · 813 sal. · 12,4 s |
| **Chat de Fredy** (medio) | 3 | 9.095 | 0 | 1.871 | 1.202 | 23,3 | 3.032 ent. · 624 sal. · 7,8 s |
| Informe nuevo, criterios corregidos, **medio** | 28 | 181.224 | 121.088 (66,8 %) | 22.414 | 15.892 | 311,7 | 6.472 ent. · 800 sal. · 11,1 s |
| Informe nuevo, **bajo** (su configuración actual) | 28 | 181.714 | 140.288 (77,2 %) | 10.972 | 4.189 | 178,1 | 6.490 ent. · 392 sal. · 6,4 s |
| Su chat repetido, **medio** | 3 | 10.059 | 0 | 3.359 | 2.365 | 39,8 | |
| Su chat repetido, **bajo** | 3 | 10.059 | 7.424 | 1.836 | 850 | 25,5 | |

Los segundos son la suma de las llamadas. Las 18 de transacción van en segundo plano, después de abrirse el informe.
**Lo que bloquea la pantalla** son las 10 generales: **137,8 s en medio y 77,2 s en bajo.**

**La entrada sube un 28 % por llamada** (de 5.050 a 6.472): es el bloque de criterios, el resultado frente a ellos y
el detalle de errores. **Sigue entrando en caché:** 66,8 % en medio, frente al 60,3 % del 140 y el 66,4 % del informe
de Fredy. Las llamadas sin caché son la primera de cada grupo y alguna suelta, como siempre.

**El chat de Fredy no aprovechó nada de caché.** No comparte el sistema con el informe (tiene uno propio), así que no
puede reutilizar su caché. Entre turnos sí comparte el principio, pero el primer y el segundo mensaje estuvieron 5 min
43 s separados. Es probable que la caché se hubiera vencido, **pero no lo he comprobado**.

### La propuesta, con cifras medidas

**Razonamiento bajo en el chat y en las gráficas (generales y de transacción); medio solo en resumen, conclusiones y
recomendaciones.** Los números salen de la corrida de medio y de la de bajo: mismo JTL, mismos criterios y mismos
prompts.

| | Salida | Razonamiento | Segundos (las 28) | Segundos de bloqueo (las 10 generales) |
|---|---|---|---|---|
| Todo en medio (como el informe de Fredy) | 22.414 | 15.892 | 311,7 | 137,8 |
| **Propuesta** (3 en medio + 25 en bajo) | **13.565 (−39 %)** | **6.945 (−56 %)** | **208,8 (−33 %)** | **107,6 (−22 %)** |
| Todo en bajo (su configuración actual) | 10.972 (−51 %) | 4.189 (−74 %) | 178,1 (−43 %) | 77,2 (−44 %) |

- **Chat en bajo:** salida −45 %, razonamiento −64 %, tiempo −36 % (de 39,8 a 25,5 s por los 3 turnos). **El JSON
  salió válido en los 3 turnos con los dos esfuerzos**, y los dos entendieron igual lo esencial: los 64.000 como
  suma y la pregunta por la medida de los 5 s.
- **Calidad en bajo:** el informe en bajo también abre con el dictamen frente a los criterios, servicio por servicio,
  con las cifras; las conclusiones dan la cadena de causa y una viñeta por criterio. Se puede leer en la página (§8,
  desplegable). Los dos nombran la falta de `transactionIdSN`; el de medio además la explica como un problema de
  trazabilidad de la pignoración. La diferencia está en el matiz, no en si usa los criterios. Es una sola corrida
  de cada uno.
- **Para aplicarla hace falta código**, no solo configuración: hoy `reasoning_effort` es uno para todo el producto.
  Habría que darle un esfuerzo a cada sección (`analysis_pipeline` y `transaction_report`) y otro al chat. No lo he
  hecho: se pidió solo medir y proponer.

## 8. La comprobación con IA real

**`C:\proyectos\Kinetix_pruebas\r2\analista_v2.html`** contiene, en este orden:

1. Arriba, los criterios corregidos con su resultado, el veredicto antes y ahora, y los criterios tal como llegaron al
   informe de antes.
2. El coste.
3. El chat repetido.
4. **El informe general de antes y el de ahora, lado a lado y los dos con razonamiento medio.**
5. Los informes de las tres transacciones (solo en el de ahora).
6. Los textos en bajo, plegados.

Los datos están en `analista_v2_medium.json` y `analista_v2_low.json`.

Gpt-5.5 en proceso, **sin escribir en la base**:

- conexión de solo lectura;
- `_upsert` sustituido por un colector;
- sin contadores de uso;
- el esfuerzo forzado **solo dentro del proceso**, sin tocar `ai_config`.

**Criterios corregidos que se usaron, a confirmar con Fredy:**

| Lo que dijo | Cómo se tomó | Resultado |
|---|---|---|
| «5 segundos el tiempo de espera» | Tiempo **máximo** ≤ 5 s en cada servicio. La medida no la dijo; se tomó el máximo porque su propio modelo de resumen juzga los máximos | **No cumple**: Receptor 21.038 ms y SaveFunds 9.221 ms; Originator 788 ms |
| «64.000 entre asegurar fondos y originador… es por servicio» | **32.000 por servicio** en 30 min. **La IA real, con su misma frase, entendió 64.000 cada uno**: hay que preguntarle a él. El resultado es el mismo | **No cumple**: SaveFunds 9.516 y Originator 9.489 |
| «8.000 para receptor» en 30 min | ≥ 8.000 correctas | **Cumple**: 30.380 |
| «28 usuarios concurrentes» en los dos servicios | ≥ 28 en su grupo de hilos | **Cumple**: 28 y 28 |

**Veredicto:**

- **Antes:** NO APTO en el panel, pero las conclusiones decían «apto para avanzar».
- **Ahora:** NO APTO en los dos, y las tres transacciones NO APTO por sus criterios.

**El resumen de ahora** abre así: «La ejecución no cumplió los criterios de aceptación y queda no apta para producción
en estas condiciones». Sigue con el tiempo máximo servicio por servicio, el volumen frente a las 32.000 y las 8.000, y
la concurrencia, y al final cuenta los errores y el cuello de botella.

**Las conclusiones** abren con el dictamen y la cadena de causa: el tramo SaveFunds-Originator no llega al volumen, dos
servicios superan el máximo, y el error de SaveFunds deja una operación sin `transactionIdSN`. Después va una viñeta por
criterio incumplido.

**Un hueco que destapó la corrida y que quedó arreglado** (`442ee24`): el resumen recibía solo los criterios de tiempo
y abría hablando del tiempo, sin el volumen. Ahora recibe todos.

## 9. Pruebas

| Suite | Resultado |
|---|---|
| `b5_e_adjuntos_v2.py` (nueva) | TODO PASA: 23 comprobaciones; 28 con la copia temporal del archivo real presente |
| `b5_f_criterios_v2.py` (nueva, el caso de Fredy en sintético, en proceso con la IA sustituida) | TODO PASA: 24 |
| `b5_g_informe_criterios.py` (nueva, el informe con criterios, con colector) | TODO PASA: 21 |
| `cierre_b5.sh` (A-G) | **CIERRE B5: TODO PASA** |
| `b5_pantalla.py` (Playwright, `--ia-falsa`) | TODO PASA: 45, con el adjunto soltado sobre el chat y la agrupación |
| `estructura_prompts.py` | ESTRUCTURA: TODO PASA |
| `cierre_r1.sh` | CIERRE R1: TODO PASA |
| `tsc --noEmit` | sin errores |

**Suites viejas que cambiaron porque cambió la regla, no porque algo se rompiera:**

- **A:** un criterio sin servicio ya no se mide contra el total. Los de proceso y concurrencia llevan `toda_la_prueba`
  donde hacía falta. El proceso que no llega es no_cumple. La concurrencia por transacción ya es válida.
- **C:** los textos del bloque («cada transacción», «NO CUMPLE»), y la transacción recibe sus criterios en lugar del
  bloque del motor.
- **D:** los resultados que viajan a la ejecución, y «Así los entendí» al final de la respuesta.

**El JTL sintético** `ZZTEST-B5_fredy.jtl` queda en `/app/uploads` (prefijo ZZTEST).

## 10. Lo que no se comprobó

- **La pantalla con la IA real.** Se probó con la IA del chat sustituida por un guion. El chat real se comprobó en
  proceso (§7).
- **Un arrastre real desde el Explorador de Windows** sobre el chat. Se simuló con eventos `drop`.
- **Que la caché del chat se pierda por los 5 minutos.** Es una hipótesis.
- **Una sola corrida por variante.** El modelo no es determinista.

## 11. Lo que Fredy tiene que volver a probar

1. Ctrl+Shift+R. No hace falta reconstruir nada.
2. **Análisis → Analista IA**, nueva conversación con el mismo JTL.
3. **Soltar el archivo de errores sobre el chat**, el mismo `resultados_log_carga_error_General…csv`. Ahora lo lee: 2
   errores, la causa de la aserción y el cruce con el JTL.
4. **Decir los criterios como la otra vez.** Mirar:
   - que la IA entienda los 64.000 como suma y pregunte la medida de los 5 s;
   - que la respuesta traiga «Así los entendí» por servicio;
   - que la ficha los agrupe por transacción.
5. **Corregir «es por servicio, no el total»** y comprobar que el de la suma **desaparece**, sin duplicados. Decir
   cuántas por servicio son: 32.000 o 64.000.
6. Responder la medida del tiempo: máximo, P90… o «no sé».
7. **Generar** y mirar:
   - que el resumen abra con el dictamen servicio por servicio;
   - que la primera conclusión sea el dictamen;
   - que haya una recomendación por criterio incumplido;
   - que el veredicto de arriba diga lo mismo.
8. Decidir lo pendiente:
   - **el razonamiento por sección** (§7);
   - **la regla 3 frente a su modelo** (§6);
   - **la columna de umbral de `Dashboard.tsx`** (§6).
