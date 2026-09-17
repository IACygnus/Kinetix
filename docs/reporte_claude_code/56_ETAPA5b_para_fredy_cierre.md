24102cd · 2026-09-17

# ETAPA 5b — para Fredy

---

## Qué se hizo

**1. Los criterios de cada transacción ahora se ven y se abren desde un botón.** La tabla
del panel tiene una última columna, **Criterios**, con un botón por fila que dice con qué
se está evaluando esa transacción: **"Globales"** en gris, o **"Propios"** en índigo si le
puso valores suyos. Ese botón es el que despliega sus tres campos. La flecha de la
izquierda desaparece. Todo lo demás sigue igual: el panel desplegable con la marca de agua
del global, el botón "Usar globales", varias filas abiertas a la vez y la criticidad
recalculándose al instante.

**2. La IA ya usa esos criterios.** Era el hueco de verdad: la tabla de veredictos sí
miraba el criterio propio de cada transacción, pero **la IA no lo veía**. Los seis análisis
de una transacción no recibían **ningún** criterio, y el informe general solo conocía el
global. Con un límite propio de 300 ms y un promedio de 422 ms, la tabla marcaba NO APTO
mientras el texto podía darla por buena contra los 2.000 ms generales.

Ahora:

- **En los análisis de una transacción** entra el límite que se le aplica, diciendo cuál
  es: *"límite propio de esta transacción"* o *"criterio general de la prueba"*.
- **En los análisis del informe general** entra la lista de las transacciones que tienen
  criterio propio, con sus valores, y la instrucción de no contradecir la tabla.

Y lo importante: **la regla que decide el umbral es una sola**. La función que calcula los
veredictos y la que se lo cuenta a la IA son ahora la misma, así que no pueden separarse.

**3. La especificación pasa a v1.3** con esto escrito en §2.2.

---

## Evidencia

La prueba real, `E5b-criterios`, con "1. Auth" a 300 ms propios y el resto a 2.000 ms.
Esto es lo que escribió la IA, literal:

> **En el bloque de la transacción:** "**Con límite de 300 ms**, 1 de cada 10 usuarios
> espera más de 462 ms (P90: 462 ms), por lo que la experiencia supera el tiempo esperado
> para el ingreso."

> **En el informe general:** "**Auth promedió 422 ms y quedó por encima de su límite propio
> de 300 ms**, lo que apunta a que el ingreso puede sentirse más lento desde el inicio del
> flujo."

Antes, ese mismo párrafo la habría dado por buena.

- **16 llamadas a la IA** de las 20 autorizadas, contadas en el contador de la aplicación
  (198 → 214). Todas con resultado correcto.
- **52 comprobaciones automáticas sin gastar ni una llamada**: 26 sobre los prompts, con un
  interceptor que cuenta y bloquea cualquier petición, y 26 sobre la pantalla real.
- **15 controles** sobre el informe generado: los seis textos hablan de los 300 ms, ninguno
  presenta los 2.000 ms como su límite, y de las 11 frases del informe general que nombran
  a Auth, **6 la juzgan contra sus 300 ms**.
- **El detector de estilo sigue en 0 avisos**, en el bloque por transacción y en el general.
- **Nada se rompió:** la suite completa de la Etapa 2 pasa en las cuatro salidas, la paridad
  de criticidad sigue 25/25, las pruebas de la Etapa 6 siguen pasando y los 492 tests del
  backend siguen igual.
- **Ningún archivo protegido** se tocó.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. El botón.** Nuevo Reporte → suba un JTL. La tabla tiene una última columna
**Criterios**, con un botón **"Globales"** gris en todas las filas. La flecha de la
izquierda ya no está.

**2. Poner un criterio propio.** Pulse el botón de una fila: se abren sus tres criterios,
con el valor global como marca de agua. Escriba un tiempo de respuesta propio — por ejemplo
300 — y mire dos cosas a la vez: **el botón pasa a "Propios" en índigo** y **la criticidad
de esa fila se recalcula al instante**, sin volver a subir el archivo. Pulse **"Usar
globales"** y todo vuelve a como estaba. Puede dejar varias filas abiertas a la vez.

**3. Lo que escribe la IA.** Abra el informe **`E5b-criterios`**, ya generado:

- En el bloque de **"1. Auth"**, los análisis hablan de **su límite de 300 ms** y dicen que
  lo supera. No mencionan los 2.000 ms como si fueran los suyos.
- En el **informe general**, el análisis de Response Times dice que Auth quedó **por encima
  de su límite propio de 300 ms** — lo mismo que dice la tabla de veredictos, que la marca
  NO APTO.

---

## Una cosa para que decida

Junto al nombre de la transacción sigue apareciendo el chip índigo **"criterios propios"**,
que ahora dice lo mismo que el botón nuevo:

```
1. Auth   crítica   criterios propios   …   [Propios ▸]
```

**No lo quité** porque no estaba en lo acordado. Si prefiere que el botón sea el único
indicador, es quitar una línea.

---

**Estado: Etapa 5b implementada, pendiente validación de Fredy.**
