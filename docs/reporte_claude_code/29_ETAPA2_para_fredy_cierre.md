6052cfe · 2026-09-16

# ETAPA 2 — para Fredy

Estado: **implementada, pendiente de tu validación.** Rama `backup-trabajo-local`, todo
empujado a `github`. Presupuesto de IA gastado: **30 de 50**.

---

## 1. Qué se hizo

**El informe por transacción ya es el informe general, filtrado.** Antes era otro documento:
otras gráficas, otros títulos, otros colores, con sus propias conclusiones. Ahora cada
transacción se pinta con el mismo código que el informe general — en pantalla, en el PDF, en
el HTML y en el integrado. Si mañana cambias una gráfica del general, cambia también en las
transacciones, porque es la misma.

**Cada transacción tiene su tabla resumen**, la misma del informe general con su fila, y su
análisis debajo.

**Se fue «Throughput Over Time»** del producto entero: la gráfica y su análisis. El número de
throughput (req/s) del KPI y de la tabla sigue donde estaba — se retiró la gráfica, no la
métrica.

**Las conclusiones van una sola vez, al final**, sobre toda la prueba. Cada transacción tenía
las suyas y se repetían. Y el orden es el que pediste: general → transacciones → conclusiones.

**Desapareció la palabra «mini-informe»**, hasta en los comentarios que viajan dentro del HTML
que se descarga. Cada bloque se titula con el nombre exacto de la transacción y nada más.

**El informe tarda 2 minutos y 21 segundos**, medido de punta a punta. Antes, casi 6.
La mitad del recorte es de esta etapa (28 llamadas a la IA en vez de 35); la otra mitad, del
`reasoning_effort` en **bajo**, que ya habías aprobado.

**La página ya no se queda sorda mientras genera.** El parseo del JTL salió del hilo que
atiende las peticiones: durante los 141 segundos de generación, el servidor respondió siempre
por debajo de 11 milisegundos.

---

## 2. Evidencia verificada

Todo esto está comprobado con Playwright y con llamadas reales, sobre datos reales, no sobre
ejemplos de juguete. Se vuelve a correr entero con un comando
(`verificar_etapa2.py`, diez pasos):

| Qué se comprobó | Resultado |
|---|---|
| La pantalla carga entera | **26 gráficas** (11 generales + 5 × 3 transacciones) |
| La tabla de cada transacción | una fila, sin TOTAL, **celda a celda igual** a la fila de esa transacción en la tabla general |
| Los tres canales de texto | editar en el general, en una transacción o en el integrado guarda **cada uno en el suyo** y no toca a los otros dos; al recargar, el texto sigue |
| PDF | 16 páginas, cada transacción abre página, sin throughput, conclusiones al final |
| HTML | se abre en un navegador: **22 gráficas pintadas, cero errores** de consola |
| Integrado | PDF y HTML correctos; las conclusiones individuales se recortan y **los bloques por transacción sobreviven** |
| Corrida real `E2-validacion` | **28 llamadas, todas correctas, todas en `low`**; ninguna de throughput ni de conclusiones por transacción |
| Tiempo | T2−T0 **141,0 s** (antes 354-357 s) · media por llamada **4,9 s** (antes 10,1) |
| El texto no se acortó | el texto visible por llamada baja solo un **7 %** (244 → 226 tokens) |

Los refactores de los cuatro archivos protegidos se hicieron en dos pasos y con la
equivalencia demostrada antes de cambiar nada: pantalla **0,000 % de píxeles**, PDF con `diff`
**vacío**, HTML idéntico salvo un comentario que cambia de sitio.

**Antes de desplegar en el servidor** hay que ejecutar `docs/sql/etapa2_reasoning_effort.sql`.
Sin esa columna, todos los informes saldrían con texto de relleno **y sin avisar**.

---

## 3. Guion de prueba

1. **Configuración de IA** (menú *Administración → Configuracion IA*). Junto al modelo aparece
   **«Esfuerzo de razonamiento»**, en **Bajo (low)**. Cámbialo a **Medio (medium)**, *Guardar
   Configuracion*; vuelve a **Bajo (low)**, *Guardar Configuracion*. Pulsa **Probar Conexion**:
   tiene que responder OK.
2. **El informe nuevo** (*Análisis → Historial Reporte* → **E2-validacion**). Comprueba, en
   este orden: el informe general **sin «Throughput Over Time»** → tres bloques titulados
   **solo** con el nombre de cada transacción, cada uno con **su tabla resumen de una fila**,
   su análisis y **5 gráficas con su análisis** (sin «Active Threads») → **conclusiones y
   recomendaciones una sola vez, al final**. En ninguna parte debe aparecer «mini-informe».
3. **Calidad con `low`.** Abre **E1.3-baseline-2** en otra pestaña y compara sus análisis del
   informe general con los de **E2-validacion**: fíjate en si dicen **menos cosas** o **menos
   precisas**, no en cómo suenan — la jerga se corrige en la Etapa 3. Si `low` se lee más
   pobre, súbelo a **medium** en el paso 1 y vuelve a generar: cada informe costaría unos 40
   segundos más.
4. **Que lo editado se guarde.** Cambia un análisis del informe general y otro dentro de una
   transacción. Recarga la página: los dos tienen que seguir ahí, cada uno en su sitio.
5. **PDF** (*Exportar PDF* en E2-validacion): cada transacción empieza en página nueva y las
   conclusiones están al final.
6. **HTML** (*Exportar HTML*): misma estructura, y las gráficas de cada bloque responden a sus
   botones (*Mostrar todas* / *Ocultar todas*).
7. **Un informe viejo** (*Historial Reporte* → **E1.3-baseline-2**): se ve con la estructura
   nueva y **sin conclusiones por transacción**, aunque en la base siguen guardadas.
8. **Integrado** (*Análisis → Historial Integrado* → **E2-validacion + E1.3-baseline-2**):
   exporta PDF y HTML y comprueba la misma estructura. Edita una sección, recarga: persiste, y
   el informe individual de esa ejecución **no cambia**.
9. **Que la página no se bloquee.** *Análisis → Nuevo Reporte*, sube un JTL con una sola
   transacción crítica y, mientras genera, navega por la aplicación en otra pestaña: tiene que
   responder al instante.

**Si algo de esto falla, dímelo con el paso y lo que viste** — no lo des por bueno.
