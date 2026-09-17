9404b07 · 2026-09-16

# ETAPA 3 — para Fredy

> Sustituye al reporte 36. Cambia tres cosas: no hace falta rebuild, el aviso
> ámbar ya aparece también en el informe general, y se añade lo que pasó con
> «prueba final 2».

---

## 1. Qué se hizo

Los textos que escribe la IA dejaron de sonar a herramienta y pasaron a sonar a
informe. Lo que pedía el §4 de la especificación:

- **Fuera la jerga.** Ni «tier excelente», ni «alta variabilidad», ni
  «dispersión», ni «latencia crítica». Y no solo se le prohibió al modelo: se
  quitó también de **los datos que se le entregan**, que era de donde la copiaba.
- **Los percentiles se leen en personas.** «1 de cada 10 usuarios espera más de
  3,5 segundos (P90: 3.515 ms)» en vez de «P90 de 3.515 ms». La frase se calcula
  antes de enviarla; el modelo solo la copia.
- **Las cifras van en español.** 8.600 · 0,27% · 1,1 segundos · 125 ms · 3,9
  veces. Antes convivían «3,1 veces» y «3.9x» en el mismo informe.
- **Ninguna sección dice si el sistema está listo para producción.** Eso quedó
  donde tiene que estar: en las conclusiones y las recomendaciones del final.
- **Los análisis narran el flujo de negocio** y agrupan lo que se comporta
  igual, en la línea de la referencia aprobada.

Y, para no tener que confiar en que salió bien: un **aviso ámbar** encima de la
caja de análisis cuando un texto todavía trae jerga, percentiles sueltos o
cifras a la inglesa. Se calcula al leer, no se guarda, y desaparece solo cuando
el texto se corrige. **Ya aparece en las cuatro vistas** —informe general,
bloques por transacción, integrado, y monitoreo y evidencias— y **no sale en el
PDF ni en el HTML**.

---

## 2. Evidencia

**Mismo JTL, mismos criterios, mismas tres transacciones, mismo modelo.** Lo
único que cambió son los prompts:

| | `E2-validacion` (Etapa 2) | `E3-estilo-pruebakinetix` (Etapa 3) |
|---|---|---|
| Cifras en formato inglés | 105 | **0** |
| Jerga (tier, variabilidad, dispersión) | 9 | **0** |
| Percentiles sin traducir | 9 | **0** |
| Veredicto dentro de una sección | 1 | **0** |
| **TOTAL** | **124** | **0** |

**38 secciones de texto nuevas, cero avisos.**

Otras tres cosas medidas:

- **Las cifras salen de los datos de la prueba.** Comprobado número a número:
  **98,6 %** trazables en una corrida y **97,8 %** en la otra. Las diez
  restantes están explicadas una a una y **ninguna es inventada**: son cuentas
  que el modelo hizo con lo que tenía (por ejemplo, 100 − 28,20 = 71,80 % de
  disponibilidad).
- **El modelo no copia el ejemplo aprobado.** El ejemplo de la especificación es
  el mismo dataset de pruebakinetix, así que se corrió una segunda prueba con
  otro cliente (avianca): **cero apariciones** de sus 18 cifras y nombres.
- **Se envía un 35 % menos de texto al modelo** y la caché del proveedor pasó del
  7,8 % al 36,9 %, porque el bloque de estilo viaja una sola vez por llamada en
  vez de dos.

**Lo que empeoró, dicho sin adornos: el informe tarda 18 segundos más** (141 s →
159 s). El prompt es más corto, pero el modelo escribe un 16 % más de texto
visible y tarda más en escribirlo. Sigue muy por debajo de los 354 s de la línea
base de la Etapa 1.

### 2.1 Datos que borré, y no pude recuperar

En una prueba de la etapa llamé a un endpoint que guarda, y **sobrescribí los
dos análisis globales —monitoreo y evidencias— de la ejecución «prueba final 2»
(cliente popular, prueba de estrés de 2021, cargada el 1 de abril)**.

- **Lo que se perdió:** solo esos dos textos globales.
- **Lo que está intacto y verificado:** sus **7 análisis por imagen** (5 de
  monitoreo, 2 de evidencias), las imágenes, todos los análisis del informe y
  los dos informes integrados que usan esa ejecución.
- **Recuperación:** se buscó en los informes integrados, en los exportados del
  disco, en el resto de la base y hasta en las páginas internas de PostgreSQL
  (que no ha pasado nunca por `VACUUM`). **No se pudo recuperar** y la evidencia
  no permite afirmar ni negar que esos dos textos llegaran a generarse alguna
  vez.
- **Cómo queda:** la ejecución está **exactamente como si nunca se hubiera
  generado el análisis global** — sin caja, con su botón «Generar Analisis
  Global» y con sus siete análisis por imagen a la vista. No hay ni un resto del
  texto falso.
- **Para regenerarlos**, si los quieres: Performance → Monitoreo → seleccionar
  «prueba final 2 — popular» → **Generar Analisis Global**; y lo mismo en
  Performance → Evidencias. **Dos llamadas.** Saldrán con el estilo nuevo.

El detalle completo está en el reporte 38. La prueba que causó el borrado ya
está corregida: ahora desactiva el guardado y deshace lo que toca.

---

## 3. El guion de prueba

**Siete pasos.** **No hace falta rebuild**: en local el backend recarga solo
(`--reload`) y el frontend corre en modo desarrollo. Basta **Ctrl + Shift + R**
en el navegador.

**1. El antes y el después, lado a lado.**
Historial → abre **`E3-estilo-pruebakinetix`** y, en otra pestaña,
**`E2-validacion`**. Es el mismo JTL. Compara los análisis:

- En el nuevo **no aparece** «tier», ni «variabilidad», ni «dispersión», ni un
  percentil suelto.
- Los percentiles se leen «1 de cada 10 usuarios espera más de…».
- Las cifras van en español: `8.600` · `0,27%` · `1,1 segundos` · `125 ms`.

*Detalle conocido:* los textos de esta corrida dicen «espera **mas** de», sin
tilde. Es un fallo de una letra en el código que arma la frase, **ya
corregido**; la próxima generación la lleva. No se regeneró por no gastar 40
llamadas en una tilde.

**2. Ninguna sección dictamina.**
Recorre el resumen y las seis gráficas del informe nuevo. **Ninguna** dice si el
sistema está listo para producción. Baja al final: **ahí sí**, las conclusiones
abren con «APTO CON RESERVAS» o «NO APTO» y explican qué criterio se incumple.

**3. Se lee como un informe, no como una lista.**
El resumen debería contarte el recorrido en orden —autenticar, consultar, crear,
y ahí se rompe— agrupando lo que se comporta igual, en vez de recitar las seis
transacciones una a una.

**4. Otro cliente, otras cifras.**
Abre **`E3-estilo-avianca`**. Sus textos hablan de `auth`, `crear`, `Paso 2` y
`Paso 4`, de sus 81.714 peticiones y su 0,06 % de error. **Nada del ejemplo de
reservas.**

**5. El aviso ámbar, en todo el informe.**
Vuelve a **`E2-validacion`** (textos antiguos). Verás **13 franjas ámbar
«Revisar estilo: …»**:

- **10 en el informe general** — el resumen, los errores, las seis gráficas, las
  conclusiones y las recomendaciones.
- **3 en los bloques por transacción.**

Edita una, quita la palabra que señala, espera a que diga «Guardado», recarga
con **Ctrl + Shift + R**: **el aviso desapareció**. Vuelve a poner el texto como
estaba y el aviso regresa.

**6. Los exportados, limpios.**
Genera **PDF** y **HTML** de `E3-estilo-pruebakinetix`, y el **integrado**
`E3-estilo — integrado`. Comprueba dos cosas: **no hay ninguna franja ámbar** en
los documentos, y los textos son los nuevos.

**7. La trazabilidad.**
Lee el §4 del reporte 34. Cada cifra de cada análisis está comprobada contra los
datos que se le enviaron al modelo, y las diez que no cuadran están explicadas
con nombre y apellido.

---

## 4. Lo que hace falta de ti

1. **El guion de arriba.** Tu validación visual es el único criterio de éxito.
2. **Decidir** si quieres que regenere los dos análisis globales de «prueba
   final 2» (§2.1). Son dos llamadas y las puedes lanzar tú desde la pantalla.

Antes de desplegar al servidor sigue pendiente lo de siempre (reporte 35 §7):
ejecutar `docs/sql/etapa2_reasoning_effort.sql` en la base de producción, y allí
**sí** hace falta rebuild.

**Estado: Etapa 3 implementada, pendiente validación de Fredy.**
