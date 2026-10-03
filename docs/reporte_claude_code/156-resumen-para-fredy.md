Commit base `0641e57` · 3 de octubre de 2026 · Reporte 156 — Resumen para Fredy: rediseño, Etapa 0

# Etapa 0 del rediseño: lo que hay que mirar

## Qué quedó hecho

- **La base del sistema de diseño**, sacada del mockup Índigo: colores claro y
  oscuro, las tres tipografías (Plus Jakarta Sans, JetBrains Mono y Space
  Grotesk, ya **cargadas de verdad**, sin internet) y 25 componentes listos para
  las siguientes etapas (botones, campos, tabla, pestañas, modal, confirmación,
  avisos…). Todo documentado en `docs/DESIGN_SYSTEM.md`.
- **El armazón nuevo**: cabecera con los módulos, riel de sección a la izquierda,
  buscador de pantallas (**Ctrl + K**), pausa de animaciones y **tema claro/oscuro**,
  que se recuerda. Bajo 1100 px, menú desplegable y sub-pestañas. **Mismos ítems y
  rutas que hoy para los tres roles.**
- **El inicio de sesión del mockup**, con la prueba de carga animada y la misma
  autenticación de siempre.
- Las demás pantallas **no cambian todavía**: se ven dentro del armazón nuevo,
  siempre en claro.
- **Tu pantalla del 5173 no ha cambiado**: todo está en la rama
  `rediseno-ui-e0`, sin subir, y se probó compilado aparte. Llamadas a la IA: 0.

## Qué mirar en la validación visual

Para verlo hace falta el paso de abajo («Qué necesito de ti»). Después, con
**Ctrl + Shift + R**:

1. **El login** a pantalla completa: titular, cifras que cambian, tarjeta a la
   derecha. Pulsa **«Pausar animación»**: todo debe quedar quieto. Entra con tu
   usuario como siempre.
2. **La cabecera**: los módulos arriba, el actual resaltado en índigo y, a la
   izquierda, las pantallas del módulo. Entra en Análisis → Historial Reporte y
   comprueba que lo marca.
3. **El botón de la luna** (cabecera, a la derecha): cambia la cabecera y el riel
   a oscuro. **El contenido de las pantallas sigue claro a propósito** hasta que
   se migre cada una. Recarga: debe seguir en oscuro.
4. **Ctrl + K**: escribe «regis» y pulsa Intro; debe llevarte a Registro de horas.
5. **Ventana estrecha** (menos de 1100 px, o la tableta): aparece el botón de menú
   a la izquierda y las pantallas pasan a una fila de pestañas encima del
   contenido.
6. **Tu nombre** en la cabecera: abre «Mi perfil» y «Cerrar sesión».
7. **Dos o tres pantallas que uses a diario** (Horas, Historial, Observabilidad):
   que funcionen igual que antes. Ahora el contenido tiene un ancho máximo y
   queda centrado en pantallas grandes.
8. Con la tecla **Tab** nada más abrir una pantalla: lo primero que aparece es
   «Saltar al contenido».

Capturas de todo, en los 7 anchos, en claro y oscuro y junto al mockup:
`docs/reporte_claude_code/155-rediseno-etapa-0-capturas.zip` (fuera de git).

## Decisiones que tomé (detalle en el reporte 155 §3)

- El tema **claro** es el de partida; el oscuro se activa con la luna y se recuerda.
- Las pantallas sin migrar se quedan en claro aunque el tema sea oscuro, para que
  nada quede ilegible mientras tanto.
- El botón de pausa del login es la **misma** pausa que la de la cabecera.
- El menú conserva las etiquetas de hoy, con tildes en «Administración» y
  «Configuración IA»; «Monitoreo en vivo» no se acorta a «En vivo».
- Con la pausa puesta las animaciones se **quitan**, no se congelan: congeladas
  dejaban invisibles los diálogos. Lo encontró la validación y está corregido.

## Lo que necesito de ti

1. **Que lo veas.** El paso es el avance rápido de `rediseno-ui` a
   `rediseno-ui-e0` en tu copia: como el frontend corre con `vite dev`, **no hace
   falta reconstruir**; basta recargar. Dime cuándo tienes la aplicación lista
   para que cambie, o hazlo tú con
   `git merge --ff-only rediseno-ui-e0` en `C:\proyectos\Kinetix`.
2. **Tu aprobación** para el `git push github rediseno-ui`, que solo hago después.
3. ~~Cabecera en una línea~~: **hecho** tras tu revisión (reporte 155 §10). Entre
   1100 y 1499 px queda solo el avatar.
4. **Para la Etapa 1** (Perfil, Usuarios, Clientes, Asignaciones, Configuración IA):
   que confirmes que, una vez validado el armazón, borro `Sidebar.tsx` y
   `Footer.tsx`. Y, si quieres que pruebe las pantallas con los roles de analista
   y visor en el navegador, un usuario de prueba de cada uno (hoy no hay ninguno).
