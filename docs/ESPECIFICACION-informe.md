# Especificación funcional del informe — Kinetix Pro

**Versión 1.0 · 20/09/2026 · Pendiente de aprobación de Fredy**

Este documento es la referencia única de cómo debe quedar el informe. Todo prompt de
desarrollo se valida contra esto, no contra mensajes anteriores.

---

## 0. Términos

**Nunca se usa la palabra "mini-informe".** El producto es un **informe**, que se compone de:

- **Informe general** — todas las transacciones juntas. Es lo que existe hoy.
- **Informe por transacción** — el mismo informe, filtrado a una sola transacción.
- **Conclusiones y recomendaciones** — una sola vez, al final, sobre toda la prueba.

El título de cada informe por transacción es **el nombre de la transacción**. Nada más.

---

## 1. Estructura del informe completo

```
┌─ PORTADA
│
├─ INFORME GENERAL
│    Tabla resumen por transacción (todas)
│    Análisis del resumen
│    Gráfica 1 + su análisis
│    Gráfica 2 + su análisis
│    …las N gráficas generales
│
├─ [nombre de la transacción 1]          ← página nueva
│    Tabla resumen (solo esa transacción)
│    Análisis del resumen de esa transacción
│    Sus gráficas + sus análisis
│
├─ [nombre de la transacción 2]          ← página nueva
│    …lo mismo
│
└─ CONCLUSIONES Y RECOMENDACIONES        ← una sola vez, de toda la prueba
```

**El informe por transacción es el informe general con el mismo diseño, filtrado.**
Mismas tablas, mismas gráficas, mismo estilo visual. No es un formato nuevo.

### 1.1 Qué cambia respecto a lo que existe hoy

| Hoy | Debe quedar |
|---|---|
| Se llama "Mini-informe por Transaccion" | Se llama por el nombre de la transacción |
| Cada transacción tiene sus propias conclusiones y recomendaciones | **No las tiene.** Van solo al final, generales |
| Diseño propio, distinto del informe general | **Mismo diseño** que el general |
| 8 secciones de IA por transacción | **6**: resumen + 5 gráficas |

### 1.2 Las gráficas

Del informe general, por transacción aplican estas:

| Gráfica | ¿Por transacción? |
|---|---|
| Response Times | Sí |
| Latency | Sí |
| Error Rate | Sí |
| Response Codes | Sí |
| Transactions per Second | Sí |
| Active Threads | **No** — los hilos son de toda la prueba, no de una transacción |
| Throughput Over Time | **Se retira del producto entero** (decisión de Fredy) |

---

## 2. Panel de selección (pantalla Nuevo Reporte)

### 2.1 Columnas de la tabla

| Hoy | Debe quedar |
|---|---|
| Transacción · Muestras · Promedio · P90 · Max · Errores | **Transacción · Muestras · Promedio · TPS · Errores** |

Se quitan **P90** y **Max**: con pocas muestras repiten el mismo valor del promedio y
confunden. Se añade **TPS**.

### 2.2 Criterios por transacción — dentro de la tabla

El bloque desplegable "Criterios por Transaccion" que hoy vive **aparte, debajo** de la
tabla, desaparece como bloque independiente.

En su lugar: **cada fila de la tabla se despliega** y muestra los criterios de aceptación
de esa transacción (concurrencia, tiempo de respuesta, disponibilidad), editables.

Al cambiarlos, **la criticidad de esa transacción se recalcula inmediatamente**, igual que
ocurre hoy al cambiar los criterios globales.

Si una transacción no tiene criterios propios, se evalúa con los globales — como hoy.

---

## 3. Gráficas: control de promedio y máximo

Hoy cada transacción dibuja dos líneas (promedio sólida, máximo punteada), lo que satura
la gráfica y se presta a malinterpretación.

**Se añade un control encima de la gráfica** para elegir qué se muestra:

```
Mostrar:  ( ) Promedio    ( ) Máximo    ( ) Ambos
```

- Aplica en **pantalla** y en el **HTML exportado** (donde el usuario puede interactuar).
- En el **PDF** no hay interacción: se imprime lo que estuviera seleccionado, o el valor
  por defecto.
- Valor por defecto: **a decidir por Fredy** (recomendación: "Ambos", que es lo actual).

---

## 4. Estilo de los textos de IA

### 4.1 Prohibido el lenguaje técnico de especialista

El informe lo leen gerentes, no solo ingenieros de performance. **Queda prohibido**:

| No escribir | Escribir |
|---|---|
| "tier excelente" / "tier degradado" | "tiempos bajos" / "tiempos altos", o la cifra directamente |
| "P90 de 3.515 ms" a secas | "1 de cada 10 usuarios espera más de 3,5 segundos (P90: 3.515 ms)" |
| "alta variabilidad" | "unos usuarios esperan mucho más que otros" |
| "latencia crítica" | describir el efecto concreto |

### 4.2 El veredicto de producción va solo en las conclusiones

Los análisis de sección **no dicen** si el sistema está o no listo para producción. Eso
pertenece a las conclusiones finales. Un análisis de gráfica describe, interpreta y señala
el impacto; no dictamina.

### 4.3 Referencia de estilo aprobada

Texto objetivo (ejemplo real aprobado por Fredy):

> La prueba ejecutó un total de 10.075 transacciones, obteniendo un 28,20% de errores
> globales (2.841 errores). El comportamiento de la aplicación fue estable durante los tres
> primeros pasos del flujo (Auth, Get Booking y Post Create Booking), los cuales registraron
> 0% de errores y tiempos de respuesta adecuados para una carga de 10 usuarios concurrentes.
>
> Sin embargo, a partir de las operaciones que interactúan con el identificador de la reserva
> (Get_Booking_Id, Put_Update_Booking y Delete_Booking_Id) se presentó una degradación
> funcional significativa, evidenciada por porcentajes de error de 41,26%, 56,77% y 71,42%,
> respectivamente. Estos resultados indican que la aplicación logra crear las reservas
> correctamente, pero presenta problemas al consultarlas, actualizarlas o eliminarlas
> posteriormente.

Qué tiene que lo hace bueno: narra el flujo de negocio, agrupa lo que se comporta igual,
explica qué significa funcionalmente ("crea bien pero falla al consultar"), y no usa ni una
palabra de jerga.

Se conservan las reglas ya vigentes: cifras exactas, ratios, formato español
(8.600 · 0,27%), cierre con impacto al usuario, sin markdown, sin palabras prohibidas.

---

## 5. Tiempo de generación

Con una transacción seleccionada el informe tardó ~7 minutos, y eso es demasiado.

Reducciones ya identificadas:

| Cambio | Llamadas de IA que ahorra |
|---|---|
| Retirar Throughput Over Time del producto | 1 por informe |
| Quitar conclusiones y recomendaciones por transacción | 2 por transacción |

Con eso, una transacción adicional pasa de 8 a 6 llamadas, y el informe general de 12 a 11.

**Pendiente de decidir por Fredy** si además se quiere reducir más (paralelizar las llamadas
de IA fue descartado en su momento por riesgo; se puede reconsiderar con estos números).

---

## 6. Salidas

Todo lo anterior aplica igual en las cuatro salidas:

| Salida | Estado |
|---|---|
| Pantalla (reporte individual) | debe cumplir la especificación |
| PDF individual | idem |
| HTML individual | idem |
| Informe integrado (PDF y HTML) | idem, con cada ejecución mostrando lo suyo |

---

## 7. Convenciones de trabajo

| Tema | Regla |
|---|---|
| Repositorio real | `github` (IACygnus/Kinetix). **Es el único destino de push** |
| Azure (`azure`) | No recibe commits. Push bloqueado deliberadamente |
| Carpeta de reportes | `docs/reporte_claude_code/` — **única**, no se crean otras |
| Numeración | Desde `01`, consecutiva, con hash de commit y fecha en la primera línea |
| Validación | Claude Code prueba todos los cambios; Fredy valida al final del ciclo completo |

---

## 8. Lo que falta decidir (Fredy)

| # | Decisión |
|---|---|
| D1 | Control de gráfica: ¿valor por defecto "Ambos", "Promedio" o "Máximo"? |
| D2 | ¿Se reconsidera paralelizar las llamadas de IA para bajar el tiempo? |
| D3 | El informe por transacción, ¿empieza en página nueva en el PDF? (recomendación: sí) |
