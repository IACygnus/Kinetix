Commit base `367d975` · 2 de octubre de 2026 · Reporte 154 — resumen de la auditoría de interfaz (153)

# Auditoría de interfaz: el resumen

**36 pantallas** (41 rutas con sus variantes), en 6 módulos más el login. Revisé
cada una en 7 tamaños, de la tableta en vertical (834 px) al monitor 2K (2560 px).
No cambié nada del producto. **Llamadas a la IA que generan texto: 0.** El
navegador abortó 223 peticiones, ninguna de IA. Detalle en el reporte 153 y en su
JSON; las 465 capturas van en el zip, **fuera de git**.

## Los 10 hallazgos más graves

1. **En el Historial de reportes no se llega a las acciones** a 1366 ni a 1920 px.
   La tabla mide 1.830 px dentro de una caja que corta lo que sobra, así que Ver,
   Exportar y Eliminar quedan fuera. Además pinta las 88 filas sin paginar.
2. **El contenido cortado no se ve.** `<main>` oculta lo que sobra a lo ancho, y
   eso pasa en 20 de las 41 rutas a 834 px (tablas, KPI del informe, el Script Designer).
3. **El menú lateral mide 288 px fijos y no se pliega.** A 834 px se lleva el 35 %
   de la pantalla. Además, el menú va en 24 px, un tamaño más grande que casi todos
   los títulos.
4. **Cuatro identidades visuales**, con cuatro colores de botón principal: oro,
   navy, índigo y azul. El Analista IA y los Diseñadores IA no usan el oro en
   ningún sitio, y Perfil y Configuración IA son páginas oscuras dentro de un marco
   claro.
5. **El título «Mi Perfil» es invisible**: blanco sobre gris claro, contraste 1,1:1.
6. **Contraste**: fallan 723 de 5.734 textos medidos. El gris 400 (`#9ca3af`,
   2,5:1) está en casi todas las pantallas. **El oro de marca no sirve como color
   de texto sobre blanco** (2,03:1).
7. **No hay biblioteca de componentes.** Hay 477 botones en unas 15 familias (401
   sin `type`), 9 colores de foco, 6 estilos de cabecera de tabla, 37 modales con
   6 fondos distintos y 38 avisos del navegador (`alert`/`confirm`).
8. **La letra no es la que se pidió.** El código pide Inter, pero no se carga de
   ningún sitio: en Windows sale Segoe UI y en otro equipo saldrá otra. Los ejes de
   las gráficas del informe van a 8 px.
9. **Al fallar, varias pantallas enseñan ceros como si fueran datos** («Total
   Reportes 0», «0 usuarios registrados»). Solo el informe ofrece Reintentar, y no
   hay indicadores de carga en la mitad.
10. **El informe guarda al salir de un cuadro de texto aunque no haya cambios**: 100
    `PUT /analysis` en el recorrido, todos abortados. Además, dos ítems del menú
    llevan al visor de vuelta al Dashboard sin decirle por qué (Nuevo Reporte e
    Historial Integrado).

**Más que hay que saber:**
- **Idioma:** Ejecución está en inglés, y partes del Script Designer también.
  Muchos textos van sin tildes («Configuracion», «Contrasena»).
- **Monitores grandes:** a 2560 px trece pantallas se estiran sin límite, y el chat
  del Analista llega a 183 caracteres por línea.
- **Exportados:** el informe de análisis usa tres paletas a la vez. Una misma
  gráfica cambia de color entre el PDF y el HTML, y el PDF tiene tablas en 6,5-7,5
  pt.

## Qué no se pudo auditar

- **Los roles analista y visor en el navegador.** No hay usuarios de desarrollo
  para ellos (los tres analistas son personas reales) y no los creé. Lo que ve
  cada rol lo saqué del código.
- **Una sesión de monitoreo con datos.** No hay ninguna, y abrirla escribe en la
  base.
- **El Editor IA con un diseño abierto, y Grafana con datos.** Los dos necesitan un
  `POST`, que estaba bloqueado.
- **Los estados vacíos reales.** Habría que borrar datos para verlos, así que los
  describo desde el código.
- **Cuántas llamadas de `/ai-config/estado` y `/models/live` llegaron de verdad a
  OpenAI.** Consultan el modelo sin generar texto y el backend las guarda en caché,
  así que no lo medí.
- **Una última pasada de títulos y columnas.** El séptimo login chocó con el límite
  de 5 cada 15 minutos y no reintenté. **Durante esos minutos tampoco habrías
  podido entrar desde este equipo.** El inventario por pantalla salió del código.

## Decisiones que tomé

| Decisión | Por qué |
|---|---|
| Seguí con 134 archivos sin versionar en `docs/reports/repo/` | Ningún archivo versionado tenía cambios, y la regla 19 dice que esos no se tocan ni se señalan |
| Usé Playwright de **Python** en lugar del de npm | En el equipo no hay Node. Es la misma herramienta, instalada fuera del repo, y Chromium se descargó sin problemas |
| Leí las versiones dentro de `jmeter_frontend` | El `node_modules` del anfitrión está vacío |
| Abrí la sesión de monitoreo con un id inexistente | Su GET escribe en la base. Con un id que no existe responde 404 y no toca nada |
| Simulé «cargando» reteniendo las respuestas y «error» con un 500 falso, en el propio navegador | Así se ven esos estados sin tocar datos ni el backend |
| Abrí los modales a mano (34 controles) | La heurística automática no los encontraba (por los botones sin `type`), y elegirlos a mano evita pulsar algo que confirme una acción |
| Aborté también las exportaciones al abrir el diálogo de exportar | Exportar no es abrir un modal, y genera un PDF pesado |
| Numeré 153 el técnico, el JSON y el zip, y 154 este resumen | El JSON y el zip son anexos del 153. Este es otro documento |
