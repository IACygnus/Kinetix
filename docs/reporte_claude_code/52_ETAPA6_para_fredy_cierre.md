3ba8fee · 2026-09-17

# ETAPA 6 — para Fredy

---

## Qué se hizo

**1. Las gráficas se pueden apagar por capa** (especificación §3). Response Times dibuja
dos líneas por transacción: el promedio en línea sólida y el máximo en punteada. Ahora
cada gráfica tiene un selector **Ambas · Promedio · Máximo** junto al título. Está en el
informe general y en cada bloque por transacción, y cada uno va por su cuenta: cambiar el
del general no mueve los de las transacciones.

**2. El tooltip ya no sale duplicado.** Antes listaba `Auth` y `Auth (max)` como si fueran
dos transacciones. Ahora es una línea por transacción, con el máximo dentro:

```
1. Auth                405 ms (máx. 414 ms)
2. Get Booking         200 ms (máx. 227 ms)
```

Con una sola capa activa muestra solo ese valor. Las transacciones apagadas en la leyenda
no aparecen. Las cifras van en formato español.

**3. Al exportar, el sistema pregunta qué incluir** (§6). Exportar PDF o Exportar HTML abre
un diálogo con dos opciones: **Solo informe general**, o **General y transacciones** con la
lista de las que tienen análisis, todas marcadas. Cancelar no exporta nada. El informe
integrado no cambia.

**4. Lo que se ve en pantalla es lo que se imprime.** Si deja una gráfica en "Máximo" y
exporta, el PDF la dibuja así y las demás con las dos capas. El HTML abre igual, y además
lleva los tres botones dentro: quien lo reciba puede cambiar las capas sin pedir otra
exportación.

**5. Los títulos llevan tilde** en pantalla, PDF, HTML e integrado: "Transacción",
"Análisis", "Códigos de Respuesta", "Duración", "Ejecución", "Métricas". Son 80 textos. Los
nombres de gráfica que la especificación fija en inglés ("Response Times", "Latency Over
Time") se conservan.

**6. Se retiró código muerto**: la función que pintaba el antiguo bloque "Análisis por
Transacción Crítica", sin usar desde el HF-4.

---

## Evidencia

- **89 comprobaciones automáticas** propias de esta etapa: **todas pasan**. Se cuentan los
  trazos reales del dibujo y se comparan los PNG del PDF byte a byte, no las clases de un
  botón.
- **La suite completa de la Etapa 2** (diez pasos, las cuatro salidas) pasa sobre las dos
  ejecuciones, `E3-estilo-pruebakinetix` y `E5-panel`.
- **El informe integrado sigue igual**: sus dos exportaciones responden 200 y conservan
  todo lo que la Etapa 2 dejó.
- **La edición y el autoguardado no se tocaron**: las diez comprobaciones del cableado
  siguen pasando.
- **Cero llamadas a la IA** en toda la etapa. El presupuesto era diez.
- Los cuatro archivos protegidos quedaron dentro de su presupuesto. Uno lo cruzó a mitad de
  camino y se corrigió sacando el JavaScript y el CSS fuera del archivo; está explicado en
  el reporte 49.

---

## Guion para validar

Abra `E3-estilo-pruebakinetix`. Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. Las capas en pantalla.** En *Response Times por Transacción* del informe general,
pulse **Máximo**: quedan solo las líneas punteadas. **Promedio**: solo las sólidas.
**Ambas**: las dos. Pase el cursor por la gráfica: el tooltip muestra **una línea por
transacción**, sin ninguna entrada "(max)" repetida. Baje a un bloque por transacción y
repítalo — su selector va por separado y el del general no se mueve.

**2. Exportar solo el general.** Pulse **Exportar PDF** → aparece el diálogo → elija **Solo
informe general** → Exportar. El PDF no trae ningún bloque por transacción, pero sí la
portada, la tabla resumen, las gráficas generales y las conclusiones.

**3. Exportar algunas transacciones.** Pulse **Exportar PDF** → **General y transacciones**
→ desmarque una → Exportar. Solo salen las marcadas. Antes de exportar, deje una gráfica en
**Máximo**: el PDF la imprime con esa capa y el resto con las dos.

**4. El HTML.** **Exportar HTML** y abra el archivo. Las gráficas abren con la selección que
tenía en pantalla y traen sus propios botones **Ambas · Promedio · Máximo**; al pulsarlos
las líneas cambian y el tooltip solo muestra lo que está visible.

**5. Las tildes.** Compruebe "Transacción", "Análisis", "Códigos de Respuesta" y "Duración"
en pantalla, en el PDF y en el HTML.

**6. El informe integrado.** Ábralo y expórtelo en PDF y HTML: tiene que salir igual que
antes. El diálogo de alcance no aparece ahí, a propósito (§6).

---

## Qué mirar con lupa

- Que el selector de capas **no aparezca** en Latency, Error Rate, Response Codes, TPS ni
  Active Threads: esas gráficas tienen una sola capa y no tendrían qué alternar.
- Que al cambiar de capa **no se mueva la escala del eje Y**: es intencional, para que la
  gráfica no salte bajo la vista.
- Que cancelar el diálogo **no descargue nada**.

---

## Después de validar

Queda un documento aparte, `53_checklist_despliegue.md`, con todo lo que hay que ejecutar o
revisar en el servidor antes de subir estas seis etapas. **No se ejecutó nada de eso**: es
solo la lista.

**Estado: Etapa 6 implementada, pendiente validación de Fredy. Plan de corrección
completo.**
