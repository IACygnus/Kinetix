# Especificación funcional del informe — Kinetix Pro

**Versión 1.1 · Aprobada por Fredy Bonilla**

Referencia única de cómo debe quedar el informe. Todo prompt de desarrollo se valida
contra este documento, no contra mensajes anteriores.

---

## 0. Términos

**Nunca se usa la palabra "mini-informe".** El producto es un **informe**:

- **Informe general** — todas las transacciones juntas. Es lo que existe hoy.
- **Informe por transacción** — el mismo informe general, filtrado a una transacción.
- **Conclusiones y recomendaciones** — una sola vez, al final, sobre toda la prueba.

El título de cada informe por transacción es **el nombre de la transacción**. Nada más.

---

## 1. Estructura del informe completo

```
PORTADA

INFORME GENERAL
  Tabla resumen por transacción (todas)
  Análisis del resumen
  Gráfica 1 + su análisis
  Gráfica 2 + su análisis
  …las N gráficas generales

[nombre de la transacción 1]          ← página nueva en el PDF
  Tabla resumen (solo esa transacción)
  Análisis del resumen de esa transacción
  Sus gráficas + sus análisis

[nombre de la transacción 2]          ← página nueva en el PDF
  …lo mismo

CONCLUSIONES Y RECOMENDACIONES        ← una sola vez, de toda la prueba
```

**El informe por transacción es el informe general con el mismo diseño, filtrado.**
Mismas tablas, mismas gráficas, mismo estilo visual. No es un formato nuevo.

### 1.1 Qué cambia respecto a lo que existe hoy

| Hoy | Debe quedar |
|---|---|
| Se llama "Mini-informe por Transaccion" | Se titula con el nombre de la transacción |
| Cada transacción tiene sus conclusiones y recomendaciones | **No las tiene.** Van solo al final, generales |
| Diseño propio, distinto del general | **Mismo diseño** que el general |
| 8 secciones de IA por transacción | **6**: resumen + 5 gráficas |

### 1.2 Las gráficas

| Gráfica | ¿Por transacción? |
|---|---|
| Response Times | Sí |
| Latency | Sí |
| Error Rate | Sí |
| Response Codes | Sí |
| Transactions per Second | Sí |
| Active Threads | **No** — los hilos son de toda la prueba |
| Throughput Over Time | **Se retira del producto entero** |

---

## 2. Panel de selección (pantalla Nuevo Reporte)

### 2.1 Columnas

| Hoy | Debe quedar |
|---|---|
| Transacción · Muestras · Promedio · P90 · Max · Errores | **Transacción · Muestras · Promedio · TPS · Errores** |

Se quitan P90 y Max. Se añade TPS.

### 2.2 Criterios por transacción, dentro de la tabla

El bloque desplegable "Criterios por Transaccion" que hoy vive aparte **desaparece**.

Cada fila de la tabla se despliega y muestra los criterios de aceptación de esa
transacción (concurrencia, tiempo de respuesta, disponibilidad), editables. Al
cambiarlos, **la criticidad de esa transacción se recalcula de inmediato**.

Sin criterios propios, se evalúa con los globales.

---

## 3. Gráficas: control de capas

Las gráficas muestran dos líneas por transacción: promedio (sólida) y máximo
(punteada). Debe poder **apagarse cualquiera de las dos capas**, y el tooltip debe
mostrar **solo la capa activa** — hoy lista todas las series y se ve duplicado.

- Por defecto: **ambas visibles**.
- Aplica en **pantalla** y en el **HTML exportado**.
- En el PDF se imprime lo que estuviera seleccionado.

---

## 4. Estilo de los textos de IA

### 4.1 Prohibido el vocabulario de especialista

| No escribir | Escribir |
|---|---|
| "tier excelente" / "tier degradado" | "tiempos bajos" / "tiempos altos", o la cifra |
| "P90 de 3.515 ms" a secas | "1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)" |
| "alta variabilidad" | "unos usuarios esperan mucho más que otros" |
| "latencia crítica" | describir el efecto concreto |

### 4.2 El veredicto de producción va solo en las conclusiones

Los análisis de sección **no dicen** si el sistema está listo para producción. Eso
pertenece a las conclusiones finales. Un análisis describe, interpreta y señala el
impacto; no dictamina.

### 4.3 Referencia de estilo aprobada

> La prueba ejecutó un total de 10.075 transacciones, obteniendo un 28,20% de errores
> globales (2.841 errores). El comportamiento de la aplicación fue estable durante los
> tres primeros pasos del flujo (Auth, Get Booking y Post Create Booking), los cuales
> registraron 0% de errores y tiempos de respuesta adecuados para una carga de 10
> usuarios concurrentes.
>
> Sin embargo, a partir de las operaciones que interactúan con el identificador de la
> reserva (Get_Booking_Id, Put_Update_Booking y Delete_Booking_Id) se presentó una
> degradación funcional significativa, evidenciada por porcentajes de error de 41,26%,
> 56,77% y 71,42%, respectivamente. Estos resultados indican que la aplicación logra
> crear las reservas correctamente, pero presenta problemas al consultarlas,
> actualizarlas o eliminarlas posteriormente.

Narra el flujo de negocio, agrupa lo que se comporta igual, explica qué significa
funcionalmente, y no usa ni una palabra de jerga.

Reglas vigentes que se conservan: cifras exactas, ratios, formato español
(8.600 · 0,27% · 1,1 segundos), cierre con impacto al usuario, sin markdown, sin
palabras prohibidas.

---

## 5. Tiempo de generación

El informe tardaba ~40 segundos y hoy tarda más de 5 minutos.

**Decisión de Fredy: se mantiene el modelo `gpt-5.5`.** No se vuelve a modelos
anteriores. La optimización se busca por otras vías:

| Vía | Ahorro |
|---|---|
| Retirar Throughput Over Time | 1 llamada por informe |
| Quitar conclusiones y recomendaciones por transacción | 2 llamadas por transacción |
| Agrupar llamadas de IA (enviar varias secciones juntas) | a evaluar con medición |

Antes de optimizar hay que **medir** dónde se va el tiempo con `gpt-5.5`: cuánto tarda
cada llamada y cuánto pesa el razonamiento del modelo.

---

## 6. Exportación

Al pulsar Generar PDF o Generar HTML, el sistema **pregunta qué incluir**:

- Solo el informe general, o
- El general más las transacciones que se seleccionen.

Aplica a las dos salidas.

---

## 7. Salidas

Todo lo anterior aplica igual en: pantalla, PDF individual, HTML individual e informe
integrado (PDF y HTML).

---

## 8. Convenciones de trabajo

| Tema | Regla |
|---|---|
| Repositorio real | remoto `github` (IACygnus/Kinetix). Único destino de push |
| Remoto `azure` | No recibe commits. Push bloqueado a propósito |
| Carpeta de reportes | `docs/reporte_claude_code/` — única, no se crean otras |
| Numeración de reportes | desde `01`, consecutiva, con hash de commit y fecha en la primera línea |
| Validación | Claude Code prueba todo lo que pueda; Fredy valida al final del ciclo |
