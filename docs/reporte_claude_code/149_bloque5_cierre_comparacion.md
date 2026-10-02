Commit base `856062c` · 2 de octubre de 2026 · Bloque 5, cierre — el mismo informe tres veces con IA real, regresión de análisis y reglas nuevas (reporte 149)

# Bloque 5: cierre

**Pendiente de la validación visual de Fredy.** El menú no se ha tocado: «Analista IA» convive con «Nuevo Reporte»
hasta que Fredy decida el cambio.

## 1. «prueba 6», tres veces, con IA real y sin escribir

`backend/pruebas_e2e/corrida_comparacion_b5.py`, en proceso. El mismo arnés que `corrida_r2.py`: conexión a tu base
**de solo lectura** (`default_transaction_read_only=on`) con rollback al final, `_upsert` de los informes por transacción
sustituido por un colector, y tokens por intento sacados de la telemetría E1.2. **Nada se guardó en ninguna base.**
Modelo: openai gpt-5.5 (`medium`). Ejecución `b81d713b` («prueba 6», carga, 4.811 peticiones, 41,32 % de errores).

| Variante | Qué recibe |
|---|---|
| **(a) Como hoy** | Los criterios que guardó Nuevo Reporte: 100 usuarios, 2.000 ms, 99,5 %; informe propio para las 3 transacciones con errores |
| **(b) Criterios y relato** | La ficha que dejó la conversación real del 147: P90 < 1 s, disponibilidad ≥ 99 %, ninguna transacción por encima del 5 % de errores (cada una), ambiente QA y las dos líneas del relato (ronda corta para validar el script; desarrollo confirmó que Put y Delete no envían el token) |
| **(c) Lo mismo y un archivo de errores** | Un XML de JMeter **sintético** (1,2 MB), fabricado a partir de los 1.988 fallos del JTL, con `responseData`, `samplerData` y cabeceras, y con tres secretos falsos sembrados. Su resumen: 1.988 errores en 3 grupos, **cuadra con el JTL** |

**Resultado: `C:\proyectos\Kinetix_pruebas\r2\comparacion_analista.html`**, lado a lado: la tabla de costes, «qué recoge»
cada informe, lo que reciben los prompts de nuevo y las 10 secciones del general y las 6 de cada transacción. Los datos,
en `comparacion_analista.json` y `errores_sinteticos.json`.

### 1.1 Coste

| | (a) Como hoy | (b) Criterios y relato | (c) + archivo de errores |
|---|---|---|---|
| Llamadas (al respaldo) | 28 (0) | 28 (0) | 28 (0) |
| Tiempo total | 326,9 s (general 110,4 · transacciones 216,5) | 337,1 s (142,0 · 195,1) | 296,8 s (111,4 · 185,4) |
| Tokens de entrada | 142.597 | 155.385 (+9 %) | 165.372 (+16 %) |
| …en caché | 86.272 (60,5 %) | 107.520 (69,2 %) | 121.856 (73,7 %) |
| …sin caché | 56.325 | 47.865 | 43.516 |
| Tokens de salida (razonamiento) | 23.925 (17.783) | 24.356 (18.220) | 22.516 (16.499) |
| Veredicto del motor | NO APTO | NO APTO | NO APTO |
| Avisos del detector de estilo | 0 | 0 | 0 |

- **Las secciones nuevas añaden entre un 9 % y un 16 % de entrada**, y como van en el bloque común, se pagan a precio
  de caché.
- **Ojo con la caché: el orden favorece a (b) y (c).** Las tres variantes comparten el principio del bloque de la
  ejecución (cifras, tabla, fases) y se corrieron seguidas, a → b → c: (a) arrancó en frío. La bajada de los tokens sin
  caché no demuestra que el Analista IA salga más barato; demuestra que no sale más caro.
- **El tiempo es el de siempre** (de 5 a 5,6 minutos para 28 llamadas). Las diferencias entre variantes están dentro del
  ruido de la API.

### 1.2 Qué recoge cada informe

Búsqueda automática sobre el resumen, los errores, las conclusiones y las recomendaciones. Es orientativa; la lectura
de los textos está debajo.

| | (a) | (b) | (c) |
|---|---|---|---|
| El criterio nuevo «errores por cada transacción» | no | sí | sí |
| La confirmación de desarrollo (el token no se envía) | no | sí | sí |
| Que era una ronda corta antes de la prueba larga | no | sí | sí |
| El ambiente (QA) | no | sí | no |
| Los códigos 404/405 (también están en el JTL) | sí | sí | sí |
| Ningún secreto del archivo a la vista (textos y prompts) | sí | sí | sí |

**Lo que se ve al leerlos:**

- **(a)** acierta en lo que dicen los datos (404 en Get, 405 en Put y Delete, Auth la más lenta, NO APTO por
  disponibilidad), pero **tiene que adivinar la causa**: habla de «configuración de métodos permitidos» y de «errores
  de correlación».
- **(b)** y **(c)** **usan lo que contó el analista**: atribuyen Put y Delete al token que no se envía «según la
  confirmación de desarrollo»; el dictamen nombra **los tres criterios** («cumple el de tiempo, incumple el de
  disponibilidad global y el de errores por transacción»). Y recogen la ronda corta de maneras distintas: (b) abre el
  resumen con «En esta validación corta en QA…», y (c) recomienda repetir **una validación corta y solo después pasar
  a la prueba larga**.
- **(c) no aporta mucho más que (b)**, porque el archivo sintético repite los códigos y mensajes del JTL
  («Method Not Allowed», «Not Found»). Sí añade una recomendación de script que (b) no tiene: comprobar que la reserva
  se creó antes de seguir el flujo. **Con un archivo real, con respuestas que el JTL no trae, la diferencia debería
  ser mayor: no se ha medido.**
- **Un riesgo que Fredy tiene que mirar:** en (b) y (c) la IA da por buena la explicación del analista y llama a los
  405 «coherentes con» la falta de token, aunque un 405 es «método no permitido», no un rechazo de autenticación. El
  prompt le dice que lo del analista es información para explicar, no para cambiar cifras; **no le pide que contraste el
  relato con los datos**. Si se quiere, es un ajuste de una línea en `services/analista/prompt.py` (que diga cuándo los
  datos no apoyan lo que cuenta el analista). No se ha hecho: es decisión de Fredy.

## 2. Regresión completa de análisis

Nuevo corredor `backend/pruebas_e2e/regresion_analisis.sh`. Reinicia el 8002, lo pasa a `--ia-falsa` solo para la
pantalla del Analista IA y lo deja como estaba.

| Suite | Resultado |
|---|---|
| Estructura de los prompts (2.2-2.5) | TODO PASA |
| Conclusión única del integrado (3) | TODO PASA |
| **Series y hechos de R2** (`r2_series.py`) | **FALLA — previo al bloque 5** (ver abajo) |
| Zona horaria de los informes (146) | TODO PASA |
| `/upload` igual que antes del bloque 5 (contra `2dc56bc`) | TODO PASA |
| F1 aviso de respaldo (backend) | TODO PASA |
| F2 aviso de respaldo (pantallas) | TODO PASA |
| Viñetas en las exportaciones (2.3) | TODO PASA |
| Pantalla de la conclusión única (3.5) | TODO PASA |
| Cierre R1 (integrado R1.1-R1.4, C2 integrado, C2 individual) | TODO PASA |
| Cierre B5 (Analista IA, backend: A, B, C, D) | TODO PASA |
| Pantalla del Analista IA (148) | TODO PASA |

**`r2_series.py` falla igual con el código de antes del bloque 5.** Lo comprobé copiando `backend/app` de `2dc56bc` al
contenedor y corriendo la suite contra esa copia: los mismos nueve «FALLA». La causa es de la suite: corta el acceso a
la configuración de la IA («r2_series no toca la base») y, desde F1 y el bloque 2.2, el pipeline necesita un analizador
para armar los prompts. Sin él aborta antes de capturar nada. No la he arreglado: es de R2, no de este bloque.

**Lo que no está en la regresión:** las suites de etapas viejas que apuntan a ejecuciones concretas de tu base
(E2-validación, E5, Nova vía `/tmp/e2e`) o que entran con contraseña (`KX_PWD`, regla 26): `avisos_estilo`,
`avisos_general`, `capas_*`, `dialogo_export`, `export_alcance`, `panel_seleccion`, `panel_boton_criterios`,
`tabla_por_transaccion`, `integrado_*`, `hf4_check`, `verificar_etapa2`, `criterios_5b2`, `criterios_en_prompts`,
`e5_verdictos`, `tramos_fases` y `captura_prompts_r2`. Las C2 sí van, dentro de `cierre_r1.sh`.

## 3. Documentación

- **`CLAUDE.md`**: el estado del Analista IA en §1; la tabla de rutas `/analista` en §4; el corredor
  `regresion_analisis.sh` en la regla 36; y **tres reglas nuevas en §13.2**:
  - **37**: los criterios se cuentan en la conversación, sin criterios no se genera, y lo del analista llega a los
    prompts entre marcas de datos;
  - **38**: el resultado de un criterio lo calcula el servidor con el JTL, nunca la IA, y lo no declarado queda sin
    límite;
  - **39**: todo lo que sale de un adjunto se enmascara antes de guardarse o llegar a un prompt, el XML se lee sin
    DOCTYPE, y ni el archivo ni los mensajes van al log.
- **`PROJECT_STATUS.md`**: el plan de análisis (puntos 4, 5 y 6, con la decisión pendiente del menú) y la deuda del
  Analista IA.

## 4. Lo que no se comprobó

- **Un archivo de errores real.** Sigue sin haber muestras (`Kinetix_pruebas\muestras_errores\` no existe).
- **La variante (b) o (c) con la caché en frío.** Para medir el coste sin el sesgo del orden habría que correr cada
  variante sola, en otro momento: 28 llamadas más cada una.
- **Una sola corrida por variante.** El modelo no es determinista: las diferencias de redacción entre (b) y (c) pueden
  ser azar.
