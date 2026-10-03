Commit base `0641e57` · 3 de octubre de 2026 · Reporte 155 — Rediseño de la interfaz, Etapa 0: sistema de diseño, armazón e inicio de sesión

# Rediseño, Etapa 0

> **Qué es.** La base del rediseño aprobado en `docs/diseno/kinetix-mockup.html`
> (variante Índigo): tokens claro/oscuro, tres tipografías autoalojadas, la
> biblioteca de 25 componentes, el armazón nuevo (cabecera, riel de sección,
> menú desplegable, buscador) y el inicio de sesión animado. **Ninguna pantalla
> adopta todavía la biblioteca**, salvo el armazón y el login.
>
> **No se tocó**: el backend, los exportadores, ningún archivo protegido, ni
> `package.json`. **No hubo rebuild de Docker** ni reinicio de contenedores: el
> trabajo vive en la rama `rediseno-ui-e0`, en un worktree fuera de `./frontend`,
> y se compiló en `/tmp/e0` dentro de `jmeter_frontend` sin tocar `/app`. La
> pantalla de Fredy (5173) **no ha cambiado**.
>
> **Llamadas a la IA que generan texto: 0.** Peticiones abortadas: 0. Inicios de
> sesión: 2 (§6.3).

---

## 1. Paso previo

| | Resultado |
|---|---|
| a. Rama, árbol, mockup | `rediseno-ui`, árbol limpio (solo `docs/reports/repo/`, que la regla 19 no deja tocar). El mockup no estaba en `docs/diseno/`; Fredy lo puso allí (idéntico al de `Downloads`: 1.016.493 bytes, mismas cinco marcas) y se versionó en `rediseno-ui` (`0641e57`, solo ese archivo). La rama de la etapa sale de ahí |
| b. Auditoría 153 | Leída. Lo que pesa en esta etapa: menú fijo de 288 px sin cortes, `overflow-x-hidden` en `<main>`, filtrado por rol en `Sidebar.tsx:323-326`, dos ítems engañosos para el visor (§1d), inventario del login (§9) |
| c. Ver sin reconstruir | `jmeter_frontend` corre `vite dev` sobre `./frontend` montado: editar allí cambia la pantalla de Fredy al instante (regla 31). Método aprobado por Fredy: worktree + build aislado + servidor estático con vuelta a `index.html` + `--host-resolver-rules` (§6.1) |
| d. Alcance | Presentado y aprobado. Real frente a lo estimado en §2 |

## 2. Archivos

### 2.1 Creados

| Archivo | Líneas | Estimado |
|---|---|---|
| `frontend/src/styles/tokens.css` | 183 | 160 |
| `frontend/src/styles/fonts.css` | 33 | 30 |
| `frontend/src/styles/ui.css` (no previsto: §3, D4) | 230 | — |
| `frontend/src/assets/fonts/{plus-jakarta-sans,jetbrains-mono,space-grotesk}-var.woff2` | 27 + 40 + 22 KB | binarios |
| `frontend/src/assets/logo-sqa.png` | 24 KB, 237 × 120 | binario |
| `frontend/src/components/ui/` (25 componentes + `Spinner`, `cx`, `campo`, `index`) | 1.906 | ~1.900 |
| — de ellos `LoadFx.tsx` | 471 | 220 (§3, D11) |
| `frontend/src/context/PreferenciasContext.tsx` | 88 | 80 |
| `frontend/src/components/layout/navegacion.ts` | 199 | 150 |
| `frontend/src/components/layout/{Cabecera,RielSeccion,MenuMovil,BuscadorPantallas,MenuUsuario,Marca}.tsx` | 545 | ~550 |
| `tools/check_tokens.py` | 147 | 120 |
| `docs/DESIGN_SYSTEM.md` | 336 | 300 |
| `docs/diseno/PLAN-REDISENO.md` | 149 | 120 |
| Este reporte y el 156 | — | — |

### 2.2 Modificados (con respaldo `.bak_rediseno-e0_20261003-1443` al lado, ignorado por git)

| Archivo | Antes → después | Qué |
|---|---|---|
| `frontend/tailwind.config.js` | 23 → 193 | **Solo se añade**: colores, radios, sombras, familias, tamaños, cortes, animaciones y `dark:`. `sqa` y la paleta por defecto siguen |
| `frontend/src/index.css` | 91 → 64 | Importa tokens, fuentes y `ui.css`; **fuera Inter**, las partículas del login viejo y `.sqa-animated-header` (sin uso); el fondo y el texto del `body` salen de tokens; foco visible global |
| `frontend/src/components/layout/Layout.tsx` | 46 → 128 | El armazón nuevo |
| `frontend/src/components/auth/Login.tsx` | 152 → 212 | El inicio de sesión del mockup, con la misma autenticación |
| `frontend/src/main.tsx` | 10 → 18 | `PreferenciasProvider` y `ToastProvider` |
| `frontend/index.html` | 13 → 23 | Tema y pausa aplicados antes del primer pintado |
| `CLAUDE.md` | +9 | Referencia al plan y al sistema de diseño (§1) |

**Sin importar, conservados** hasta la validación (decisión de Fredy):
`layout/Sidebar.tsx` y `layout/Footer.tsx`.

## 3. Decisiones

| # | Decisión | Por qué |
|---|---|---|
| D1 | Mockup versionado en `rediseno-ui` antes de crear `rediseno-ui-e0` | Si solo estuviera en la rama de la etapa, el avance rápido final chocaría con la copia sin versionar de Fredy |
| D2 | Tokens **generados por script** desde los bloques del mockup, con el hex original como comentario en cada línea | 124 valores: transcribirlos a mano es donde se cuelan los errores |
| D3 | Cinco tokens con otro nombre en Tailwind: `bg`→`canvas`, `text`→`ink`, `text-muted`→`ink-muted`, `border`→`line`, `border-strong`→`line-strong` | Con los del mockup saldrían `bg-bg`, `text-text`, `border-border` |
| D4 | Un `ui.css` además de Tailwind | Las tarjetas de la tabla (consulta de **contenedor**), el dibujo del interruptor, las «hormigas» de la zona de arrastre y la regla global de pausa no se escriben en Tailwind 3.4 sin valores arbitrarios, que la regla 4 prohíbe. Todo sale de tokens |
| D5 | Los valores fluidos del mockup (`clamp(...)`) y las medidas que no están en la escala (42 px, 232 px, 98rem) entran como **claves del tema** (`min-h-control`, `px-login-x`, `text-titular`…) | Así no son valores arbitrarios y quedan con nombre |
| D6 | `rounded-chico/control/panel/pill` en vez de `rounded-s/m/l` | `rounded-s` ya existe en Tailwind (radio lógico de inicio) |
| D7 | **Tema claro por defecto**, recordado en `localStorage` | Es el del mockup y el de las pantallas sin migrar |
| D8 | El contenido va dentro de **`.tema-claro`**; el armazón sigue el tema | Las pantallas sin migrar están pintadas con la paleta clara de Tailwind: en oscuro serían ilegibles. `dark:` está definido para no aplicar dentro de `.tema-claro` |
| D9 | Tamaño de letra fijo en 16 px | El selector «Letra 14/16/18» es de la barra del prototipo |
| D10 | El botón «Pausar animación» del login **es la misma pausa** que la de la cabecera | Una sola preferencia, recordada; el mockup tenía dos estados sueltos |
| D11 | `LoadFx` es un solo componente con las dos escenas del mockup (`login` y `hero`) | Comparten el bucle, la pausa y la lectura de tokens. Por eso pesa 471 líneas frente a las 220 estimadas: es el código de las dos escenas portado tal cual, sin dependencias |
| D12 | Con pausa o movimiento reducido el lienzo **no corre**: pinta una imagen fija de un tramo de prueba simulado (17 s en el login, en plena carga) | Es lo que hace el mockup con movimiento reducido, y la imagen quieta sigue contando la historia |
| D13 | Iconos de `lucide-react` (ya instalado) en vez de las rutas SVG propias del mockup | Sin dependencias nuevas y con los mismos iconos que ya usa la app; grosor 1,8 como el mockup |
| D14 | Cabecera: módulos como **enlaces** al primer ítem visible; riel y sub-pestañas como **enlaces de navegación** (`aria-current="page"`), no `role="tab"` | Cambian de ruta; el patrón de pestañas de WAI-ARIA es para paneles en la misma página. `Tabs` (con `role="tab"`) queda para eso |
| D15 | El módulo y la pantalla actuales los decide `ubicar()`: la ruta más larga que case, con `tambien` para rutas con id (`/performance/report/<id>` es «Reporte»; `/ai-script-designer/editor/<id>`, «Editor IA») | Antes cada grupo se abría por prefijos sueltos en un `useEffect` |
| D16 | Al cambiar de pantalla, el foco va a `<main>` (sin mover el desplazamiento); en la primera carga, no | El lector de pantalla anuncia el contenido nuevo, como hace el mockup con el `h1`; las pantallas sin migrar no siempre tienen `h1` |
| D17 | Cuenta de usuario en un **diálogo** con «Mi perfil» y «Cerrar sesión» | Como el mockup (`ACT.user`); son las dos acciones del pie del menú viejo |
| D18 | Login: `<Navigate>` en lugar de `navigate()` durante el render, y todos los hooks antes del `return` | Mismo resultado; el viejo llamaba a `navigate` en pleno render. Regla 16 |
| D19 | Login: «Escribe tu usuario y tu contraseña.» en la página, en vez de la burbuja de `required` | Es el comportamiento del mockup; no hay petición si falta algo |
| D20 | Mensajes del login **con tildes** («Credenciales inválidas. Verifica tu usuario y contraseña.»), mismo texto | Regla 10. El `detail` del servidor y el aviso de sesión expirada (que viene de `AuthContext`) salen tal cual |
| D21 | Etiquetas del menú: las de hoy, con tildes en «Administración» y «Configuración IA». «Monitoreo en vivo» se queda así (el mockup dice «En vivo») | La regla es conservar los ítems exactos |
| D22 | **En pausa las animaciones se quitan** (`animation: none`), no se congelan | Encontrado al validar (§7.1): congeladas, las de entrada se quedaban en `opacity: 0` y el diálogo no se veía |
| D23 | Un botón **cargando** no se atenúa | Su texto («Guardando…») bajaba a 2,5:1. El deshabilitado sí se atenúa (WCAG exime los controles inactivos) |
| D24 | El botón de pausa del login lleva un fondo `lg-bg/70` | Sin él, a 834 px su texto quedaba en 4,36:1 sobre las partículas |
| D25 | Guardián en Python con alcance por etapa, exentos `tokens.css` y el menú viejo | `tokens.css` es la definición; `Sidebar`/`Footer` no son código migrado |

## 4. Criterios de aceptación

| Criterio | Resultado |
|---|---|
| `tsc` y `vite build` sin errores, dentro del contenedor | **Cumple.** `tsc` sin salida; `vite build` en 5,8 s (el aviso de tamaño del bloque de 1,6 MB ya existía) |
| `tools/check_tokens.py` reporta 0 valores prohibidos | **Cumple.** «43 archivos revisados · 0 valores prohibidos». Probado con un archivo sembrado: detecta los 12 casos (hex, `rgb()`, `bg-[#…]`, `text-[11px]`, `bg-indigo-600`, `text-gray-500`, `hover:bg-white`, `border-sqa-gold`, `[&_p]:`, `[overflow-wrap:anywhere]`…) y ningún falso positivo (`lista[0]`, `rgb(var(--x))`, `rgb(${r},…)`) |
| Cada rol ve los mismos ítems y rutas que hoy | **Cumple.** Los menús de `Sidebar.tsx` y `navegacion.ts` se leen como datos y se filtran con el mismo algoritmo: **iguales** para admin (28 ítems), analista (24) y visor (14), en orden y ruta. Para el admin, además, en el navegador: los 7 módulos y el riel de cada uno coinciden. Los dos ítems engañosos del visor siguen, como pidió Fredy |
| 834-2560 px: el documento no desborda y el armazón no corta nada (login + 3 pantallas) | **Cumple.** 7 anchos × 2 temas × (login + Dashboard, Historial de reportes, Registro de horas): `scrollWidth − clientWidth = 0` en las 56 vistas, 0 elementos del armazón fuera de la ventana, 0 textos recortados, 0 objetivos < 24 px |
| Textos del armazón y del login cumplen AA en claro y oscuro | **Cumple.** Medido sobre los **píxeles reales** de detrás de cada texto (§5.2): peor caso 4,95:1 (umbral 4,5). Tokens: 77 de 78 pares cumplen; el que no, no se usa así (§5.1) |
| «Pausar animación» o `prefers-reduced-motion` dejan el lienzo quieto | **Cumple.** Con el botón: el lienzo cambiaba entre dos lecturas y deja de cambiar (4 de 4 casos). Con movimiento reducido emulado: quieto y sin botón de pausa. Con la pausa ya recordada al entrar: quieto y todo el texto visible (opacidad 1) |
| Una pantalla sin migrar funciona igual dentro del armazón | **Cumple** en lo que se puede ver sin escribir: las **29 rutas** del menú del admin más Perfil abren dentro del armazón, con contenido, **0 errores de JavaScript** y sin desborde del documento. No se pulsó nada que escriba (regla 7) |

## 5. Contraste

### 5.1 Tokens (cálculo)

Tabla completa, 39 pares × 2 temas, en `docs/DESIGN_SYSTEM.md` §3. Resumen:

| | Pares | Cumplen | Mínimo |
|---|---|---|---|
| Claro | 39 | 38 | 3,74:1 (`border-strong` / `surface`, umbral 3:1) |
| Oscuro | 39 | 39 | 4,57:1 (ídem) |

El que no llega: `lg-muted` sobre `lg-2` en claro, **4,22:1**. Es el lema del
login **si cayera** sobre el color más claro del degradado. No cae: el velo
radial lo oscurece. Lo dice la medida de §5.2.

### 5.2 Medido en la página

Método: con la animación en pausa, se captura la página con todos los textos en
transparente y se compara el color calculado de cada texto con **el peor 5 % de
los píxeles de su caja**. Así cuentan el degradado, el velo y las partículas.

| Superficie | Tema | Ancho | Textos | Peor | Fallos |
|---|---|---|---|---|---|
| Login | claro | 834 · 1366 | 19 · 19 | 6,10 · 6,27 | 0 |
| Login | oscuro | 834 · 1366 | 19 · 19 | 6,91 · 6,91 | 0 |
| Cabecera + riel | claro | 834 · 1366 | 11 · 22 | 6,10 · 4,95 | 0 |
| Cabecera + riel | oscuro | 834 · 1366 | 11 · 22 | 6,91 · 6,89 | 0 |
| Menú desplegable | claro · oscuro | 834 | 18 · 18 | 6,29 · 6,91 | 0 |
| «Ir a una pantalla» | claro · oscuro | 1366 | 4 · 4 | 8,35 · 9,06 | 0 |
| Galería de la biblioteca | claro · oscuro | 1366 · 834 | 110-139 | — | 0 reales (*) |

(*) La única marca de la galería es «Fecha» a 1,0:1: el `<thead>` de la tabla en
modo tarjeta, que está **oculto a la vista** (1 px recortado) y solo lo lee el
lector de pantalla. Falso positivo de la medida.

## 6. Validación

### 6.1 Cómo

- **Compilación aislada**: el `frontend` del worktree se copia a `/tmp/e0` en
  `jmeter_frontend` (con `node_modules` enlazado a `/app/node_modules`), y allí
  `tsc` + `vite build`. `VITE_API_BASE_URL` es la del contenedor
  (`http://localhost:8001/api/v1`): el build habla con el 8001 real.
- **Vista previa**: el `dist` se copia al anfitrión y lo sirve un servidor
  estático con vuelta a `index.html` en el 5190; Chromium se lanza con
  `--host-resolver-rules=MAP localhost:5173 127.0.0.1:5190`. La página cree estar
  en el 5173: CORS y cookies funcionan. El 5173 de Fredy no recibió nada.
- **Guiones** (fuera del repositorio, en `C:\proyectos\kinetix-audit-tools`):
  `etapa0.py` (login, armazón, menú por rol, pantallas sin migrar, mockup) y
  `etapa0_galeria.py` (la biblioteca en una galería **temporal**, compilada aparte
  en `/tmp/e0`, que no entra al repositorio). Se pueden volver a correr; las
  variables están en su cabecera.
- **Interceptor de la regla 7** en todo el contexto: toda petición que no sea GET
  se aborta y se anota, salvo el POST de `/auth/login`.

### 6.2 Cifras

| | |
|---|---|
| **Llamadas a la IA que generan texto** | **0** |
| Peticiones abortadas | **0**: ninguna pantalla intentó escribir (no se pulsó nada; el `PUT` al perder el foco del informe que vio la auditoría no se dispara sin tabular dentro) |
| GET que tocan un endpoint de IA | 1, **de lectura**: `GET /executions/<id>/transaction-report` al abrir «Reporte» (lee las secciones ya guardadas; generar es un POST) |
| Errores de JavaScript | 0 |
| Capturas | 129 (login 14, armazón 42, menú desplegable 2, buscador 2, cuenta 2, pantallas sin migrar 29, mockup 28, galería 7, estados 3) |
| Datos escritos en la base | Ninguno. Una consulta de **solo lectura** a `users` comprobó, sin gastar cupo de login, que la contraseña del entorno del backend sigue siendo la del admin |

### 6.3 Inicios de sesión

**Dos**, los dos correctos: el de la primera corrida, y otro en la última,
cuarenta minutos después, porque la sesión guardada había caducado. Las corridas
intermedias la reutilizaron. Nunca más de uno en 15 minutos.

### 6.4 Comprobaciones de comportamiento (todas pasan)

- Ctrl + K abre «Ir a una pantalla» con `role="dialog"` y el foco en el campo;
  «regis» deja solo «Registro · Horas» e Intro lleva a `/horas/registro`.
- El botón de tema pone `data-theme="dark"`, lo guarda y **sobrevive a recargar**.
- La pausa de la cabecera pone `data-movimiento="pausado"`, lo guarda y el botón
  pasa a «Reanudar animaciones».
- La primera parada de Tab es «Saltar al contenido», visible; Intro lleva el foco
  a `<main id="contenido">`.
- Menú desplegable (834): muestra los 7 módulos con Análisis desplegado; Escape lo
  cierra y devuelve el foco al botón de menú.
- Login con los campos vacíos: aviso en la página, `aria-invalid` y foco en el
  usuario, **sin enviar nada**.
- Galería: flechas en las pestañas (`aria-selected` y panel), foco atrapado en el
  modal y de vuelta al botón al cerrar, foco en «Cancelar» al confirmar, toast de
  error que **no se va solo** (el de éxito sí, a los 4,5 s), columna de acciones
  pegada al borde y tabla en tarjetas en contenedor angosto.

## 7. Lo que encontró la validación (corregido)

1. **Con la pausa puesta, los diálogos no aparecían.** La regla de pausa congelaba
   las animaciones (`animation-play-state: paused`) y la de entrada se quedaba en
   su primer fotograma, `opacity: 0`: se veía el velo y nada más. Lo mismo dejaba
   invisible el texto del login a quien volviera con la pausa recordada. Ahora en
   pausa **no hay animación** (D22), y el guion lo comprueba en los dos sitios.
2. **La tabla ancha desbordaba el documento a 834 px** (311 px): su ancho mínimo
   iba en línea y el modo tarjeta no podía anularlo. Ahora es una variable CSS.
3. **En modo tarjeta, las acciones salían en columna**: la celda heredaba el
   `width: 1%` de la columna fija.
4. **El botón secundario y el de contorno del Hero no pintaban su borde**: un
   `border-transparent` común ganaba por orden en el CSS generado. El color del
   borde lo pone ahora solo la variante.
5. **Botón cargando a 2,5:1** (D23) y **botón de pausa del login a 4,36:1** a
   834 px (D24).
6. Dos fallos de los guiones, no del producto: el script de arranque volvía a
   imponer el tema en cada recarga, y el clic en un módulo chocaba con el modal
   que abre el Script Designer al entrar. Corregidos en el guion.

## 8. Lo que no se pudo verificar

| Qué | Por qué |
|---|---|
| Analista y visor **en el navegador** | No hay usuarios de prueba con esos roles; los analistas son personas reales. Cubierto comparando los dos menús como datos, con el mismo filtro (§4) |
| La app servida por el `vite dev` de Fredy | A propósito (regla 31): se validó el **build**. Lo que puede variar con HMR es poco (mismo código, mismo CSS), pero no se ha visto |
| Que las pantallas sin migrar **hagan** lo mismo que antes | Solo se abrieron, sin pulsar nada que escriba (regla 7). El armazón no toca su código: solo su contenedor (más ancho máximo, sin `overflow-x-hidden`, dentro de `.tema-claro`) |
| `prefers-reduced-motion` **del sistema** | Emulado por Playwright, no con la opción de Windows |
| Lectores de pantalla reales (NVDA, Narrador) | Se comprobaron roles, nombres y foco por código y en el DOM; no se escuchó |
| Firefox y Safari | Solo Chromium. El layout usa consultas de contenedor y `:has()` (en el guion), soportados por los tres desde 2023 |
| Gestos táctiles en tableta | Solo ratón y teclado emulados |

## 9. Pendiente y deuda

- **Validación visual de Fredy** (único criterio de éxito, regla 9) y, con su
  visto bueno, el avance rápido de `rediseno-ui` a `rediseno-ui-e0` en su copia y
  `git push github rediseno-ui`. La rama `rediseno-ui-e0` **no se ha subido**.
- Tras la validación: borrar `Sidebar.tsx` y `Footer.tsx`.
- Los dos ítems del visor que lo devuelven al inicio («Nuevo Reporte»,
  «Historial Integrado»): deuda decidida por Fredy, anotada en `navegacion.ts`.
- Heredado y sin tocar: el aviso de sesión expirada sin tildes (`AuthContext`), el
  favicon `/vite.svg` que no existe, los modales de página con `z-50` encima de
  la cabecera, la tarjeta `sticky top-4` de Ejecución que ahora se mete bajo la
  cabecera fija (Etapa 5), y el título blanco de «Mi Perfil» sobre fondo claro
  (Etapa 1).
- Entre 1100 y 1366 px la cabecera del admin ocupa dos líneas (98 px). Igual que
  el mockup; si Fredy lo quiere en una, es una decisión de diseño (menos módulos
  a la vista o etiquetas más cortas).
- El retardo escalonado de entrada del texto del login (0,08 s entre líneas) no se
  portó: necesita un retardo por elemento que Tailwind no trae sin valores
  arbitrarios. Las líneas entran a la vez.
- `LoadFx` superó en más de un 50 % su estimación de líneas (471 frente a 220):
  avisado aquí; es el código de las dos escenas del mockup (D11).
