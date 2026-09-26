Commit `a9e9294` · 26 de septiembre de 2026

# R1, para Fredy — el guion de validación

El detalle técnico está en el reporte 121. Aquí solo lo que hay que mirar, en orden, con qué debe verse y qué sería un fallo.

**Antes de empezar:** Ctrl + Shift + R en el navegador. En desarrollo no hace falta reconstruir nada.

> **Un cambio que vas a notar (opción (a)):** en pantalla, la sección de carga o estrés **ya no muestra dentro** sus capturas ni sus evidencias. Entran **solo como sección propia**, con los botones «Monitor (n)» y «Evidencia (n)», igual que en el PDF y el HTML. Si un informe viejo no tenía esas secciones añadidas, al abrirlo ya no verás sus capturas: añádelas como sección.

---

## El guion

**1. El historial.**
Abre *Informes integrados → Historial*. Hay dos columnas nuevas: **Trabajo guardado** y **Contenido**.
- ✔ El del **12/08 10:43** dice «10 textos editados» y «consolidado corregido».
- ✔ Los del **25/09 12:35** y **13:14** dicen solo «consolidado corregido»: sin textos de sección, que es lo que se perdió ese día.
- ✔ En el filtro de estado, «Con ediciones guardadas» deja **10** informes.
- ✘ Fallo: un informe que sabes que editaste sale «Sin ediciones», o la columna no aparece.

**2. Crea un integrado nuevo** con una prueba de carga que tenga transacciones y capturas. Añade su «Reporte», su «Monitor» y su «Evidencia».

**3. Antes de generar, el selector.**
En la tarjeta del reporte pulsa «Incluye: todas las transacciones» y **desmarca una**. En la de monitoreo, **desmarca una captura**.
- ✔ Las tarjetas dicen «N de M transacciones» y «N de M capturas».

**4. Genera el informe.**
- ✔ La transacción desmarcada **no tiene bloque**, y la captura desmarcada **no aparece**.
- ✔ La barra de abajo a la derecha dice «Sin cambios pendientes» o «Guardado HH:MM».

**5. Edita y sal a lo bruto.**
Escribe una palabra al final del análisis del resumen general. Sin hacer clic fuera, **pulsa enseguida otro enlace del menú**.
- ✔ Mientras escribes, la barra dice **«Cambios sin guardar»** y el botón «Guardar cambios» se pone ámbar.
- ✘ Fallo: dice «Guardado» antes de que hayas salido.

**6. Vuelve** desde el historial.
- ✔ **Tu palabra está ahí.**
- ✔ La selección sigue igual en las tarjetas.
- ✔ No aparece ningún aviso amarillo de «cambios que no llegaron a guardarse».
- ✘ Fallo: la palabra no está. Es el fallo del 25/09.

**7. Lo mismo con F5.**
Escribe otra palabra en una **captura** y, con el cursor dentro, pulsa **F5**.
- ✔ Al recargar, la palabra está.

**8. Exporta PDF y HTML.**
- ✔ Las dos palabras están en los dos documentos.
- ✔ La transacción y la captura que desmarcaste no están.

**9. El consolidado.**
Genéralo. Es una llamada de IA de verdad.
- ✔ Las conclusiones **no mencionan la captura desmarcada**.
- ✔ No remiten a un informe de la transacción desmarcada. De ella solo puede haber lo que dice la tabla resumen general.

---

Si todo esto pasa, R1 está validada. Lo que queda abierto está en el reporte 121 §8: la deuda del guardado lento (§2.2), medida y sin arreglar.
