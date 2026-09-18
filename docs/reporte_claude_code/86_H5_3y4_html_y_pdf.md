bc0f952 · 2026-09-18

# ETAPA H5.3 y H5.4 — El HTML y el PDF

**0 llamadas a la IA.**

---

## 1. Un generador, dos ramas

| Archivo | Qué es | Líneas |
|---|---|---|
| `backend/app/services/horas/informe.py` | **nuevo** — el documento, en sus dos ramas | 718 |
| `backend/app/api/v1/endpoints/time_informe.py` | `+/html`, `+/pdf`, `+/csv` | +100 |

**Las diez secciones se arman una sola vez**, en `_secciones()`. Lo que cambia
entre HTML y PDF es la envoltura —los estilos y, en el HTML, los controles—,
nunca el contenido. Es H-D50 escrito en código: si cada salida montara sus tablas
por su cuenta, en tres semanas dirían cosas distintas. Es exactamente lo que le
pasó al informe de análisis y lo que costó la Etapa 2 entera arreglar.

**Generador propio** (H-D51): no se tocó `report_generator.py`, que está
protegido. Lo que sí se respetan son sus reglas, y están comprobadas una a una en
el punto 4.

---

## 2. El HTML (H5.3)

Autocontenido de verdad: **ni una referencia a la red** en todo el documento —se
comprueba con una expresión regular sobre el HTML entregado—, con los estilos y
el JavaScript embebidos. Se guarda, se envía por correo y se abre sin internet.

Lo que lleva dentro (H-D55): botones de **Equipo** y de cada persona, filtros de
cliente y proyecto, casilla de solo facturables, búsqueda en el detalle, tablas
ordenables por cabecera, **Descargar CSV** e **Imprimir**.

### La única aritmética del documento, y por qué está acotada

Los seis indicadores se rehacen al filtrar **sumando las filas visibles del
detalle**, que es el mismo dato crudo que sumó el backend. Lo que depende de la
jornada o de las estimaciones —secciones 2, 6, 7 y 8— **se filtra por fila y no
se recalcula**, porque esos datos no viajan en el detalle y inventarlos sería
justo lo que este módulo lleva cinco etapas evitando.

Y el documento lo dice: al filtrar aparece un aviso que explica que las secciones
de jornada y estimación enseñan solo las filas que coinciden.

---

## 3. El PDF (H5.4)

`GET /time/informe/pdf`, con WeasyPrint y las dos `@page` que H5.1 dejó
comprobadas. Por defecto **sin el detalle de registros** (H-D58).

```
    orientaciones: ['vertical', 'vertical', 'vertical', 'HORIZONTAL', 'vertical']
PASA  | hay paginas horizontales (la seccion 9)
PASA  | y verticales (el resto)
PASA  | el informe empieza en vertical
PASA  | y la hoja vuelve a vertical al salir de la seccion 9
PASA  | forzar vertical: {'vertical'}
PASA  | forzar horizontal: {'HORIZONTAL'}
```

**Cómo se midió, que importa:** WeasyPrint guarda los objetos del PDF
comprimidos, así que `/MediaBox` **no se puede leer** del archivo ya escrito —el
primer intento devolvió cero páginas y cero orientaciones, y esa es la razón—.
Se mide sobre el **mismo HTML de impresión que usa el endpoint**, generado por la
propia función del producto y renderizado en la prueba para poder preguntarle el
tamaño de cada página. Es el método con el que se comprobó H-D56 en H5.1. Del PDF
que devuelve el endpoint se comprueba aparte que es un PDF de verdad, con su
nombre y su tiempo.

### Una decisión que el propio requisito obligó a tomar

«Ningún texto por debajo de 8 pt» chocaba con mi primera hoja de estilos, que
usaba 7 y 7,5 pt en las casillas de los días. Subir todo a 8 pt deja la sección 9
bien —va en horizontal y hay sitio—, pero **el mapa de la sección 7 no**: 31
columnas en una hoja vertical no admiten «8,5» a 8 pt.

Así que **en papel el mapa habla por color y no lleva cifras**. La leyenda dice
qué significa cada uno y las horas exactas están en la sección 9. En pantalla sí
lleva los números, donde sobra sitio.

---

## 4. Validación — 58 comprobaciones, todas pasan

```
--- autocontenido (H-D55) ---
PASA  | ni una referencia a la red ([])
PASA  | estilos y JavaScript embebidos
PASA  | las diez secciones, una a una

=== 2. El HTML, abierto de verdad ===
PASA  | sin errores de consola ([])
PASA  | estan las 41 filas del periodo (41)
PASA  | filtra el detalle (2 de 41) · y el resumen se rehace (4 h)
PASA  | y avisa de que la vista esta filtrada
PASA  | la seccion 2 deja una sola fila (1)
PASA  | ordenar por cabecera deja la columna de menor a mayor ([4, 57.5, 60, 61.5])
PASA  | y al pulsar otra vez, de mayor a menor ([61.5, 60, 57.5, 4])
PASA  | el CSV se descarga como «informe-horas-2026-09-equipo.csv»
PASA  | con BOM, para que Excel en espanol lo abra bien
PASA  | y solo con las filas visibles (27 de 27)

--- ningun texto por debajo de 8 pt ---
PASA  | el menor tamano del PDF es 8.0 pt

--- reglas de impresion (regla 11) ---
PASA  | la rama de impresion no usa flex ni grid
PASA  | ni rem
PASA  | y ninguna fila se parte entre paginas
PASA  | la cabecera se repite en cada pagina
```

**Dos aserciones que empezaron siendo mentira y se arreglaron:** la del número de
filas comparaba contra mi contador y no contra lo que dice el informe —la base
tenía registros de antes—, y la del orden era **vacua**: comparaba la primera
fila antes y después de ordenar y pasaba con `ok(True, …)`. Ahora lee la columna
entera y exige que quede monótona, en los dos sentidos.

---

## 5. El logo y los tiempos

**El logo sigue sin existir** (H-D54). El informe sale con el nombre en texto, no
se rompe, y la prueba lo comprueba. En cuanto el archivo esté en
`backend/app/assets/logo-sqa.png` se tomará solo.

**Tiempos con 39 registros: HTML 0,01 s y PDF 0,78 s**, muy por debajo de los 5 y
15 s de H-D62. La medición que pide la etapa —**unos 300 registros**— va en H5.6,
que es donde el prompt la sitúa.

---

## 6. Lo que viene

H5.5 monta `/horas/informes` con sus cuatro pestañas, el panel de filtros y de
secciones, y la vista previa que enseña **este** documento, no una maqueta aparte.
