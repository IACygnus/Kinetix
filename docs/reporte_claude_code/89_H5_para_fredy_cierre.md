25b2897 · 2026-09-18

# ETAPA H5 — para Fredy

---

## Qué se hizo

**El informe de horas**, en HTML y en PDF. Y es **uno solo**: los dos son el mismo
documento con las mismas cifras; cambia el papel, no el contenido.

**1. Diez secciones, en este orden.** Resumen con seis indicadores · ocupación por
persona · facturable frente a no facturable · cobertura por cliente · en qué se
fue el tiempo · consumido frente a estimado con su estado · mapa del mes ·días
sin registrar · horas día a día · detalle de registros.

**2. Usted elige qué entra.** Filtros de personas, fechas, cliente, proyecto y
solo facturables; y **una casilla por sección** para quitar lo que no quiera. Lo
que quita desaparece del documento de verdad, no solo de la pantalla.

**3. La vista previa es el documento.** No es una maqueta parecida: es el mismo
archivo que se descarga, enseñado dentro de la página. En modo PDF trae el número
de páginas y botones para pasarlas.

**4. El PDF gira la hoja donde hace falta.** Va en vertical, y **solo las páginas
de «Horas día a día» salen en horizontal**, para que el mes entero quepa de
corrido. Un selector permite forzarlo todo vertical o todo horizontal. El detalle
de registros no entra al PDF salvo que marque su casilla: trescientas filas en
papel no se leen.

**5. El HTML funciona solo, sin internet.** Se guarda, se envía por correo y se
abre en cualquier parte. Dentro lleva los botones de Equipo y de cada persona,
los filtros de cliente y proyecto, la casilla de solo facturables, la búsqueda en
el detalle, las tablas que se ordenan al pulsar su cabecera, **Descargar CSV** e
**Imprimir**.

**6. El CSV es para Excel.** Solo el detalle de registros del filtro aplicado,
con encabezados y con la marca que hace que Excel en español abra las tildes bien
a la primera.

**7. Los archivos se llaman como deben:**
`informe-horas-2026-09-equipo.pdf`, en minúsculas y sin tildes.

---

## Evidencia

- **154 comprobaciones automáticas** propias de la etapa, todas pasan. **0
  llamadas a la IA**.
- **Las cifras cuadran, y eso se comprueba una a una**: cada sección suma lo mismo
  que el resumen, y el total coincide con lo que dicen la Consulta y el
  Calendario. Una cifra, una fuente.
- **La orientación del PDF está medida página a página**, no supuesta: vertical,
  vertical, vertical, HORIZONTAL, vertical.
- **Tiempos con 312 registros: HTML 0,03 s y PDF 1,10 s**, frente a los 5 y 15
  segundos que nos habíamos puesto de tope.
- El HTML descargado se abrió **sin servidor** y sus botones filtran.
- **El resto de Kinetix no se movió**: la suite de la Etapa 2 pasa en las cuatro
  salidas, y H1, H2, H2b y H3 siguen verdes.
- No se tocó ningún archivo protegido, ninguna dependencia nueva y ninguna
  columna de la base.

---

## Guion para validar

Recargue con **Ctrl + Shift + R**. No hace falta rebuild.

**1. Generar.** Horas → **Informes**. Arranca en el mes en curso y con todo el
equipo. Verá la vista previa del documento.

**2. Revisar la previa.** Baje por el documento: están las diez secciones, con el
resumen arriba y el detalle al final.

**3. Quitar y poner secciones.** Desmarque **Mapa del mes**: desaparece del
documento. Vuelva a marcarla: vuelve. Pruebe con otras.

**4. Filtrar.** Marque una o dos personas, o un cliente, y vea cómo cambia la
previa. Marque **Solo facturables** y fíjese en el total.

**5. Descargar el HTML.** Ábralo desde su carpeta de descargas —sin conexión, si
quiere— y use sus botones: Equipo, cada persona, los filtros, la búsqueda y el
orden por cabecera. Pulse **Descargar CSV** desde dentro del propio informe.

**6. El PDF.** Cambie a modo **PDF**: verá el número de páginas y podrá pasarlas.
Descárguelo y compruebe que **las páginas de «Horas día a día» están en
horizontal** y el resto en vertical. Cambie el selector a «Todo vertical» y vea
la diferencia.

**7. El CSV en Excel.** Descárguelo y ábralo: las tildes tienen que verse bien
sin tocar nada.

**8. Que el análisis sigue igual.** Abra un informe desde Historial Reporte y
expórtelo en PDF.

---

## Dos cosas que conviene que sepa

**Falta el logo, y el informe sale igual.** `backend/app/assets/logo-sqa.png` no
existe todavía, así que la cabecera lleva el nombre en texto. En cuanto deje el
archivo ahí, el informe lo tomará solo —se lee en cada generación—, sin reiniciar
nada. Lo decidimos así a propósito para que la falta de un archivo no bloqueara
la etapa.

**Un detalle del mapa en papel.** En pantalla, el mapa del mes enseña las horas
de cada día. En el PDF **enseña solo el color**, con su leyenda: con 31 columnas
en una hoja vertical, meter la cifra obligaba a bajar de 8 puntos y por debajo de
eso no se lee. Las horas exactas de cada día están en «Horas día a día», que es
justo la sección que gira la hoja para que quepan.

---

**Estado: Etapa H5 implementada, pendiente validación de Fredy.**
