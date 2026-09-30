Commit base `3a01a4f` · 30 de septiembre de 2026 · Bloque 2, paso 1 — inventario de los prompts de análisis (solo lectura)

# Inventario de los prompts de análisis

No se ha cambiado código. Este reporte **no copia textos de clientes**. Cada prompt entero, con lo que
produjo en el «después» de Nova al lado, está en
**`C:\proyectos\Kinetix_pruebas\r2\inventario_prompts.html`**, fuera del repositorio. Lo genera
`backend/pruebas_e2e/inventario_prompts.py`, sin IA y sin base.

---

## 1. Cuántos son de verdad

**24 prompts, que salen de 13 plantillas**, más **el mensaje de sistema**, que va delante de casi todos.

| Familia | Prompts | Plantillas |
|---|---|---|
| Informe general | 11: resumen, errores, 6 gráficas, redirecciones, conclusiones y recomendaciones | 6: las 6 gráficas comparten `analyze_chart` |
| Informe por transacción | 6: resumen y 5 gráficas | 1: `build_section_prompts` |
| Capturas | 4: cada imagen, su respaldo por OCR, el global de monitoreo y el global de evidencias | 4 |
| Comparativo e integrado | 3: la comparativa, las conclusiones unificadas y el consolidado | 3 |

**Los «17» son los del informe: 11 generales y 6 por transacción.** Los otros 7 se lanzan desde otras
pantallas.

**Fuera del inventario:** el diseñador de scripts con IA (`script_ai.py`), que no escribe informes.

---

## 2. Los parámetros, que son casi los mismos para todos

| | Todos menos la captura | La captura (`analyze_image`) |
|---|---|---|
| Modelo | el de la configuración: **gpt-5.5** | el mismo |
| Razonamiento | `reasoning_effort` de la configuración, que hoy es **`medium`** (no `low`, que es el valor por defecto si está en NULL) | **no se envía** |
| Temperatura | 0,7 en el código, pero **no llega**: `openai_chat_completion` la filtra para la familia gpt-5 | 0,3, también filtrada |
| Tope de salida | 16.384 tokens (`OPENAI_MAX_TOKENS["gpt-5.5"]`) | **1.024**, y en gpt-5.5 el razonamiento cuenta dentro de ese tope |
| Mensaje de sistema | `SYSTEM_PROMPT` (o su variante con permiso de dictamen) | **ninguno**: el bloque de estilo va dentro del mensaje del usuario, sin la presentación del analista |

**Palabras vedadas y estilo**, comunes a todos por el mensaje de sistema:

- **las 15 reglas** (`estilo.BLOQUE_ESTILO`): vocabulario prohibido, percentiles en personas, formato
  español, cifras exactas, sin markdown, apertura con dato, hipótesis marcadas, sin dictamen fuera de
  las conclusiones (regla 10), cierre con impacto, párrafos de 2 a 4 oraciones y sin disculpas (regla 15);
- **el ejemplo de tono** de otra prueba.

Cada plantilla añade su tope de palabras y lo que tiene que cubrir.

---

## 3. La tabla

Tokens de entrada medidos en las tres corridas del «después» de R2: mínimo–máximo, **con el mensaje de
sistema incluido**. Los que no se corrieron llevan una estimación.

| # | Prompt | Archivo:línea | Qué recibe (además de las cifras) | Extensión | Entrada (tokens) | ¿Rampas? | ¿Dónde fallan? |
|---|---|---|---|---|---|---|---|
| 1 | Resumen de la prueba | `gemini.py:1450` | Criterios · hechos de R2 (primer y último fallo) | 180 pal. | 3.487–3.762 | No | Primero y último |
| 2 | Errores | `gemini.py:1550` | Criterios · lectura base · «del min A al min B» por error | 140 pal. | 2.765–3.017 | No | Primero y último |
| 3 | Tiempos de respuesta | `gemini.py:1652` (+`:1609`) | Serie R2 de cada transacción · criterios · lectura base | 130 pal. | 5.179–6.189 | No | Sí, degradación: tramos y episodios |
| 4 | Latencia | `gemini.py:1652` (+`:1638`) | Serie R2 · criterios · lectura base | 130 pal. | 2.908–3.099 | No | Sí, degradación |
| 5 | Tasa de error | `gemini.py:1652` (+`:1640`) | Serie R2 · criterios · lectura base | 130 pal. | 3.007–3.045 | No | **Sí** (constante, intermitente o a más), pero la serie trae también el primero y el último |
| 6 | Códigos de respuesta | `gemini.py:1652` (+`:1642`) | Códigos en el tiempo · criterios · lectura base | 130 pal. | 2.872–3.055 | No | Las dos cosas: «primera vez» y «se concentra» |
| 7 | Transacciones por segundo | `gemini.py:1652` (+`:1644`) | Serie R2 · criterios · lectura base | 130 pal. | 3.145–3.492 | Pide el arranque sin saber dónde acaba | No aplica |
| 8 | Usuarios activos | `gemini.py:1652` (+`:1646`) | Serie de hilos · criterios · lectura base | 130 pal. | 2.845–3.767 | **Sí**, el único | Por nivel de concurrencia |
| 9 | Redirecciones | `gemini.py:1686` | Recuento y etiquetas | plantilla | — (no se generó) | No | No aplica |
| 10 | Conclusiones | `gemini.py:1784` | Criterios y veredicto · **los textos de todas las secciones**. Sin series | 350 pal., 6 párrafos | 4.417–4.672 | De segunda mano | De segunda mano |
| 11 | Recomendaciones | `gemini.py:1903` | Criterios · los textos de las secciones | 350 pal. | 4.147–4.372 | De segunda mano | De segunda mano |
| 12 | Transacción · resumen | `transaction_report.py:150` (+`:84`) | Criterio de la transacción · **sus 5 series** | 200 pal. | 3.817–4.197 | No: sus series no llevan los hilos | Puntual o sostenido |
| 13 | Transacción · tiempos | `transaction_report.py:150` (+`:87`) | Su serie · lectura base de la transacción | 130 pal. | 3.072–3.268 | No | Sí, degradación |
| 14 | Transacción · latencia | `transaction_report.py:150` (+`:88`) | Ídem | 130 pal. | 3.207–3.397 | No | Sí, degradación |
| 15 | Transacción · error | `transaction_report.py:150` (+`:89`) | Ídem (con el peor y el mejor minuto) | 130 pal. | 3.105–3.266 | No | **Sí**, peor minuto y concentración |
| 16 | Transacción · códigos | `transaction_report.py:150` (+`:90`) | Ídem | 130 pal. | 2.896–3.139 | No | Las dos cosas |
| 17 | Transacción · caudal | `transaction_report.py:150` (+`:91`) | Ídem | 130 pal. | 3.051–3.172 | Pide el arranque sin saberlo | No aplica |
| 18 | Captura (cada imagen) | `gemini.py:1295` | La imagen · **la descripción que escribe el analista** | 300 pal. | ~1.900 + la imagen (estimado) | No | No aplica |
| 19 | Captura por OCR | `gemini.py:1368` | El texto OCR · la descripción del analista | 200 pal. | ~1.900 (estimado) | No | No aplica |
| 20 | Global de monitoreo | `analysis_ai.py:75` | Cifras globales · los textos de cada captura | 500 pal. | ~2.200 + capturas (estimado) | No, y se le pide relacionar picos con carga | No |
| 21 | Global de evidencias | `analysis_ai.py:185` | Ídem, con evidencias | 400 pal. | ~2.100 + evidencias (estimado) | No | No |
| 22 | Comparativa carga/estrés | `compare.py:108` | Cifras globales de las dos pruebas y el cambio en % | 500 pal. | ~2.300 (estimado) | No, y en un estrés es lo que importa | No |
| 23 | Conclusiones unificadas del integrado | `integrated_report.py:1730` | Conclusiones de cada ejecución · capturas y evidencias | **sin límite** (7 + 7 puntos) | variable | No | De segunda mano |
| 24 | Consolidado del integrado | `integrated_report.py:2219` | Todo lo anterior · **las correcciones del analista, con prioridad** | 2 × 400 pal. | variable | No | De segunda mano |

- **Los prompts por transacción** se miden sobre 11 transacciones.
- **Los de pantalla** se estiman como el mensaje de sistema (~1.720 tokens) más la plantilla, a unos 3,7
  caracteres por token.
- **«Lectura base»** es el resumen ya escrito que R2 (R-D17) pasa a las demás secciones.

---

## 4. Lo que marcó el 136, prompt a prompt

### 4.1 Las rampas

- **Solo un prompt sabe dónde están la subida, la meseta y la bajada: el de usuarios activos (8).**
  Recibe la serie de hilos y se le pide contarlo.
- **Lo que sabe no llega a los demás como dato.** Llega a las conclusiones y a las recomendaciones solo
  como el texto que haya escrito.
- **Ninguna sección por transacción recibe los hilos.**
- **Los tramos de la serie de R2 son de 5 minutos fijos**, no las fases de la prueba. En Nova, el primer
  tramo mezcla 3:14 minutos de subida con 1:46 de meseta.

**Por eso en el 136, 5 de los 23 momentos citados caían en una rampa.**

### 4.2 Concentración o primero y último

| Lo que se le pide | Prompts |
|---|---|
| **Dónde se concentra** (tramos, episodios, peor minuto) | 3, 4, 5, 13, 14, 15 |
| **Primero y último** | 1 (los «hechos»), 2 («del min A al min B») |
| **Las dos cosas a la vez**: «cuándo aparece por primera vez» y «si se concentra» | 6, 16 |
| **Nada**: no reciben series | 10, 11, 20–24 |

**El primero y el último vienen además en los datos** de la tasa de error y de los códigos, aunque la
instrucción pida concentración. El modelo los cita porque están.

**Y las conclusiones heredan lo que escribieron las secciones.** En el 136, varios de los momentos de
rampa eran justo ese par: el primer y el último fallo.

### 4.3 Qué podría ir delante para la caché

| Qué | Hoy | Dónde está hoy |
|---|---|---|
| Mensaje de sistema (6.681 caracteres, ~1.720 tokens) | común a 23 de 24 | delante |
| Permiso de dictamen | 5 prompts | **dentro del sistema**, entre la regla 15 y el ejemplo. Parte en dos el prefijo común: las conclusiones comparten con el resto solo hasta la regla 15 |
| «Unidad de medida + tipo de prueba» (~250 caracteres) | las 11 generales | delante del mensaje del usuario |
| Criterios de aceptación | las 11 generales | **detrás de los datos** de cada sección |
| Lectura base (~1.300 caracteres) | 7 de las 11 generales: errores y las 6 gráficas | **detrás de los datos** de cada sección |
| Cabecera de la transacción (métricas, percentiles, criterio) | las 6 de una transacción | delante, pero **empieza por el nombre** de la transacción: de una transacción a otra no comparten nada tras el sistema |
| Línea de tiempo («la prueba va de…») | las 12 que llevan serie | en medio, delante de la serie: igual en todas las secciones de un informe, pero detrás de datos que cambian |

---

## 5. Incoherencias encontradas (no se corrigen: van al bloque de prompts)

1. **Los globales de monitoreo y de evidencias (20, 21)** piden «propón umbrales» y «propón acciones
   correctivas», pero reciben el mensaje de sistema **sin** permiso de dictamen, cuya regla 10 prohíbe
   convertir el análisis en lista de tareas.
2. **El global de monitoreo (20)** pide «relaciona los picos de consumo con los momentos de mayor
   carga» y **no recibe ninguna línea de tiempo** de la prueba.
3. **El respaldo por OCR (19)** pide «si el texto es pobre, di que no fue posible analizar el
   contenido»: la disculpa que prohíbe la regla 15.
4. **La captura (18):**
   - el estilo va dentro del mensaje del usuario, sin la presentación del analista;
   - no se envía el esfuerzo de razonamiento;
   - la salida está limitada a 1.024 tokens, razonamiento incluido.

   **Sin comprobar** si eso trunca o vacía respuestas: el `finish_reason` de las capturas no se ha
   mirado.
5. **Las conclusiones unificadas (23)** no tienen límite de palabras.
6. **Instrucciones muertas:**
   - `response_time_over_time` y `throughput` en el diccionario de `analyze_chart` (`gemini.py:1634`,
     `:1636`), retiradas en D19;
   - `conclusions` y `recommendations` en `transaction_report.INSTRUCCIONES` (`:94-95`), retiradas en
     D20.

   No se usan, pero siguen ahí.
7. **La comparativa (22)** no recibe series ni transacciones. En un estrés, lo que importa es en qué
   escalón se rompe, y no tiene cómo saberlo.
8. **`reasoning_effort` en `medium`.** CLAUDE.md §6 lo describe con `low` por defecto. El valor lo puso
   alguien desde la pantalla y **no es un error**, pero multiplica el razonamiento: en el 136, el 74 %
   de la salida era razonamiento.

---

## 6. Propuesta: una estructura común (solo propuesta)

**Principio:** lo que es igual en muchas llamadas va **delante y siempre en el mismo orden**; lo propio
de cada sección, **detrás**. OpenAI reutiliza la caché por bloques desde el principio del mensaje (136
§4.2), así que cuanto más largo y estable sea el tramo inicial, más se aprovecha.

```
┌─ 1. SISTEMA (una sola versión para todos)
│     rol del analista + las 15 reglas + ejemplo de tono
│     → el permiso de dictamen SALE de aquí
│
├─ 2. BLOQUE DE LA EJECUCIÓN (igual en todas las llamadas de un mismo informe)
│     unidad de medida · tipo de prueba · cifras globales · criterios de aceptación
│     · LÍNEA DE TIEMPO CON FASES: subida hasta min X, meseta, bajada desde min Y
│     · hechos de la prueba
│
├─ 3. LECTURA BASE (cuando ya existe)
│     general: el resumen ya escrito · por transacción: su resumen ya escrito
│
└─ 4. LO PROPIO DE LA SECCIÓN
      (por transacción: su cabecera; después, los datos y la serie de su gráfica)
      instrucción · extensión · lo que no debe decir
      · el permiso de dictamen, SOLO en conclusiones, recomendaciones,
        comparativa e integrado
```

**Qué gana cada familia:**

| Familia | Prefijo común que quedaría |
|---|---|
| Informe general | sistema + bloque de la ejecución + lectura base: igual en 7 de las 11 secciones |
| Por transacción | sistema + **el mismo bloque de la ejecución que el general**: igual para todas las transacciones del informe. Luego la cabecera y la lectura base de cada una, iguales en sus 6 secciones |
| Conclusiones y recomendaciones | todo lo anterior + los textos de las secciones en el mismo orden: la segunda llamada reutilizaría casi entera la primera |
| Capturas | pasan a usar el mismo sistema, en vez de llevar el estilo en el mensaje del usuario |

**Las fases, en un solo sitio y para todos.** `resumen_serie.py` ya calcula los hilos. Poner la subida,
la meseta y la bajada en el bloque de la ejecución (2), y usar las fases como tramos en vez de 5
minutos fijos, deja a todas las secciones separar lo que pasa al subir la carga de lo que pasa con la
carga sostenida. Y permite pedir **dónde se concentran** los fallos y la degradación **en la meseta**,
en lugar del primero y el último.

**Coste esperado, sin medir:**

- El bloque 1+2+3 rondaría los **2.500–3.000 tokens** por llamada, pagados a precio de caché a partir de
  la segunda llamada de cada informe.
- La serie de R2 seguiría pagándose entera, porque es lo propio de cada sección.
- **Hay que medirlo con una corrida**, igual que el 136.

**Qué tocaría, cuando se decida (no ahora):**

- `gemini.py` (plantillas y mensaje de sistema), `estilo.py`, `transaction_report.py`,
  `analysis_pipeline.py`, `resumen_serie.py` (las fases), y los prompts de `analysis_ai.py`,
  `compare.py` e `integrated_report.py`.
- **Ningún archivo protegido.** Son más de 3 archivos y más de 50 líneas, así que va **en pasos** (regla
  4), cada uno con su corrida antes y después.

---

## 7. Lo que no se comprobó

- **Los tokens de los prompts de pantalla (18–24)** son estimaciones: no se corrieron.
- **El tamaño exacto del mensaje de sistema en tokens.** ~1.720 es una regresión (136 §4). Hace falta
  `tiktoken` o una llamada.
- **Si el tope de 1.024 tokens de la captura** corta respuestas con gpt-5.5.
- **Cuánto ahorraría la estructura propuesta.** Hace falta una corrida.
