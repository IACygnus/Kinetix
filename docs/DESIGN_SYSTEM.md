# Sistema de diseño de Kinetix

> Referencia única del aspecto de la interfaz desde el rediseño (Etapa 0, octubre
> de 2026). **La especificación visual es el mockup aprobado**,
> `docs/diseno/kinetix-mockup.html`, en su variante **Índigo** (`data-dir="i"`).
> Este documento dice cómo está llevado al frontend real y cómo se usa. El plan
> de etapas y sus reglas están en `docs/diseno/PLAN-REDISENO.md`.
>
> **No aplica a los exportadores** (PDF, HTML, integrado) ni al informe de horas:
> esos tienen su propia referencia (`docs/ESPECIFICACION-informe.md`,
> `docs/diseno-informe-horas.md`).

---

## 1. Dónde vive cada cosa

| Pieza | Archivo |
|---|---|
| Tokens (claro y oscuro) | `frontend/src/styles/tokens.css`: **el único archivo del frontend con colores literales** |
| Tipografías autoalojadas | `frontend/src/styles/fonts.css` + `frontend/src/assets/fonts/*.woff2` |
| Lo que Tailwind no escribe sin valores arbitrarios | `frontend/src/styles/ui.css` (consultas de contenedor, interruptor, pausa global) |
| Tokens en Tailwind | `frontend/tailwind.config.js` → `theme.extend` (la paleta por defecto y `sqa` siguen ahí mientras queden pantallas sin migrar) |
| Tema y pausa | `frontend/src/context/PreferenciasContext.tsx` (+ el script de `index.html`, que los aplica antes del primer pintado) |
| Biblioteca base | `frontend/src/components/ui/`: un componente por archivo, exportados en `index.ts` |
| Armazón | `frontend/src/components/layout/`: `Layout`, `Cabecera`, `RielSeccion`, `MenuMovil`, `BuscadorPantallas`, `MenuUsuario`, `Marca`, `navegacion.ts` |
| Logo | `frontend/src/assets/logo-sqa.png` (el `<img id="logo-src">` del mockup, 237 × 120, con transparencia) |
| Guardián | `tools/check_tokens.py` |

## 2. Tokens

### 2.1 Cómo se usan

Cada color es una variable CSS con **canales RGB sueltos** (`--primary: 79 70 229`),
para que Tailwind pueda aplicar opacidad:

```js
// tailwind.config.js
primary: 'rgb(var(--primary) / <alpha-value>)'
```

```tsx
<div className="bg-primary text-on-primary" />      // sólido
<div className="bg-scrim/60" />                      // con opacidad
```

En CSS propio: `color: rgb(var(--text));`. En un `<canvas>`: leer el token con
`getComputedStyle` (ver `LoadFx.tsx::colorDe`). **Nunca un hex, un `rgb()` con
números, un valor arbitrario (`bg-[#…]`, `text-[11px]`) ni una clase de la paleta
de Tailwind (`bg-indigo-600`, `text-gray-500`, `bg-white`) en código migrado**: lo
comprueba `tools/check_tokens.py`.

Cinco nombres cambian respecto al mockup, para no producir `bg-bg` o `text-text`:
`--bg` → `canvas`, `--text` → `ink`, `--text-muted` → `ink-muted`, `--border` →
`line`, `--border-strong` → `line-strong`.

### 2.2 Tema

`data-theme="light" | "dark"` en `<html>`. Por defecto, **claro** (el del mockup).
Se cambia con el botón de la cabecera y se recuerda en `localStorage` (`kx-tema`).

- `dark:` en Tailwind = tema oscuro (`darkMode: ['variant', …]`), **salvo dentro de
  `.tema-claro`**.
- `.tema-claro` fuerza el claro en un subárbol. **El contenido de las pantallas aún
  no migradas va dentro**: están pintadas con la paleta clara de Tailwind y en
  oscuro serían ilegibles. El armazón sí sigue el tema. Cada etapa que migre una
  pantalla la sacará de ahí.

### 2.3 Colores

| Token CSS | Clase Tailwind | Claro | Oscuro | Uso |
|---|---|---|---|---|
| `--bg` | `canvas` | `#F3F4F9` | `#0D0E24` | Fondo de página |
| `--surface` | `surface` | `#FFFFFF` | `#16183A` | Paneles, campos, tarjetas |
| `--surface-2` | `surface-2` | `#EEF0F8` | `#20234D` | Hover, pestañas, segmentados, esqueletos |
| `--border` | `line` | `#DFE2EE` | `#2C3062` | Separadores |
| `--border-strong` | `line-strong` | `#7C83A1` | `#7A80B8` | Bordes de campos y botón secundario |
| `--text` | `ink` | `#14153A` | `#EEF0FF` | Texto principal |
| `--text-muted` | `ink-muted` | `#555A7B` | `#A9AED6` | Texto secundario, etiquetas de tabla |
| `--link` | `link` | `#4338CA` | `#A5B4FC` | Enlaces y botón fantasma |
| `--primary` | `primary` | `#4F46E5` | `#8B93F9` | Botón primario, ítem activo, foco de marca |
| `--on-primary` | `on-primary` | `#FFFFFF` | `#0D0E24` | Texto sobre primary |
| `--primary-hover` | `primary-hover` | `#4338CA` | `#A5B4FC` | Hover del primario |
| `--primary-soft` | `primary-soft` | `#E8EAFF` | `#26295C` | Chips, opción elegida |
| `--on-primary-soft` | `on-primary-soft` | `#3730A3` | `#C7D2FE` | Texto sobre primary-soft |
| `--accent` | `accent` | `#A5B4FC` | `#6D5FF5` | Acento decorativo |
| `--accent-text` | `accent-text` | `#4338CA` | `#C7D2FE` | Texto de acento |
| `--cta` | `cta` | `#4F46E5` | `#8B93F9` | Botón de llamada (Ingresar) |
| `--on-cta` | `on-cta` | `#FFFFFF` | `#0D0E24` | Texto sobre cta |
| `--cta-hover` | `cta-hover` | `#4338CA` | `#A5B4FC` | Hover de cta |
| `--nav-bg` | `nav-bg` | `#1E1B4B` | `#090A1C` | Menú desplegable |
| `--nav-text` | `nav-text` | `#FFFFFF` | `#EEF0FF` | Texto del menú |
| `--nav-muted` | `nav-muted` | `#C7D2FE` | `#A9AED6` | Módulos inactivos |
| `--nav-hover` | `nav-hover` | `#312E81` | `#20234D` | Hover del menú, caja del buscador |
| `--nav-active-bg` | `nav-active-bg` | `#4F46E5` | `#8B93F9` | Módulo actual |
| `--nav-active-text` | `nav-active-text` | `#FFFFFF` | `#0D0E24` | Texto del módulo actual |
| `--nav-border` | `nav-border` | `#312E81` | `#2C3062` | Separadores del menú |
| `--nav-label` | `nav-label` | `#C7D2FE` | `#A9AED6` | Pie del menú |
| `--hdr-bg` | `hdr-bg` | `#1E1B4B` | `#090A1C` | Cabecera |
| `--hdr-text` | `hdr-text` | `#FFFFFF` | `#EEF0FF` | Texto de la cabecera |
| `--hdr-muted` | `hdr-muted` | `#C7D2FE` | `#A9AED6` | Rol del usuario |
| `--hdr-border` | `hdr-border` | `#1E1B4B` | `#2C3062` | Borde de la cabecera |
| `--lg-bg` | `lg-bg` | `#312E81` | `#0B0C20` | Login: fondo del lienzo |
| `--lg-2` | `lg-2` | `#4F46E5` | `#2A2680` | Login: segundo color del lienzo |
| `--lg-text` | `lg-text` | `#FFFFFF` | `#FFFFFF` | Login: titular y cifras |
| `--lg-muted` | `lg-muted` | `#C7D2FE` | `#B9C0EE` | Login: lema y rótulos |
| `--lg-line` | `lg-line` | `#C7D2FE` | `#A5B4FC` | Login/Hero: trazos |
| `--lg-hot` | `lg-hot` | `#FCA311` | `#FCA311` | P90 excedido, peticiones fallidas |
| `--brand-bg` | `brand-bg` | `#1E1B4B` | `#1E1B4B` | Chip del logo |
| `--brand-text` | `brand-text` | `#FFFFFF` | `#FFFFFF` | «Kinetix» junto al logo |
| `--brand-muted` | `brand-muted` | `#C7D2FE` | `#C7D2FE` | «Performance» |
| `--hero-bg` | `hero-bg` | `#4338CA` | `#312E81` | Hero: inicio del degradado |
| `--hero-2` | `hero-2` | `#5548E0` | `#4338CA` | Hero: fin del degradado |
| `--hero-text` | `hero-text` | `#FFFFFF` | `#FFFFFF` | Hero: título |
| `--hero-muted` | `hero-muted` | `#E0E7FF` | `#E0E7FF` | Hero: texto |
| `--hero-line` | `hero-line` | `#C7D2FE` | `#A5B4FC` | Hero: trazos del lienzo |
| `--ok` | `ok` | `#0B6B3A` | `#7EE2A8` | Éxito (texto) |
| `--ok-bg` | `ok-bg` | `#E1F4E8` | `#0F3324` | Éxito (fondo) |
| `--warn` | `warn` | `#7A4B00` | `#FFD479` | Advertencia (texto) |
| `--warn-bg` | `warn-bg` | `#FFF1CC` | `#3A2A05` | Advertencia (fondo) |
| `--err` | `err` | `#A8201A` | `#FFB1AB` | Error (texto) |
| `--err-bg` | `err-bg` | `#FCE8E6` | `#45140F` | Error (fondo) |
| `--info` | `info` | `#3730A3` | `#C7D2FE` | Información (texto) |
| `--info-bg` | `info-bg` | `#E8EAFF` | `#26295C` | Información (fondo) |
| `--danger` | `danger` | `#B3261E` | `#C4322A` | Botón de peligro |
| `--on-danger` | `on-danger` | `#FFFFFF` | `#FFFFFF` | Texto sobre danger |
| `--focus` | `focus` | `#4338CA` | `#C7D2FE` | Anillo de foco |
| `--focus-nav` | `focus-nav` | `#FFFFFF` | `#C7D2FE` | Foco en el menú |
| `--focus-hdr` | `focus-hdr` | `#FFFFFF` | `#C7D2FE` | Foco en la cabecera |
| `--focus-hero` | `focus-hero` | `#FFFFFF` | `#FFFFFF` | Foco sobre Hero y login |
| `--chart-1` | `chart-1` | `#4F46E5` | `#7C83F0` | Serie 1 |
| `--chart-2` | `chart-2` | `#C76A00` | `#C8820F` | Serie 2 |
| `--chart-3` | `chart-3` | `#0E9F6E` | `#2FAE7F` | Serie 3 |
| `--scrim` | `scrim` | `#060B29` | `#000000` | Velo de modales y del menú desplegable (siempre con opacidad: `bg-scrim/60`) |

Sombras: `shadow-card` (paneles, KPI), `shadow-pop` (modales, menú), `shadow-seg`
(pestaña y segmento elegidos), `shadow-boton` (resplandor del primario),
`shadow-login` (tarjeta del login). Cambian con el tema.

### 2.4 Tipografía

| Familia | Clase | Para qué |
|---|---|---|
| **Plus Jakarta Sans** (200–800) | `font-body`, `font-display` | Toda la interfaz. Títulos en 800 con `tracking-display` (−0,025em) |
| **JetBrains Mono** (100–800) | `font-code` | Código, nombres de archivo, rutas, atajos de teclado, cifras del login |
| **Space Grotesk** (300–700) | `font-titular` | Solo el titular y la marca del inicio de sesión |

Fuentes variables, subconjunto latino, extraídas del mockup: cubren todo el español
(tildes, ñ, ¿, «»); **no traen «≤»**, que sale con la fuente del sistema. Inter se
retiró (se declaraba y no cargaba: auditoría 153 §1f).

Escala: la de Tailwind (`text-xs` … `text-4xl`) más `text-mini` (11 px),
`text-nota` (13 px), `text-control` (15 px), `text-destacado` (17 px), `text-h2`
(19 px), `text-tarjeta` (26 px), `text-h1` y `text-kpi` (32 px) y las fluidas del
login (`text-titular`, `text-cifra-login`, `text-lema`). Cifras siempre con
`tabular-nums`.

### 2.5 Radios y medidas

| Clase | Valor | Para qué |
|---|---|---|
| `rounded-chico` | 8 px | Pestaña y segmento internos, esqueletos |
| `rounded-control` | 12 px | Botones, campos, avisos |
| `rounded-panel` | 20 px | Paneles, KPI, Hero, zona de arrastre, modales |
| `rounded-pill` | 999 px | Insignias, avatar, progreso |
| `min-h-control` · `-sm` · `-lg` | 42 · 32 · 50 px | Alturas de control |
| `min-h-hdr` | 76 px (`--hdr-h`) | Cabecera |
| `w-riel` | 232 px | Riel de sección |
| `max-w-pagina` | 98rem (1.568 px) | **Ancho máximo común del contenido** |
| `max-w-lectura` | 68ch | Párrafos largos |

`rounded-s` no se usa como nombre: en Tailwind ya es el radio lógico de inicio.

## 3. Contraste (WCAG 2.2 AA)

Calculado de los tokens con la fórmula de luminancia relativa de WCAG. Texto
normal ≥ 4,5:1; texto grande y componentes no textuales (foco, bordes de campo)
≥ 3:1.

| Par (texto / fondo) | Uso | Claro | Oscuro | Mínimo |
|---|---|---|---|---|
| `text` / `bg` | Texto sobre el fondo de página | 15,96:1 ✓ | 16,78:1 ✓ | 4,5:1 |
| `text-muted` / `bg` | Texto secundario sobre el fondo | 6,10:1 ✓ | 8,79:1 ✓ | 4,5:1 |
| `text` / `surface` | Texto en paneles | 17,53:1 ✓ | 15,13:1 ✓ | 4,5:1 |
| `text-muted` / `surface` | Secundario en paneles | 6,70:1 ✓ | 7,92:1 ✓ | 4,5:1 |
| `text-muted` / `surface-2` | Secundario en pestaña inactiva / segmentado | 5,89:1 ✓ | 6,89:1 ✓ | 4,5:1 |
| `text` / `surface-2` | Texto sobre surface-2 (riel hover, chips) | 15,40:1 ✓ | 13,16:1 ✓ | 4,5:1 |
| `link` / `surface` | Enlaces y botón fantasma | 7,90:1 ✓ | 8,59:1 ✓ | 4,5:1 |
| `on-primary` / `primary` | Botón primario · ítem activo del riel | 6,29:1 ✓ | 6,91:1 ✓ | 4,5:1 |
| `on-cta` / `cta` | Botón Ingresar | 6,29:1 ✓ | 6,91:1 ✓ | 4,5:1 |
| `on-danger` / `danger` | Botón de peligro | 6,54:1 ✓ | 5,47:1 ✓ | 4,5:1 |
| `on-primary-soft` / `primary-soft` | Chip / opción elegida del buscador | 8,35:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `nav-muted` / `hdr-bg` | Módulos inactivos de la cabecera | 10,72:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `nav-text` / `nav-hover` | Módulo con el ratón encima | 11,42:1 ✓ | 13,16:1 ✓ | 4,5:1 |
| `nav-active-text` / `nav-active-bg` | Módulo actual | 6,29:1 ✓ | 6,91:1 ✓ | 4,5:1 |
| `hdr-text` / `hdr-bg` | Texto de la cabecera | 15,99:1 ✓ | 17,30:1 ✓ | 4,5:1 |
| `hdr-muted` / `hdr-bg` | Rol del usuario en la cabecera | 10,72:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `nav-muted` / `nav-hover` | Lupa y Ctrl K sobre su caja | 7,66:1 ✓ | 6,89:1 ✓ | 4,5:1 |
| `brand-text` / `brand-bg` | «Kinetix» en el chip de marca | 15,99:1 ✓ | 15,99:1 ✓ | 4,5:1 |
| `nav-muted` / `nav-bg` | Menú desplegable: ítems | 10,72:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `nav-label` / `nav-bg` | Menú desplegable: pie | 10,72:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `ok` / `ok-bg` | Aviso / insignia de éxito | 5,76:1 ✓ | 8,77:1 ✓ | 4,5:1 |
| `warn` / `warn-bg` | Aviso / insignia de advertencia | 6,60:1 ✓ | 9,88:1 ✓ | 4,5:1 |
| `err` / `err-bg` | Aviso / insignia de error | 6,18:1 ✓ | 8,92:1 ✓ | 4,5:1 |
| `info` / `info-bg` | Aviso / insignia informativa | 8,35:1 ✓ | 9,06:1 ✓ | 4,5:1 |
| `err` / `surface` | Mensaje de error de un campo | 7,28:1 ✓ | 9,89:1 ✓ | 4,5:1 |
| `bg` / `text` | Toast (texto canvas sobre tinta) | 15,96:1 ✓ | 16,78:1 ✓ | 4,5:1 |
| `lg-text` / `lg-bg` | Login: titular y cifras sobre el lienzo (fondo) | 11,42:1 ✓ | 19,31:1 ✓ | 4,5:1 |
| `lg-text` / `lg-2` | Login: titular sobre el lienzo (segundo color) | 6,29:1 ✓ | 12,45:1 ✓ | 4,5:1 |
| `lg-muted` / `lg-bg` | Login: lema y rótulos (fondo) | 7,66:1 ✓ | 10,88:1 ✓ | 4,5:1 |
| `lg-muted` / `lg-2` | Login: lema y rótulos (segundo color) | 4,22:1 ✗ | 7,02:1 ✓ | 4,5:1 |
| `lg-hot` / `lg-bg` | Login: P90 excedido | 5,65:1 ✓ | 9,55:1 ✓ | 3,0:1 |
| `hero-text` / `hero-bg` | Hero: título | 7,90:1 ✓ | 11,42:1 ✓ | 4,5:1 |
| `hero-muted` / `hero-bg` | Hero: texto | 6,41:1 ✓ | 9,27:1 ✓ | 4,5:1 |
| `hero-muted` / `hero-2` | Hero: texto sobre el 2.º color | 5,03:1 ✓ | 6,41:1 ✓ | 4,5:1 |
| `focus` / `bg` | Anillo de foco sobre el fondo (no texto) | 7,20:1 ✓ | 12,74:1 ✓ | 3,0:1 |
| `focus` / `surface` | Anillo de foco en paneles (no texto) | 7,90:1 ✓ | 11,48:1 ✓ | 3,0:1 |
| `focus-hdr` / `hdr-bg` | Anillo de foco en la cabecera (no texto) | 15,99:1 ✓ | 13,14:1 ✓ | 3,0:1 |
| `focus-hero` / `hero-bg` | Anillo de foco en el hero (no texto) | 7,90:1 ✓ | 11,42:1 ✓ | 3,0:1 |
| `border-strong` / `surface` | Borde de los campos (no texto) | 3,74:1 ✓ | 4,57:1 ✓ | 3,0:1 |

**El único par que no llega** es `lg-muted` sobre `lg-2` en claro (4,22:1): el lema
y los rótulos del login **si cayeran sobre el color más claro del degradado**. No
caen: el velo radial (`bg-velo-login`) oscurece la columna del texto. Medido en
píxeles reales en la Etapa 0 (reporte 155 §5): el peor texto del login está en
6,1:1 en claro y 6,91:1 en oscuro. **Si se mueve el texto del login o el velo, hay
que volver a medirlo.**

Reglas que salen de aquí:

- **El oro de marca no es un color de texto** sobre fondo claro (2,03:1, auditoría
  153 §6.1). En el sistema nuevo no existe como token.
- Un botón **deshabilitado** baja al 50 % (WCAG exime los controles inactivos); uno
  **cargando** no: su texto («Guardando…») tiene que leerse.
- El texto sobre lienzo animado (login, Hero) se mide sobre los píxeles de
  verdad, no sobre el token: las partículas cruzan por detrás.

## 4. Biblioteca base (`components/ui/`)

Todos tipados, con `type="button"` por defecto donde aplica, foco visible (anillo
de 3 px `focus`; en cabecera, Hero y login, su color propio) y objetivos de al
menos 24 px.

| Componente | Estados | Notas de uso |
|---|---|---|
| `Button` | normal, hover, foco, deshabilitado, **cargando** (giro + `aria-busy`) | Variantes `primary`, `cta`, `secondary`, `ghost`, `danger`, `hero`, `hero-outline`; tamaños `sm`/`md`/`lg`; `icon`; `bloque`. **Un solo primario por pantalla** |
| `IconButton` | ídem | `etiqueta` obligatoria (aria-label y título). Variante `cabecera` para la barra oscura |
| `Field` | con ayuda, con error, obligatorio | Etiqueta + control + ayuda + error. `describedBy(id, ayuda, error)` da el `aria-describedby` |
| `Input`, `Select`, `Textarea` | normal, foco, deshabilitado, **error** (`invalido` → `aria-invalid`) | Una altura (42 px) y un foco. `Input codigo` usa JetBrains Mono |
| `Checkbox` | marcado, deshabilitado, error | La fila entera es pulsable (40 px) |
| `Switch` | encendido, apagado, deshabilitado | `role="switch"` |
| `Badge` | `neutral`, `ok`, `warn`, `err`, `info`, `primary` | El texto dice lo mismo que el color |
| `Panel` | con o sin cabecera, `sinRelleno` | Sin borde en claro, con borde en oscuro |
| `Kpi` | con nota (tono), **sin dato** | Sin dato pinta «—» y lo dice al lector: **nunca un 0 falso** |
| `DataTable` | con filas, vacía (`vacio`) | Columna de **acciones fija** a la derecha; **tarjetas** si el contenedor mide < 58rem; `caption` oculto. La carga y el error no son de la tabla |
| `Tabs` + `TabPanel` | activa, inactiva, foco | Patrón WAI-ARIA completo: flechas, Inicio, Fin |
| `Segmented` | elegido | Grupo con `aria-pressed`: cambia la vista en el sitio, sin panel |
| `Alert` | `info`, `ok`, `warn`, `err`; con acción; con cierre | El de error es `role="alert"` |
| `EmptyState` | — | Solo si la petición salió bien y no hay nada |
| `LoadingState` | — | Esqueleto con `role="status"` y el nombre de lo que carga |
| `ErrorState` | con o sin **Reintentar**, reintentando | Sustituye a los indicadores y tablas: **no se pintan ceros** |
| `Modal` | abierto, bloqueado | `role="dialog"`, foco dentro y atrapado, Escape, vuelve al botón que lo abrió, por portal |
| `ConfirmDialog` | normal, peligro, ejecutando | Sustituye a `confirm()`. El botón dice lo que hace; el foco empieza en **Cancelar** |
| `Toast` (`ToastProvider` + `useToast`) | `ok`, `info`, `warn`, `err` | Sustituye a `alert()`. Se van a los 4,5 s **salvo los de error**; se paran con el ratón o el foco encima |
| `Dropzone` | normal, arrastrando, deshabilitado, error | `<label>` + `input file` oculto: clic, teclado y arrastre |
| `Progress` | con valor, indeterminada; tonos | `role="progressbar"` con `aria-valuetext` |
| `Hero` | animado, quieto | Degradado `hero-bg → hero-2` con `LoadFx` detrás |
| `LoadFx` | animado, pausado, quieto | Escenas `login` y `hero`. Ver §5 |
| `Spinner` | — | Decorativo; el texto de al lado es el que informa |

## 5. Movimiento

| Interruptor | Dónde | Efecto |
|---|---|---|
| **Pausa del usuario** | Botón de la cabecera (y el del login, que es el mismo) | `html[data-movimiento="pausado"]`, recordado en `localStorage` (`kx-movimiento`) |
| **`prefers-reduced-motion: reduce`** | El sistema operativo | Las animaciones CSS duran 0,01 ms; el botón de pausa del login no aparece |

Reglas:

1. **En pausa, las animaciones se quitan, no se congelan** (`animation: none`).
   Congeladas, las de entrada se quedaban en su primer fotograma (`opacity: 0`) y
   un diálogo abierto con la pausa puesta no se veía (encontrado en la Etapa 0).
2. Toda animación de pieza se escribe con `motion-safe:` (`motion-safe:animate-pop`).
3. Los lienzos (`LoadFx`) miran `quieto` de `usePreferencias()`: con pausa o
   movimiento reducido **no corren**; pintan una imagen fija de un tramo de prueba
   ya simulado, y al reanudar siguen desde ahí.
4. Animaciones disponibles: `pop` (diálogos), `rise`, `sube` y `tarjeta`
   (entradas), `pulso` (esqueletos), `parpadeo` (indicador de fase), `crece`
   (barras), `flota` (icono de la zona de arrastre). Duraciones de 0,18 a 1,8 s con
   `cubic-bezier(.2,.8,.2,1)` (`ease-suave`).
5. Nada parpadea más de 3 veces por segundo (WCAG 2.3.1).
6. **Entrada escalonada**: los hijos de `.kx-escalonado` (en `ui.css`) entran uno
   tras otro, separados por el token `--entrada-paso` (80 ms). Solo afecta a los
   que ya tienen una animación `motion-safe:`.
7. **Texto sobre un lienzo animado** lleva `.kx-sobre-lienzo`: un halo del color
   del fondo para que una partícula que pase por detrás no baje el contraste.

## 6. Armazón y cortes de ancho

```
>= 1100 px  [marca] [módulos …]                 [buscar] [pausa] [tema] [cuenta]
            [riel de sección] [contenido, máx. 98rem, centrado]

<  1100 px  [menú] [marca]                       [buscar] [pausa] [tema] [cuenta]
            [sub-pestañas del módulo, en varias líneas si hace falta]
            [contenido]
            «menú» abre el panel desplegable (todos los módulos, plegables)

1100-1499   la cabecera esconde el nombre, el rol y «Ctrl K»: queda el avatar
            (nombre y rol en su aria-label y title), y los módulos caben en UNA línea

<   900 px  la cabecera esconde el nombre del usuario y el atajo «Ctrl K»
```

| Clase | Corte | Qué cambia |
|---|---|---|
| `nav:` | 1100 px | Módulos en la cabecera y riel vertical; por debajo, menú desplegable y sub-pestañas |
| `cabecera:` | 901 px | Nombre del usuario y «Ctrl K»; el login pasa a dos columnas |
| `amplia:` | 1500 px | Vuelven el nombre, el rol y «Ctrl K» a la cabecera (entre 1100 y 1499 se esconden) |
| `sm:` … `2xl:` | los de Tailwind | Márgenes del contenido |

- **La cabecera es siempre de una línea, de 76 px de alto** (Fredy, revisión de
  la Etapa 0: era de 60). Logo a 36 px de alto, módulos a 1rem con peso 600,
  botones de la derecha de 44 × 44 con iconos de 22 px y avatar de 40 px. Si un
  día no caben, se reduce el espacio entre módulos antes que la letra.
  Entre 1100 y 1499 px, para que quepan los siete módulos del admin, se esconden el nombre, el rol y «Ctrl K»;
  el avatar lleva el nombre en `aria-label` y `title` (decisión de Fredy en la
  revisión de la Etapa 0; el mockup partía los módulos en dos líneas). Medido a
  1194, 1280 y 1366: una línea (a 1194 sobran unos 10 px).
- `<main>` **no** lleva `overflow-x-hidden`: si algo no cabe, se ve.
- Los ítems, rutas y roles del menú salen de `navegacion.ts`, una sola definición
  para cabecera, riel, menú desplegable y buscador. `ubicar(ruta)` decide el módulo
  y la pantalla actuales (gana la ruta más larga que case).
- Accesibilidad del armazón: «Saltar al contenido» es la primera parada de Tab;
  al cambiar de pantalla el foco va a `<main>`; Ctrl + K abre «Ir a una pantalla»
  (combobox con `aria-activedescendant`); el menú desplegable atrapa el foco y
  Escape lo devuelve al botón de menú.
- Las sub-pestañas y el riel son **enlaces de navegación** (`aria-current="page"`),
  no pestañas de WAI-ARIA: cambian de ruta, no muestran un panel.

## 7. El guardián de tokens

```
python tools/check_tokens.py           # falla (código 1) si hay valores prohibidos
python tools/check_tokens.py --lista   # qué archivos revisa
```

Revisa el **alcance de cada etapa** (lista `ALCANCE`, ampliable) y busca hex,
colores funcionales literales, valores/variantes/propiedades arbitrarias de
Tailwind y clases de la paleta por defecto o de `sqa-*`. Exento: solo `tokens.css` (el menú viejo,
`Sidebar.tsx` y `Footer.tsx`, se borró al empezar la Etapa 1).
**Cada etapa añade a `ALCANCE` lo que migra.**
