b10de07 · 2026-09-17

# HF-4 + ETAPA 5 — para Fredy

---

## 1. Qué se hizo

**HF-4.** El bloque «Análisis por Transacción Crítica» salió del producto. Era
el que casi siempre decía *«Esta transacción se marcó como crítica pero no se
generó su análisis individual»*: leía una tabla que quedó en solo lectura hace
varios sprints. Ya no está en el PDF, ni en el HTML, ni en el integrado. **En
pantalla nunca estuvo.** Las filas de la base no se tocaron.

De paso, la tabla de cada bloque por transacción en PDF y HTML dejó de llamarse
«Métricas de la Transacción» y se llama igual que la del informe general,
**«Reporte Resumen por Transacción»**, con las mismas 14 columnas.

**El panel de selección** de «Nuevo Reporte» quedó como pide el §2 de la
especificación:

- **Columnas**: Transacción · Muestras · Promedio · **TPS** · Errores. Fuera
  `p90` y `Max`. El TPS **es el mismo** que verás luego en la tabla resumen del
  informe: no se recalcula, se trae.
- **Cada fila se despliega** y muestra sus propios criterios de aceptación
  —concurrencia, tiempo de respuesta y disponibilidad—, editables. Puedes tener
  varias abiertas a la vez.
- **Sin valores propios**, cada campo muestra el global en gris y la fila se
  evalúa con los criterios generales. Con valores propios, la fila se marca y el
  botón **«Usar globales»** la devuelve.
- **La marca «crítica» se recalcula al instante** al editar, con la misma regla
  con la que el informe decide el veredicto de cada transacción.
- **Desapareció** el bloque desplegable «Criterios por Transacción».
- El texto bajo el nombre dejó de ser jerga: donde decía
  `no apto por criterios (p90 175ms, 64.79% error)` ahora dice
  **`no cumple: 1 de cada 10 usuarios espera más de 462 ms (el límite son 300 ms)`**.

---

## 2. Evidencia

| Prueba | Resultado |
|---|---|
| El bloque retirado no aparece en **ninguna** de las cuatro salidas, sobre dos informes distintos | **24 / 24** y **24 / 24** |
| El panel en pantalla: columnas, TPS, desplegar, editar, «Usar globales» | **24 / 24** |
| La misma regla de criticidad da lo mismo en el navegador y en el servidor | **25 / 25** en cada lado |
| Una generación real con criterios propios | **8 / 8**, 22 llamadas, todas correctas |
| Las cuatro salidas siguen pasando (once pasos) | **PASAN**, en los dos informes |
| Compilación del frontend y pruebas del backend | 0 errores · 492 pruebas |

Dos cosas que conviene saber:

- **El TPS del panel y el del informe son la misma cifra**, comprobado
  transacción a transacción sobre las seis de la prueba.
- **Los criterios propios de una fila llegan de verdad al informe.** En la
  corrida de validación, `1. Auth` lleva un límite propio de 300 ms: su informe
  la da **NO APTO**. Con el límite global de 2.000 ms sería **APTO**. La
  diferencia la hace el criterio que se escribió en el panel.

**Una duplicación que hay que saber que existe**: la regla de criticidad vive
ahora en el servidor y en el navegador, porque editar un criterio no puede
resubir el archivo entero. Están atadas por un juego de casos que corren los
dos: si alguien cambia una y no la otra, la prueba falla. La fuente de verdad
sigue siendo el servidor.

---

## 3. El guion de prueba

**Cinco pasos.** **Sin rebuild**: recarga con **Ctrl + Shift + R**.

**1. El bloque retirado.**
Historial → `E3-estilo-pruebakinetix` → exporta **HTML** y **PDF**. Busca
«Transacción Crítica»: **no está**. Después del informe general van
directamente los bloques por transacción, y la tabla de cada uno se llama
**«Reporte Resumen por Transacción»**, igual que la del general.

**2. Las columnas del panel.**
Nuevo Reporte → sube un JTL. La tabla trae **Transacción · Muestras · Promedio ·
TPS · Errores**. **No hay p90 ni Max.** Si quieres, abre luego el informe de ese
mismo JTL y compara el TPS con el de la tabla resumen: es el mismo.

**3. Desplegar y editar.**
Pulsa el chevron de una fila. Salen sus tres criterios con el global en gris.
Escribe un tiempo de respuesta que la haga cumplir: **la marca «crítica»
desaparece al instante** y el texto de debajo cambia, sin volver a subir nada.
Pulsa **«Usar globales»**: vuelve a como estaba.

*Para verlo con el tiempo y no con los errores*: baja primero el **Tiempo de
Respuesta global** a 100 ms. Así `1. Auth` (que no tiene errores) se marca como
crítica por tiempo, y podrás devolverla con su criterio propio.

**4. El bloque que ya no está.**
En esa misma pantalla, **no existe** el desplegable «Criterios por Transacción»
ni su «aplicar el mismo criterio a todas».

**5. Los criterios llegan al informe.**
Genera con un criterio propio en una transacción y los globales en otra. Abre el
informe y baja a la tabla de veredictos por transacción: **la que tiene criterio
propio se evalúa con él**. Ya hay una corrida hecha así, `E5-panel`, por si
prefieres mirarla en vez de generar otra.

---

## 4. Lo que hace falta de ti

**El guion de arriba.** Tu validación visual es el único criterio de éxito.

Y dos cosas anotadas, por si quieres decidir:

- `transaction_analyses_html`, la función que pintaba el bloque retirado, quedó
  **sin usar**. No se borró porque son 46 líneas en un archivo protegido y la
  autorización era solo para retirar el bloque. Si quieres, se retira entera.
- Los títulos de gráfica en pantalla siguen **sin tilde** («Response Times por
  Transaccion»). Están fuera de esta autorización; se arreglan cuando se toquen
  esas pantallas.

**Estado: Etapa 5 implementada, pendiente validación de Fredy.**
