485e8b0 · 2026-09-17

# ETAPA 7 — para Fredy

---

## Qué se hizo

**1. El informe integrado ya muestra los bloques por transacción.** Hasta ahora, abrir un
integrado en pantalla enseñaba solo el informe general de cada ejecución. Ahora enseña lo
mismo que Historial Reporte: la tabla resumen filtrada, los seis análisis y las cinco
gráficas de cada transacción, en el orden de siempre.

**2. Y esto es lo que de verdad había que arreglar:** el PDF y el HTML del integrado **ya
traían esos bloques desde la Etapa 2**. La pantalla no. Es decir, hasta hoy usted revisaba
un documento en pantalla y aprobaba un exportado con secciones que no había visto. Medido
sobre el integrado de E3-estilo: la pantalla mostraba **21 gráficas**, el HTML exportado
traía **3 bloques por transacción** que en pantalla no aparecían por ningún lado. Ahora la
pantalla muestra **36 gráficas** y los dos canales dicen lo mismo.

**3. Editar dentro del integrado no toca la ejecución original.** Si corrige el análisis de
una transacción dentro de un informe integrado, ese texto se guarda **en el integrado**. La
ejecución conserva el suyo, y en Historial Reporte se sigue viendo el original. Es la misma
regla que ya funcionaba para las cajas del informe general.

**4. Los exportados del integrado usan el texto corregido.** El PDF y el HTML salen con los
bloques completos y con lo que usted escribió en el integrado.

**5. Los integrados que ya existen no se tocan.** Los 28 informes integrados guardados se
abren con sus textos de siempre. No se migró ni se borró nada.

**6. Un documento para el despliegue.** `59_handoff_despliegue_analisis.md` reúne todo lo
necesario para preparar el despliegue de **solo el módulo de análisis** en un chat nuevo,
sin arrastrar el historial de las siete etapas: qué módulos son de análisis y cuáles no,
cuatro opciones técnicas con sus riesgos, el checklist de despliegue corregido y cinco
preguntas que necesitan su respuesta.

---

## Evidencia

- **16 comprobaciones automáticas** de punta a punta, todas pasan, **0 llamadas a la IA**.
  La prueba es reversible: deja el texto como estaba.
- Los bloques por transacción en el integrado **coinciden exactamente** con los del informe
  individual: 3 y 3.
- Al editar: el texto queda en `integrated_reports`, **`transaction_chart_analyses` no
  cambia**, al recargar el integrado sigue ahí, y en Historial Reporte esa transacción
  conserva su texto original.
- El HTML exportado abre en un navegador con **cero errores de consola**.
- **Nada se rompió:** la suite completa de la Etapa 2 pasa en las cuatro salidas, y siguen
  pasando las pruebas de las Etapas 5b y 6 (criterios, panel, capas, selector de
  exportación). 492 tests del backend igual que antes.
- Se tocó **un solo archivo protegido**, `Dashboard.tsx`, con **16 líneas** de las 40
  autorizadas — y 8 de ellas son el comentario que explica el cambio.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. Ver los bloques.** Historial Integrado → abra **"E3-estilo — integrado"**. La primera
ejecución (`E3-estilo-pruebakinetix`) muestra su informe general **y debajo sus tres
transacciones**, cada una con su tabla, sus análisis y sus cinco gráficas — igual que en
Historial Reporte. La segunda ejecución no tiene transacciones analizadas y no pinta ningún
hueco.

**2. Editar sin contaminar.** Dentro del integrado, cambie el texto de un análisis de una
transacción. Espere unos segundos y **recargue**: el texto sigue ahí. Ahora abra esa misma
ejecución en **Historial Reporte**: esa transacción conserva **su texto original**. Lo que
escribió vive solo en el integrado.

**3. Exportar.** Desde el integrado, genere el **PDF** y el **HTML**. Los dos traen los
bloques por transacción completos, y con el texto que acaba de escribir.

**4. Uno nuevo.** Cree un integrado nuevo agregando una ejecución que tenga transacciones
analizadas — por ejemplo `E5b-criterios`. Aparece completa desde el primer momento, sin
tener que editar nada.

---

## Para después de validar

El documento de despliegue (`59_handoff_despliegue_analisis.md`) le hace **cinco preguntas**
que no puedo responder yo:

1. El alcance exacto de "solo análisis" — en concreto si entran **Monitoreo Real-Time** y la
   **Configuración de IA**.
2. Dónde respaldar en git: ¿solo `github/backup-trabajo-local`, o hay que llevar algo a
   `main`, poner un tag, o preparar el envío parcial a `azure`?
3. Si el despliegue arranca con la **base actual** o con una **limpia**.
4. La ventana de despliegue.
5. Cuántas personas van a entrar — de eso depende si **HF-3** (el límite de cinco entradas
   cada quince minutos para toda la plataforma) hay que resolverlo antes.

Dos cosas que conviene que sepa de ese documento:

- **Los puertos están bien.** Su comprobación desde internet es la que manda: el NSG los
  cierra. Lo que sigue pendiente es que el compose no los cierra por sí mismo — deuda, no
  urgencia.
- **Cuidado con las imágenes de monitoreo y evidencias.** No tienen volumen propio; hoy
  sobreviven por un detalle del compose. Si se arregla el compose sin añadir antes un
  volumen para `media`, **empezarían a perderse en silencio**. Están los dos puntos juntos
  en §4.5 para que no se toque uno sin el otro.

---

**Estado: Etapa 7 implementada, pendiente validación de Fredy.**
