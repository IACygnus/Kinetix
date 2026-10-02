Commit base `367d975` · 2 de octubre de 2026 · Reporte 153 — auditoría de interfaz de Kinetix (solo lectura)

# Auditoría de interfaz de Kinetix

> **Qué es.** El inventario de cómo está configurada y cómo se ve hoy la interfaz,
> antes de rediseñarla. **No cambia nada del producto**: no se editó ningún archivo
> de `frontend/` ni de `backend/`, no hubo rebuild de Docker y no se tocó
> `package.json`. Los protegidos se leyeron.
>
> **Entregables:** este reporte · `153-auditoria-ui-datos.json` (datos crudos de
> 1e-1g y 2b-2g) · `153-auditoria-ui-capturas.zip` (465 capturas JPEG q70, **fuera
> de git**) · `154-resumen-para-fredy.md` (una página).
>
> **Llamadas reales a IA que generan texto: 0.** Peticiones abortadas: 223 (§2.1).

---

## 0. Cómo se hizo

### 0.1 Rama y árbol

- Rama de partida `backup-trabajo-local` en `367d975`. **Ningún archivo versionado
  con cambios.** Había 134 archivos **sin versionar**, todos en `docs/reports/repo/`:
  la regla 19 manda no tocarlos ni señalarlos, así que no se consideraron «cambios
  sin confirmar» y se siguió.
- Rama `rediseno-ui` creada desde ahí. El commit solo lleva los dos `.md` y el `.json`.

### 0.2 Herramientas (fuera del repo)

- **No hay Node en el equipo** (`node`, `npm`, `npx` no existen en el PATH; el
  `frontend/node_modules` del anfitrión está vacío: las dependencias viven dentro de
  `jmeter_frontend`). El paso 2 pedía `npm i playwright`; se usó **la misma
  herramienta en su versión de Python**: `C:\proyectos\kinetix-audit-tools\venv`,
  Playwright **1.63.0**, y `playwright install chromium` **sí descargó** Chromium
  (no hizo falta Edge). Los scripts (`audit.py`, `measure.js`, `focus.js`,
  `pass3.py`, `analyze.py`) quedan en esa carpeta.
- Versiones instaladas reales: leídas **dentro de `jmeter_frontend`** con
  `node -p require(...).version` (solo lectura).
- Conteos estáticos: script propio sobre los 113 `.ts/.tsx/.css` de `frontend/src`
  (sin `*.bak*`), con la paleta de Tailwind **exportada del propio contenedor** para
  traducir clase → hex.

### 0.3 Protección de datos y de cuota (paso 2)

- **Interceptor de red en todo el contexto del navegador**: toda petición que no
  sea `GET` se **aborta y se registra**, salvo `POST /auth/login`. En la pasada de
  modales se abortaron además los `GET .../export/...` (exportar no es un modal).
- **Antes de navegar**, un análisis del código de cada ruta (los `useEffect` al
  montar → `services/api.ts` → el handler del backend) confirmó:
  - **Ningún GET de ninguna ruta llama a la IA para generar.** `POST
    /transaction-report` solo sale al pulsar «Generar»; abrir una sesión del
    Analista IA **no envía mensajes**.
  - **Un solo GET escribe en la base**: `GET /observabilidad/sesiones/{id}/metricas`
    pasa la sesión de `preparada` a `en_curso` (`sesiones.py:583-586`). En la base
    hay **0 sesiones de monitoreo**, y la ruta se visitó con un id inexistente
    (`00000000-…`): devuelve 404 y no escribe nada.
  - **Tres GET hacen una llamada saliente a OpenAI que no genera texto**:
    `/ai-config/estado` (`models.retrieve`, caché 60 s), `/ai-config/models/live`
    (`models.list`, caché 5 min). Se pidieron 46 y 18 veces; con la caché, la
    cifra de llamadas que salieron de verdad a OpenAI **no se midió**.
  - `GET /gemini-test` (`upload.py:86`) **sí genera** con la IA, pero ninguna
    pantalla lo llama y no se visitó.
- No se pulsó Generar, Analizar, Regenerar, Guardar, Eliminar ni Consolidar. Los
  diálogos nativos (`confirm`) se cancelan automáticamente; no apareció ninguno.

### 0.4 Usuarios

- Solo **admin**. Existen tres usuarios **analista** (Moni, ruben, adrian), pero son
  personas reales cuya contraseña no conozco, y **no hay ningún visor**. No se
  crearon ni se tocaron. Lo que ve cada rol sale **del código** (§1d), no del
  navegador.

### 0.5 Inicios de sesión

Seis logins en total (recorrido, dos sondas de depuración, listado de controles,
modales y un fallido): el séptimo **falló por el límite de 5 por 15 min y por IP**
(regla 26) y **no se reintentó**. Ese fallo cortó una última pasada de
recolección de títulos y columnas; ese inventario se hizo leyendo el código (§9).

---

## 1. Auditoría estática

### 1a. Stack real del frontend

| Paquete | `package.json` | Instalado (contenedor) |
|---|---|---|
| react / react-dom | ^18.2.0 | **18.3.1** |
| vite | ^5.0.8 | **5.4.21** |
| tailwindcss | ^3.3.6 | **3.4.18** |
| typescript | ^5.2.2 | **5.9.3** |
| react-router-dom | ^6.20.0 | 6.30.2 |
| recharts (gráficas) | ^2.15.4 | 2.15.4 |
| lucide-react (íconos) | ^0.294.0 | 0.294.0 |
| axios | ^1.6.2 | 1.13.2 |
| @dnd-kit/core · sortable | ^6.3.1 · ^10.0.0 | 6.3.1 · 10.0.0 |
| html2canvas · jspdf | ^1.4.1 · ^3.0.4 | 1.4.1 · 3.0.4 — **sin uso**: `usePDFExport.ts` no lo importa nadie |
| postcss · autoprefixer · @vitejs/plugin-react | | 8.5.6 · 10.4.22 · 4.7.0 |
| Node (contenedor) | | v18.20.8 |

- **Librería de componentes UI: ninguna.** Ni shadcn, ni Headless UI, ni Radix: todo
  es JSX + clases de Tailwind escritas a mano.
- **Scripts** (`frontend/package.json:6-10`): `dev`, `build` (`tsc && vite build`),
  `preview`. **No existe script de lint, ni de pruebas, ni de formato**; tampoco
  hay ESLint, Prettier, Vitest ni Jest instalados. Las pruebas que existen son las
  e2e de `backend/pruebas_e2e/`, ajenas al frontend.
- `frontend/index.html:5` pide `/vite.svg` como favicon: **no existe**
  (`frontend/public/` no existe) → 404.

### 1b. Organización de los estilos

| Pieza | Dónde | Contenido |
|---|---|---|
| Tema de Tailwind | `frontend/tailwind.config.js:8-19` | Solo `extend.colors.sqa`: `navy #0a1628`, `navy-light #111d35`, `gold #f5a623`, `gold-dark #d4891a`, `gold-light #f7b84e`, `card #162040`, `border #1e3a5f`. **Nada más**: ni tipografía, ni radios, ni sombras, ni espaciado propios. Sin plugins |
| CSS global | `frontend/src/index.css` (91 líneas) | `font-family: 'Inter', …` en `body` (:5-8), fondo del `body` `#0a1628`, barra de scroll oscura, `.no-print{display:none}`, partículas del login, `.sqa-animated-header`, animación de toast. **Ninguna clase de componente con `@apply`** |
| CSS por componente | — | **No hay** archivos `.css`/`.module.css` por componente |
| Estilos en línea | 44 bloques `style={{…}}` en 18 archivos | Más en `Login.tsx` (9), `AIScriptEditor.tsx` (7), `ReportBody.tsx` (3), `BodyEditor.tsx` (3). Tamaños de letra en línea: 11 (×39), 10 (×16), 14 (×15) — casi todos de ejes de Recharts |
| Variables CSS (`--x`) | — | **Ninguna en el frontend.** (Los exportadores del backend sí tienen `:root` propio, §1j) |
| Tema oscuro (`dark:`) | — | **0 usos de `dark:`.** No hay modo oscuro conmutable; hay **pantallas oscuras sueltas** pintadas a mano (§3.1) |
| Puntos de ruptura | 65 usos en total | `md:` 27 · `sm:` 25 · `lg:` 11 · `xl:` 2. **El layout no tiene ninguno**: el menú lateral mide 288 px (`w-72`) o 64 px a cualquier ancho (`Layout.tsx:28`, `Sidebar.tsx:341`) |

**Los tokens existen pero casi no se usan**: `#f5a623` aparece **260 veces** como hex
literal (210 en clases arbitrarias `bg-[#f5a623]`…) frente a **68** usos de
`sqa-gold`; `#0a1628`, **157** frente a **23** de `sqa-navy`. Y hay un **casi
duplicado**: `#f7b84a` (25 usos, hover del oro) frente al token `gold-light
#f7b84e`, que nadie usa con ese valor.

### 1c. Rutas por módulo

`frontend/src/App.tsx`. «Líneas» = del componente de la ruta (sin sus hijos).

| Módulo | Ruta | Componente | Líneas | Roles |
|---|---|---|---|---|
| General | `/login` | `components/auth/Login.tsx` | 152 | pública |
| | `/dashboard` | `components/dashboard/DashboardHome.tsx` | 308 | todos |
| | `/profile` | `components/profile/Profile.tsx` | 257 | todos |
| Análisis | `/performance/new` | `NewReportWrapper` → `dashboard/UploadJTL.tsx` | 922 | admin, analista |
| | `/performance/analista` · `/:sesionId` | `pages/AnalistaIAPage.tsx` | 326 | admin, analista |
| | `/performance/report/:executionId` | `ReportWrapper` → `dashboard/Dashboard.tsx` ⚠ protegido | 1058 | todos |
| | `/performance/report-latest` | `pages/ReportView.tsx` (redirige al último) | 69 | todos |
| | `/performance/history` | `components/performance/History.tsx` | 440 | todos |
| | `/performance/monitoring` | `pages/MonitoringPage.tsx` («Capturas de infraestructura») | 309 | todos |
| | `/performance/evidence` | `pages/EvidencePage.tsx` | 303 | todos |
| | `/performance/integrated` · `/:reportId` | `pages/IntegratedReportPage.tsx` | 943 | todos |
| | `/performance/integrated/history` | `pages/IntegratedReportsHistory.tsx` | 477 | admin, analista |
| Horas | `/horas/registro` | `pages/horas/RegistroPage.tsx` | 335 | todos |
| | `/horas/consulta` | `pages/horas/ConsultaPage.tsx` | 424 | todos |
| | `/horas/proyectos` | `pages/horas/ProyectosPage.tsx` | 679 | todos |
| | `/horas/actividades` | `pages/horas/ActividadesPage.tsx` | 246 | todos |
| | `/horas/importar` | `pages/horas/ImportarPage.tsx` | 521 | todos |
| | `/horas/informes` | `pages/horas/InformesPage.tsx` | 623 | todos |
| Observabilidad | `/observabilidad/sesiones` | `pages/SesionesPage.tsx` | 256 | admin, analista |
| | `/observabilidad/sesiones/nueva` | `pages/SesionNuevaPage.tsx` | 369 | admin, analista |
| | `/observabilidad/sesiones/:sesionId` | `pages/SesionPage.tsx` | 311 | admin, analista |
| | `/observabilidad/servidores` | `pages/ServidoresPage.tsx` | 586 | admin, analista |
| | `/observabilidad/vivo` (y `/monitoring/vivo` → redirige) | `pages/MonitoreoVivoPage.tsx` | 286 | admin, analista |
| Monitoreo (sin menú) | `/monitoring/realtime` | `components/monitoring/MonitoringRealtime.tsx` | 269 | todos |
| | `/monitoring/settings` | `components/monitoring/MonitoringSettings.tsx` | 354 | admin |
| Administración | `/users` | `components/users/UserList.tsx` | 278 | admin |
| | `/users/new` · `/users/:userId` | `components/users/UserForm.tsx` | 249 | admin |
| | `/admin/clients` | `components/clients/ClientsPage.tsx` | 470 | admin |
| | `/admin/assignments` | `components/clients/AssignmentsPage.tsx` | 244 | admin |
| | `/admin/ai-config` | `components/admin/AIConfigPage.tsx` | 489 | admin |
| Diseño | `/script-designer` · `/:scriptId` | `pages/ScriptDesigner.tsx` ⚠ protegido | 967 | admin, analista |
| | `/script-designer/history` | `pages/ScriptHistory.tsx` | 174 | admin, analista |
| | `/ai-script-designer` | `pages/AIScriptDesigner.tsx` | 1352 | admin, analista |
| | `/ai-script-designer/history` | `pages/AIDesignerHistory.tsx` | 432 | admin, analista |
| | `/ai-script-editor` | `pages/AIScriptEditorList.tsx` | 199 | admin, analista |
| | `/ai-script-designer/editor/:designId` | `pages/AIScriptEditor.tsx` | **7375** | admin, analista |
| Ejecución | `/execution-dashboard` | `pages/ExecutionDashboard.tsx` | 101 | admin, analista |
| — | `/` y `*` | redirigen a `/dashboard` | | |

**36 pantallas distintas** (41 rutas auditadas contando variantes con id).

### 1d. Qué ve cada rol

**Mecanismo.** Guardia de ruta en `components/common/ProtectedRoute.tsx:25`
(`roles.includes(user.role)`, si no → `/dashboard` **sin aviso**). Filtro del menú en
`layout/Sidebar.tsx:323-326` (`isItemVisible`; una sección se oculta si no le queda
ningún hijo, `:378-379`). `hasRole` existe en `context/AuthContext.tsx:111-113` y
**no lo usa nadie**: todas las comprobaciones son `user?.role === 'admin'` en línea.

**Menú** (`Sidebar.tsx`): Dashboard (:71) · **Diseño** [admin, analista] (:76) con
Editor, Diseñador IA, Mis Diseños IA, Editor IA, Guardados · Ejecución [admin,
analista] (:111) · **Análisis** (:117) con Nuevo Reporte, Analista IA [admin,
analista], Reporte, Historial Reporte, Capturas de infraestructura, Evidencias,
Informe Integrado, Historial Integrado · **Observabilidad** (:169) con sus 3 ítems
[admin, analista] · **Horas** (:201), 6 ítems sin restricción · **Administración**
[admin] (:258) con Usuarios, Clientes, Asignaciones, Configuración IA · pie con
perfil (`nombreRol`, :453) y Cerrar sesión. El bloque «Monitoreo» (Real-Time,
Configuración) está **comentado** (:239-257): esas dos rutas no tienen entrada.

**Condiciones dentro de las pantallas:**

| Archivo:línea | Condición | Efecto | Quién |
|---|---|---|---|
| `performance/History.tsx:387` | `user?.role === 'admin'` | Botón Eliminar por ejecución | admin |
| `pages/IntegratedReportsHistory.tsx:421` | ídem | Eliminar informe integrado (Renombrar, todos) | admin |
| `pages/EvidencePage.tsx:238` · `MonitoringPage.tsx:243` | ídem | Eliminar adjunto | admin |
| `pages/AIDesignerHistory.tsx:374` | ídem | Eliminar diseño IA | admin |
| `pages/AIScriptEditor.tsx:6187`, `:6339` · `script-designer/DataFileManager.tsx:111` | ídem | Eliminar archivo de datos | admin |
| `pages/ServidoresPage.tsx:84` → `observabilidad/TokensIngesta.tsx:138,169,190,303,311` | `esAdmin` | Crear / revocar token de ingesta; cargar token de InfluxDB | admin |
| `pages/horas/RegistroPage.tsx:30,72,122,152,300,308,328` | `esAdmin`, `puedeEditar` | Selector de persona (deshabilitado si no), editar registros ajenos, borrar registros, registrar por otro | admin |
| `pages/horas/ImportarPage.tsx:46,55,155,354` | `esAdmin` | Importar para otro; panel **Borrar periodo** | admin |
| `pages/horas/ActividadesPage.tsx:99` | `!esAdmin` | Borrar actividad, deshabilitado con motivo | admin |
| `components/horas/EstadoProyecto.tsx:47,92` | `SOLO_ADMIN` | «No viable» y «Finalizado» deshabilitados (no ocultos) | admin |
| `dashboard/DashboardHome.tsx:85,92` | rol admin | KPI «Usuarios Registrados»; rejilla de 4 o 3 columnas | admin |
| `DashboardHome.tsx:133,222` | admin o analista | Acceso rápido «Nuevo Reporte» y «Crear primer reporte» | admin, analista |
| `clients/AssignmentsPage.tsx:143-194` | rol **del usuario listado** | Color del rol, botón Asignar, nota de admin | (no es del que mira) |

**Por rol** (deducido del código):

- **admin**: todo el menú y todas las rutas, incluidas `/monitoring/realtime` y
  `/monitoring/settings`, que no tienen entrada en el menú.
- **analista**: todo menos Administración y `/monitoring/settings`. **Ningún botón
  de eliminar**; tokens en solo lectura; en horas solo lo suyo.
- **visor**: Dashboard, Análisis (7 ítems), Horas (6) y Perfil.
- **Dos ítems del menú engañan al visor**: «Nuevo Reporte» (`Sidebar.tsx:121`) e
  «Historial Integrado» (`:162`) no llevan `roles`, pero sus rutas exigen admin o
  analista (`App.tsx:74`, `:103`). El visor los ve, pulsa, y vuelve a
  `/dashboard` sin explicación.

### 1e. Colores en uso

Cifras exactas en `153-auditoria-ui-datos.json` → `paso1_estatico.1e_colores_y_valores`.

| Medida | Valor |
|---|---|
| Clases de color de Tailwind distintas | **349** |
| Usos de clases de color | **5.803** |
| Valores arbitrarios distintos (`x-[…]`) | 97, de ellos **516 usos con color** (`#`, `rgb`) |
| Hex literales distintos en `.ts/.tsx/.css` | **68** (653 usos) |
| `rgba()` literales | 3 |

**Familias de Tailwind por uso** (todas las propiedades): gray 2.785 · red 633 ·
white 598 · indigo 306 · amber 280 · blue 262 · green 199 · **emerald 187** ·
slate 121 · purple 120 · orange 84 · **sqa-gold 68** · **yellow 36** · black 35 ·
sqa-navy 23 · cyan 8 · teal 4 · sky 3. Tres pares que significan lo mismo conviven:
**green/emerald**, **amber/yellow**, **gray/slate**.

**Las 15 clases más usadas** (con su hex):

| Clase | Hex | Usos |
|---|---|---|
| `text-gray-500` | #6b7280 | 430 |
| `text-gray-700` | #374151 | 353 |
| `border-gray-300` | #d1d5db | 350 |
| `bg-white` | #ffffff | 327 |
| `border-gray-200` | #e5e7eb | 316 |
| `text-gray-400` | #9ca3af | **297** — la que más falla en contraste (§6.1) |
| `text-gray-800` | #1f2937 | 236 |
| `text-white` | #ffffff | 227 |
| `text-gray-600` | #4b5563 | 222 |
| `bg-gray-50` | #f9fafb | 210 |
| `bg-gray-100` | #f3f4f6 | 112 |
| `bg-red-50` | #fef2f2 | 111 |
| `text-red-600` | #dc2626 | 88 |
| `text-red-700` | #b91c1c | 81 |
| `text-gray-900` | #111827 | 69 |

**Valores arbitrarios de color más usados**: `border-[#f5a623]` 87 · `bg-[#f5a623]`
80 · `text-[#0a1628]` 68 · `bg-[#0a1628]` 54 · `text-[#f5a623]` 50 ·
`bg-[#f7b84a]` 25 · `border-[#0a1628]` 22 · `ring-[#f5a623]` 19 · `bg-[#0d1f3c]` 13 ·
`border-[#2a3f6f]` 11 · `accent-[#f5a623]` 10.

**Hex literales más usados**: `#f5a623` 260 · `#0a1628` 157 · `#f7b84a` 25 ·
`#e6951e` 15 · `#2a3f6f` 14 · `#0d1f3c` 13 · `#162040` 12 · `#e5e7eb` 11 · `#ef4444`
11 · `#3b82f6` 9 · `#4f46e5` 8. **Cinco hover distintos del oro** (`#f7b84a`,
`#e6951e`, `#e09410`, `#d4850f`, `/90`) y **cinco del navy** (`#16243d`, `#1a2638`,
`#16243c`, `#1a2d4a`, `/90`).

**`config/chartConfig.ts`** (167 líneas): `CHART_COLORS` de 15 colores (:7-9:
`#3b82f6 #ef4444 #10b981 #f59e0b #8b5cf6 #ec4899 #06b6d4 #84cc16 #f97316 #6366f1
#14b8a6 #e11d48 #7c3aed #0ea5e9 #d946ef`), `HTTP_CODE_COLORS` (:13-17: 2xx verdes,
3xx azules, 4xx naranjas/rojos, 5xx rojos oscuros), colores de serie `#3b82f6`
(:77), `#8b5cf6` (:86), `#ef4444` (:93), `#6366f1` (:114) y por defecto `#94a3b8`
(:129). **Idéntico** a `backend/app/config/chart_config.py`: están sincronizados.

**Estilos calculados en el navegador** (1366 px, 41 rutas): **55 colores de texto
distintos** y **73 fondos distintos**.

### 1f. Tipografía

- **Familia declarada:** `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', …`
  (`index.css:5-8`). **Inter no se carga de ningún sitio**: ni Google Fonts, ni
  `@font-face`, ni archivo local, ni está instalada en este equipo. **Comprobado con
  CDP** (`CSS.getPlatformFontsForNode`): lo que se pinta es **Segoe UI**. En un Mac
  saldría San Francisco y en Linux otra: **la app no tiene una tipografía fija**.
- Monoespaciada: `font-mono` (186 usos) → `ui-monospace, SFMono-Regular, Menlo,
  Consolas…`; un `Consolas, Monaco, 'Courier New'` en línea (`BodyEditor`).
- **Tamaños de clase** (usos): `text-sm` 786 · `text-xs` 449 · `text-lg` 359 ·
  `text-base` 348 · `text-xl` 229 · `text-2xl` 86 · `text-3xl` 44 · `text-4xl` 31 ·
  `text-6xl` 3 · `text-5xl` 2 · `text-7xl` 1. Más `text-[10px]` (6), `text-[11px]`.
- **Pesos**: `font-semibold` 385 · `font-bold` 363 · `font-medium` 287 ·
  `font-normal` 18.
- **Tamaños calculados en pantalla** (1366, nodos con texto): 14 px 1.433 · 16 px
  1.208 · 12 px 721 · 18 px 672 · 20 px 562 · 24 px 516 · 11 px 284 · **8 px 244** ·
  30 px 148 · 36 px 54. **Los 8 px son las marcas de eje de Recharts** del informe
  (`tspan.recharts-cartesian-axis-tick-value`, 95 por informe).
- **Dos escalas que no conviven**: los módulos nuevos (Horas, Observabilidad,
  Analista) usan cuerpo de 18-20 px y controles de 44 px de alto; la familia del
  Script Designer usa `text-sm`/`text-xs`. El menú lateral va en **`text-2xl` (24
  px)** (`Sidebar.tsx:333`), más grande que casi todos los títulos de sección.

### 1g. Radios, sombras, espaciado

| | Usos |
|---|---|
| Radios | `rounded-xl` 287 · `rounded-lg` 279 · `rounded` 261 · `rounded-md` 188 · `rounded-2xl` 147 · `rounded-full` 113 · 10 variantes de esquina |
| Sombras | `shadow-sm` 65 · `shadow-lg` 63 · `shadow-xl` 26 · `shadow-2xl` 24 · `shadow` 7 · `shadow-md` 3 |
| Espaciado | **141 clases distintas** de padding, margin y gap. Más usadas: `px-3` 477 · `px-4` 418 · `py-2` 398 · `py-3` 395 · `gap-2` 379 · `gap-3` 193 · `py-1.5` 191 |
| Ancho máximo | Cada pantalla elige el suyo: `max-w-4xl` 24 · `max-w-md` 17 · `2xl` 9 · `lg` 8 · `3xl` 7 · `5xl` 5 · `7xl` 5 · `6xl` 3 · `[1100px]` · `[1400px]` · `[1600px]` · `[1800px]` |

En pantalla, los radios calculados son 12 px (979), 4 px (736), 8 px (433), 9999
px (407), 16 px (151) y 6 px (55): **seis radios** en uso para el mismo tipo de
caja.

### 1h. Componentes duplicados

**No hay biblioteca de componentes.** `components/common/` tiene `LoadingSpinner`,
`AvisoEstilo`, `AvisoRespaldo` y `ProtectedRoute`; no existe `Button`, `Input`,
`Modal`, `Card`, `Badge` ni `Tabs`. El patrón que sí se repite es la **constante de
clases copiada**: `BOTON` idéntica en 6 archivos de Observabilidad
(`TokensIngesta.tsx:25`, `MonitoreoVivoPage.tsx:36`, `ServidoresPage.tsx:34`,
`SesionesPage.tsx:19`, `SesionNuevaPage.tsx:26`, `SesionPage.tsx:27`), `CAMPO` en 4,
y `campo` en 4 de Horas (`BorrarPeriodo.tsx:107`, `PopupRegistro.tsx:141`,
`ConsultaPage.tsx:127`, `InformesPage.tsx:169`).

| Tipo | Compartido | Ocurrencias / archivos | Variantes |
|---|---|---|---|
| **Botón** | — (constante `BOTON` ×6) | 477 / 79 | **92 firmas de fondo, ~15 familias**. El primario oro tiene 26 combinaciones de tamaño y tres formas de escribir el color. Primarios en **oro, navy, indigo y azul** a la vez. **401 de 477 sin `type`** (por defecto `submit`) |
| **Campo de texto** | — (`CAMPO` ×4, `campo` ×4) | 264 inputs / 55 + 20 textareas / 15 | 50 + 14 firmas; **9 colores de foco**; 8 alturas (`py-1` … `h-16`, `min-h-[44px]`) |
| **Select** | — | 83 / 39 | 28 |
| **Tabla** | `SummaryTable` (3), `StatsTable` (solo informe) | 44 / 28; 222 `th` | 6 estilos de cabecera (navy, gris, sin fondo…); 43 firmas de `th`; `th` en `text-xl` en `Dashboard.tsx:746` y `text-base` en `SummaryTable.tsx:48` |
| **Tarjeta** | — | ~117 / 48 | 17, más **7 copias** del «hero» navy en degradado (`ClientsPage:210`, `UserList:96`, `DashboardHome:68`…) |
| **Modal** | `ExportScopeDialog` (1) | 37 overlays / 23 | 6 fondos (`black/40/50/60`, con y sin blur, navy/80, slate-950) × 4 paneles. **Solo 1 con `role="dialog"`** (`TokensIngesta`). **38 `alert()`/`confirm()` nativos** en 17 archivos |
| **Pestañas** | — | 11 implementaciones / 9 | 6 estilos (subrayado azul, navy, indigo, oro; carpeta) + 4 segmentados. **Ninguna con `role="tab"`** |
| **Aviso / banner** | `AvisoEstilo` (7), `AvisoRespaldo` (5), `AvisoDesfase` (2) | ~130 / 52 | ~50 firmas; radios `rounded`…`2xl`. **Un solo toast**, ad hoc (`Dashboard.tsx:493-530`); el resto usa `alert()` |
| **Badge / chip** | `ChipEstado` (4, solo Horas) | ~87 / 31 | ~34 |
| **Paginación** | — | 1 (`InformesPage.tsx:369`) | 1. **Las listas largas no paginan**: el Historial pinta 88 filas y 352 botones |
| **Tooltip** | `CustomChartTooltip` (solo `ReportBody`) | 20 Recharts + 132 `title=` + ~12 de hover | 4 mecanismos |
| **Carga de archivos** | — | 15 `input type=file` / 15; **5 zonas de arrastre distintas** | `UploadJTL`, `NuevaPrueba`, `ImportModal` (manipula `classList` a mano), `AIScriptDesigner`, `ChatAnalista`. `EvidencePage` y `MonitoringPage` son **casi copias** |
| **Chat** | — | 2 (`ChatAnalista.tsx:76`, `AIScriptDesigner.tsx:896`) | 2, con **los colores de usuario e IA invertidos** entre sí |
| **Progreso** | `LoadingSpinner` (4) | 99 spinners / 49; 5 barras | 28 + 4 firmas; **0 skeletons** |
| **Estado vacío** | — | ~60 / 33 | 19 |

Código muerto con interfaz propia: `script-designer/SmokeResultModal.tsx`,
`integrated/ExecutionReportSection.tsx`, `dashboard/AttachmentSection.tsx`,
`ComparisonReport.tsx`, `CapacityAnalysis.tsx` y `hooks/usePDFExport.ts` **no los
importa nadie**.

### 1i. Logos e imágenes de marca

| Ruta | Formato | Píxeles | Bytes | Uso |
|---|---|---|---|---|
| `backend/app/assets/logo-sqa.png` | PNG RGB **sin alfa** | 135×90 | 7.992 | Solo el informe de horas (`services/horas/informe.py:38,117,635`). Su fondo opaco es `#111d52`-`#111d54` (78 % de la imagen), distinto de la portada `#060B29`: se vería como un rectángulo de otro azul |
| `backend/app/assets/logo-sqa.png.webp` | WebP | 135×90 | 1.282 | **Nadie lo usa** |
| `backend/app/assets/fuentes/*.woff2` | WOFF2 | — | 17-18,6 KB | Exo 2 600/800 y Montserrat 400-700, solo informe de horas (`fuentes.py:36-45`) |
| `frontend/public/vite.svg` | — | — | — | **No existe**: favicon 404 |
| Logo del cliente | PNG ≤ 400×160 | variable | — | Tabla `client_logos`; portadas de PDF/HTML/integrado |

**En el frontend no hay ninguna imagen de marca.** El «logo» es texto:
`sqa<span class="text-sqa-gold">_</span>` en `Sidebar.tsx:351` y `Login.tsx:65`,
con el ícono `Activity` de lucide. Lo mismo en los exportadores de análisis
(`report_generator.py:1015`, `export_html.py:1244`, `integrated_report.py:636`).

### 1j. Estilos de los exportadores (leídos, no ejecutados)

**Tres paletas conviven en los documentos que ve el cliente:**

| Salida | Colores clave | Fuentes | Tamaños |
|---|---|---|---|
| **PDF de análisis** (`report_generator.py`, `export_pdf.py`) | navy `#0a1628` (cabeceras de tabla, secciones), índigo `#4f46e5` (cajas de IA), texto `#1e293b`/`#334155`, ejes `#64748b`/`#e2e8f0`, **paleta Material** en barras de título y KPI (`#4caf50 #ff9800 #9c27b0 #2196f3 #8884d8 #f44336`), degradado de portada `#0a1628→#1e293b→#1e40af`, oro `#f5a623` en la marca | `-apple-system, …, Arial` (`:660`); `'Courier New'` en números (`:887`) | pt/mm: 36 · 24 · 22 · 19 · 14 · 12 · 11 · 10,5 · 10 · 9 · 8,5 · 8 · **7,5 · 7 · 6,5 pt** (por debajo del mínimo de 8 pt de la regla 17: tablas y `th`). matplotlib 9/8 |
| **HTML de análisis** (`export_html.py`, `capas_html.py`) | `:root` con `--navy #0a1628`, `--error #ef4444`, `--success #10b981`, `--border #e2e8f0`, `--bg #f0f4f8`, `--blue #3e5aa9` **definido y sin uso**; Plotly con `CHART_COLORS`; selector de capas en oro | `-apple-system,…,sans-serif` (:1181); Plotly por defecto | 14 px cuerpo · 2 rem logo · 1,8 rem KPI · 0,75-1,2 rem |
| **Integrado** (`integrated_report.py`) | Copia del CSS del HTML con prefijo `plotly-`; pie del PDF **8 px** `#666`; `_build_exec_html` (respaldo) aún con el **estilo viejo** naranja `#fff7ed`/`#f97316` y `display:grid` en px, también en PDF | `-apple-system,…` | rem en web, pt en PDF; 8 px en el pie |
| **Informe de horas** (`services/horas/informe.py`, `graficas.py`) | Paleta D1 aprobada: `--dark #060B29`, `--navy #03287D`, `--azul #0032A7`, `--naranja #FCA311`, `--amarillo #FFC440`, `--bg #F2F5FA`, `--tinta #0E1730`, `--apagado #5C6B8A` | **Exo 2 + Montserrat incrustadas** (la única salida con tipografía propia) | pt/mm en PDF (8-40 pt); px en web (9-44 px) |

**El mismo gráfico cambia de color según la salida**: Latencia es `#8b5cf6` en el
área del PDF y `#9c27b0` en su barra de título; Errores `#ef4444` / `#f44336`; TPS
`#10b981` / `#4caf50`; Hilos `#6366f1` / `#2196f3`. Y la barra de Response Times es
`#8b5cf6` en el HTML y `#8884d8` en el PDF. Estas cifras salen de leer el código, no del navegador, así que no están en el
JSON. La paleta de horas está documentada en `docs/diseno-informe-horas.md`.

---

## 2. Auditoría en navegador

### 2.1 Alcance y protección

- **41 rutas × 7 tamaños** (834×1194, 1194×834, 1280×720, 1366×768, 1536×864,
  1920×1080, 2560×1440): desborde, recortes, texto truncado, ancho de contenido,
  estilos calculados, contraste y objetivos pequeños en cada uno. Foco con Tab a
  1366. Estados de carga y error forzados a 1366. **34 controles** abiertos (modales,
  pestañas, desplegables, edición en línea) medidos a 1366, 834 y 1920.
- **Estados simulados sin tocar datos**: «cargando» = las respuestas GET de la API
  **se retienen** (no se contestan) durante la captura; «error» = se responden con
  **500 falso** desde el propio navegador. El backend no se entera.
- **Peticiones abortadas: 223**, ninguna de la IA:

| Petición | Veces | Origen |
|---|---|---|
| `PUT /executions/{id}/analysis` | 100 | **El informe guarda al perder el foco aunque no haya cambios** (`Dashboard.tsx:74`): el recorrido con Tab lo dispara. Abortado: no se escribió nada |
| `POST localhost:3000/api/ds/query` | 111 | Las consultas internas del Grafana embebido en `/monitoring/realtime` (sus paneles salen sin datos en las capturas por eso) |
| `POST /script-designer/ai/parse-jmx` | 12 | El Editor IA lo pide al abrir un diseño (determinista, sin IA). Abortado → **el editor sale en estado de error en todas las capturas** |

  Dos sondas de depuración (localizar el texto de 8 px y listar botones) usaron el
  mismo interceptor pero **no guardaron su lista de abortadas**; una de ellas abrió
  el informe, que pudo intentar el mismo `PUT` al cerrarse. Abortado igual.
- **GET a la API**: 7.716 en 50 endpoints distintos (lista en el JSON).

### 2.2 Desborde y recortes, por pantalla y tamaño

**Ninguna pantalla produce scroll horizontal del documento** en ningún tamaño… pero
porque **`<main>` lleva `overflow-x-hidden`** (`Layout.tsx:27`): lo que no cabe **se
corta en silencio** en vez de desbordar. Eso es lo que hay que leer en esta tabla.

| Pantalla | Tamaño | Qué pasa |
|---|---|---|
| **Historial de reportes** | **834 → 1920** | La tabla mide **1.830 px** dentro de una tarjeta `overflow-hidden`: a 1366 se ven 1.028 px y **la columna de acciones (Ver, Exportar HTML/PDF, Eliminar) no se ve ni se alcanza**; a 1920 faltan 222 px; solo a 2560 cabe. `historial_1366.jpg` |
| Usuarios · Clientes · Mis Diseños IA · Historial integrado · Guardados | 834 (y 1194 en algunas) | Tablas de 843-934 px cortadas por su tarjeta `overflow-hidden` (496 px visibles) |
| Proyectos (horas) | 834 → 1366 | Tarjeta con contenido de 1.003 px cortada a 432 (834) y 964 (1366) |
| Informe de una ejecución | 834 | KPI recortados («16.65», «THROUGHPU»); tabla resumen en scroll interno 464/1.373 px; 6 recortes `overflow-hidden` |
| Informe de una ejecución | 1194 → 1536 | Tabla resumen en **scroll horizontal interno** (996 de 1.373 px a 1366) |
| Informe integrado guardado | 834 → 1536 | Igual que el informe: scroll interno 416-948 de 1.297 px |
| Script Designer con un script | 834 | `<main>` corta 957 → 546 px; el campo de URL mide 24 px de ancho; 6 recortes |
| Editor (vacío), Consulta, Informes, Diseñador IA | 834 | `<main>` corta 25-224 px de contenido |
| **Menú lateral** | **todos** | El nombre del usuario se trunca («Fredy Gabriel Boni…», 187 de 261 px). A 768 px de alto el menú no cabe y los últimos ítems quedan bajo el bloque del usuario |
| Informe / integrado | 834-1920 | El nombre del JTL se trunca en la portada (118-480 de 485 px) |
| Script Designer con script | todos | 4-6 URL truncadas (`truncate`) sin tooltip |
| Mis Diseños IA | todos | Nombres de archivo truncados a `max-w-[160px]` |

**A 834 px (tableta en vertical) el menú ocupa 288 px, el 35 % del ancho**, y `<main>`
se queda en **546 px**. No hay punto de ruptura que lo pliegue: es la causa de casi
todos los recortes de esa fila.

### 2.3 Pantallas anchas (1920 y 2560)

`<main>` mide 1.632 px a 1920 y **2.272 px a 2560**. Lo que hace cada pantalla:

| Comportamiento | Pantallas | Efecto |
|---|---|---|
| **Se estira al 100 %** (sin `max-w`) | Dashboard, Informe, Historial, Capturas, Evidencias, Informe integrado, Usuarios, Clientes, Asignaciones, Monitoreo real-time, Script Designer, Diseñador IA, Ejecución | A 2560 el contenido mide **2.183-2.224 px**: tarjetas de KPI de 640 px con un número dentro, filas de tabla con 1.500 px entre el nombre y la fecha (`general_dashboard_2560.jpg`) |
| **Se detiene en un `max-w`** | Horas (1024-1400 px), Observabilidad (1100-1600), Perfil y UserForm (672), Nuevo Reporte (1024), Config. Monitoreo (768), Historial integrado y Mis Diseños IA (1280) | Correcto, pero **alineado a la izquierda o centrado según la pantalla**: a 2560 deja 470-825 px vacíos a la derecha |
| Ancho fijo por error | Config. IA | Su contenedor oscuro ocupa todo `main` y la tarjeta interior se centra: a 2560, 737 px de oscuro vacío |

**Longitud de línea** (caracteres por línea, objetivo ≤ 75-90):

| Pantalla | 1366 | 1920 | 2560 |
|---|---|---|---|
| **Analista IA (sesión)**: los mensajes del chat | 92 | **150** | **183** |
| Sesiones de monitoreo | 78 | 142 | 142 |
| Servidores | 121 | 121 | 121 |
| Config. IA (texto de ayuda) | 118 | 118 | 118 |
| Capturas · Evidencias · Integrado | 105-110 | igual | igual |

### 2.4 Estilos calculados

Agregado de las 41 pantallas a 1366 (por pantalla, en el JSON → `rutas[].sizes`):

- Familia: Inter (pedida) → Segoe UI (real) en 5.750 nodos; monoespaciada en 112.
- 14 tamaños de letra (de 8 a 72 px) y 4 pesos.
- 55 colores de texto y 73 fondos distintos.
- 6 radios.
- 7 sombras distintas.

---

## 3. Inconsistencias

### 3.1 Cuatro identidades visuales en una misma app

| Identidad | Dónde |
|---|---|
| **Navy + oro SQA, oscura** | Login, menú lateral, pie, **Perfil** y **Configuración IA** (páginas oscuras dentro de un marco claro `bg-gray-100`) |
| **Clara con «hero» navy y cabecera de tabla navy** | Dashboard, Historial, Usuarios, Clientes, Asignaciones, informe |
| **Clara + indigo** (sin oro en ningún sitio) | Analista IA, Diseñador IA, Editor IA, Mis Diseños IA, Historial integrado |
| **Oscura slate + indigo** | Monitoreo real-time y su configuración |
| **Clara + azul**, textos **en inglés** («New Test», «History», «Start Load Test», «Configure and run load tests in real time») | Ejecución (`ExecutionDashboard`, `ScenarioForm`) |

### 3.2 Tabla de inconsistencias

| Área | Lo que hay | Ejemplos |
|---|---|---|
| Color primario | Oro, navy, indigo y azul como primario según la pantalla | `bg-[#f5a623]` (34 archivos), `bg-indigo-600` (12), `bg-[#0a1628]` (16), `bg-blue-600` (2) |
| Tokens | Definidos y evitados: 260 hex `#f5a623` frente a 68 `sqa-gold` | §1b |
| Tipografía | Inter declarada y no cargada; dos escalas (14 y 18-20 px de cuerpo); menú a 24 px | §1f |
| Botones | 15 familias, 26 tamaños del primario, 401 sin `type` | §1h |
| Formularios | 9 colores de foco, 8 alturas de campo | §1h |
| Tablas | 6 cabeceras, `th` de `text-xs` a `text-xl`, 5 paddings de celda | §1h |
| Modales | 6 fondos × 4 paneles; 38 diálogos nativos del navegador | §1h |
| Avisos | ~50 firmas; amber/yellow y green/emerald mezclados; un toast propio | §1h |
| Íconos | lucide-react en todo, pero tamaños de 3 a 14 (`w-3` … `w-14`) y colores libres | — |
| Espaciado | 141 clases distintas; 12 anchos máximos | §1g |
| Idioma | Español con y sin tildes («Configuracion», «Contrasena», «Administracion») y pantallas en inglés (Ejecución, partes del Script Designer: «Add Request», «Requests», «Import», «Smoke», «Correlate», «Debug») | — |
| Gráficas | Paleta Tailwind en pantalla, Material en las barras del PDF | §1j |
| Exportados | Tres paletas (análisis, Material, horas D1) | §1j |

---

## 4. Problemas por pantalla y tamaño

| Pantalla | Problema | Tamaño | Captura |
|---|---|---|---|
| Historial de reportes | Columna de acciones inalcanzable; 88 filas sin paginar | 834-1920 | `analisis_historial_1366.jpg` |
| Perfil | **Título «Mi Perfil» blanco sobre gris claro (1,1:1)**: invisible. Página oscura dentro del marco claro | todos | `general_perfil_1366.jpg` |
| Configuración IA | Página oscura dentro del marco claro; 737 px de oscuro vacío a 2560 | 1920-2560 | `admin_config-ia_*.jpg` |
| Informe | KPI recortados a 834; tabla en scroll interno hasta 1536; ejes a 8 px | 834-1536 | `analisis_reporte_834.jpg` |
| Informe | Guarda (`PUT`) al perder el foco aunque nada cambie | — | §2.1 |
| Analista IA (sesión) | Líneas de 150-183 caracteres; 16 botones de 16×16 | 1920-2560 | `analisis_analista-ia-sesion_*.jpg` |
| Editor IA | Sin `parse-jmx` muestra error (aquí, por el interceptor): no se pudo auditar el editor real | — | `diseno_editor-ia_*.jpg` |
| Monitoreo real-time | El Grafana embebido sin datos (POST abortados); sin entrada en el menú | — | `monitoreo_realtime_*.jpg` |
| Todas | Menú de 288 px fijo; nombre truncado; sin pliegue a 834 | 834-1194 | cualquier `_834.jpg` |
| Dashboard, Historial, Usuarios… | Estiramiento total a 2560 | 2560 | `general_dashboard_2560.jpg` |
| Ejecución | Interfaz en inglés | todos | `ejecucion_dashboard_*.jpg` |

### 4.1 Estados de carga y error

| Pantalla | Cargando | Error (500 simulado) |
|---|---|---|
| Dashboard | **Pantalla vacía** (sin indicador) | «Error al cargar estadísticas» **y las tarjetas en 0** («Total Reportes 0», «Usuarios 0»): parece un dato real |
| Historial | Vacío | «Error al cargar historial» + «0 reportes en total» |
| Usuarios · Clientes · Asignaciones | Vacío | «Error al cargar…» + «0 usuarios registrados» / «No hay clientes registrados» |
| Informe | «Cargando reporte...» | «Error al cargar el reporte. Verifique la conexión…» + **Reintentar** (el único con botón de reintentar, junto a Reporte último) |
| Analista IA (sesión) | «Abriendo la conversación…» | **Solo el texto del servidor**, sin título ni salida |
| Editor IA lista | «Cargando diseños...» | Solo el texto del servidor |
| Editor IA | «Cargando editor...» | «No se pudo abrir el editor» + mensaje + **Volver** |
| Sesión de monitoreo inexistente | Vacío | «No se pudo cargar la sesión.» |
| Monitoreo real-time · Config. monitoreo · Config. IA | Vacío | «Error al cargar configuración…» (los formularios se pintan igual, vacíos) |
| Script Designer con script | Vacío | **Redirige a `/script-designer`** sin decir por qué |
| Horas (registro, proyectos…) | Pinta la estructura | Mensaje del servidor dentro de la pantalla; el mapa del mes en 0 |
| Informes de horas | Estructura | «No se pudo generar la vista previa.» |
| Ejecución | «Loading...» | «Error loading data…» (en inglés) |

**Patrón:** al fallar, la mayoría pinta **ceros y tablas vacías** que se confunden
con datos reales. Solo el informe ofrece «Reintentar». **No hay skeletons** y la
mitad de las pantallas no tiene indicador de carga.

---

## 5. Modales, pestañas y menús (paso 2h)

34 controles abiertos sin confirmar nada. **Ningún modal desborda** el viewport ni
recorta contenido a 834, 1366 o 1920; los problemas están en la página de fondo.

| Pantalla | Control | Resultado |
|---|---|---|
| Informe | Exportar PDF | `ExportScopeDialog` (modal); contraste correcto; 3 objetivos < 24 px |
| Informe | «▶ Gráficos de Performance», «Promedio», «Hora Real» | Paneles y capas: contraste 36-48 fallos en la página (gris 400 sobre blanco) |
| Integrado guardado | Renombrar | Modal; correcto |
| Integrado guardado | «Incluye: todas las capturas» | Selector en línea; 118 fallos de contraste en la página |
| Registro de horas | Registrar horas | Modal (`PopupRegistro`); 2 fallos de contraste (gris 400) |
| Servidores | Añadir servidor | Modal; correcto |
| Clientes | Nuevo cliente · Editar | Modal; 1 fallo (`text-xs text-gray-400`) |
| Monitoreo real-time | Pantalla completa | Overlay a pantalla completa |
| Script Designer | Nuevo diseño · Import · Data Files | Modales; correcto |
| Script Designer con script | Params · Assertions · Insertar variable | Pestañas y desplegable; 6-7 textos truncados; botón rojo `#ef4444` sobre blanco 3,76:1; 14-15 objetivos < 24 px |
| Horas importar · informes | Pestañas | `#6b7280` sobre `#f3f4f6` (4,39:1) en la pestaña inactiva |
| Asignaciones | Asignar cliente | Desplegable en línea; **oro `#f5a623` sobre blanco 2,03:1** en las cifras |
| Config. IA | Google Gemini | Cambio de proveedor; gris 500 sobre `#162040` 3,3:1 |
| Ejecución | History | Pestaña; correcto salvo grises |

Detalle por control (medidas, rectángulos y capturas `*--modal-*` / `*--estado-*`)
en el JSON → `paso2_navegador.modales_pestanas_menus`.

---

## 6. Accesibilidad

### 6.1 Contraste (WCAG 2.x, 4,5:1; 3:1 en texto grande)

**723 fallos sobre 5.734 textos evaluados a 1366** (12,6 %). Los textos sobre
degradado se marcan «indeterminados» y no se cuentan (el menú y los «hero»).

| Par que falla | Pantallas | Ratio | Origen |
|---|---|---|---|
| `#64748b` sobre `#0a1628` (slate-500 en el pie y el menú) | 80 apariciones (todas) | 3,81:1 | `Footer.tsx`, separador «\|» y «SQA Kinetix Pro © 2026» |
| `#9ca3af` sobre `#f9fafb` (gray-400 en gris 50) | 65 | 2,43:1 | Celdas y metadatos de tablas |
| `#9ca3af` sobre `#ffffff` (gray-400 en blanco) | 44 | 2,54:1 | Fechas, ayudas, «sin registrar» |
| `#6b7280` sobre `#f3f4f6` (gray-500 en el fondo del marco) | 27 | 4,39:1 | Subtítulos de página |
| `#059669` sobre blanco (emerald-600) | 6 | 3,77:1 | «Grafana accesible» |
| **`#f5a623` sobre blanco (el oro de marca como texto)** | 5 | **2,03:1** | Asignaciones, Script Designer |
| `#ffffff` sobre `#f3f4f6` | 3 | **1,1:1** | **Título de Perfil** |
| `#d4891a` sobre blanco (gold-dark) | — | 2,84:1 | «Último análisis» del Dashboard |
| `#6b7280` sobre `#162040` | 3 | 3,3:1 | Ayudas de Perfil y Config. IA |
| `#ef4444` sobre blanco | — | 3,76:1 | Botones de quitar en el Script Designer |

Pantallas con más fallos: Historial (156/1.057), Integrado guardado (118/723),
Informe integrado (93/327), Informe (48/677), Config. monitoreo (21/42, la mitad de
sus textos). **El oro de marca no sirve como color de texto sobre blanco**: es una
restricción de diseño, no un error puntual.

### 6.2 Foco

- **Indicador visible**: en casi todos los controles **sí**, por el anillo por
  defecto del navegador o por `focus:ring`. Sin indicador: los campos de fecha de
  Consulta, Informes de horas e Historial integrado (los segmentos internos del
  `input type=date`). Los iframes (Grafana, vista previa del informe de horas)
  **no se pudieron evaluar**: el foco entra en otro documento.
- **Orden**: siempre **menú → contenido**: no hay enlace «saltar al contenido», así
  que con teclado hay que recorrer todo el menú (12-20 paradas) en cada pantalla.
  Diez saltos hacia atrás en el orden visual en el Informe integrado (y en el
  guardado), uno en el Script Designer y uno en el Diseñador IA. En el Diseñador IA
  el recorrido se cerró en **4 paradas** sin pasar por el menú: el modal que abre al
  entrar retiene el foco. Pantallas como el Historial tienen **375
  elementos enfocables**; el recorrido se cortó a 70.
- **Semántica**: solo 1 modal con `role="dialog"`, 0 pestañas con `role="tab"`, 12
  `role="alert/status"` sobre ~130 avisos, 29 `aria-label` en toda la app.

### 6.3 Objetivos menores de 24×24 px

**90 de 1.909** elementos interactivos a 1366:

| Pantalla | Cuántos | Cuáles |
|---|---|---|
| Analista IA (sesión) | 16 | Botones de icono 16×16 (quitar criterio, editar) |
| Script Designer con script | 15 | Iconos 14×14, enlaces de 20 px |
| Informes de horas | 13 | Casillas de 16×16 |
| Informe · Reporte último | 12 cada uno | Botones de la leyenda (`text-xs px-2 py-0.5`, 22 px de alto) |
| Asignaciones | 5 | Quitar asignación, 18×18 |
| Otros | 1-3 | Casillas de 20×20, «Refrescar modelos» de 20 px de alto |

---

## 7. Componentes a unificar (orden sugerido por impacto)

1. **Layout**: menú con pliegue por ancho, «saltar al contenido», `main` sin
   `overflow-x-hidden` ciego, y una política de ancho máximo común.
2. **Botón** (primario, secundario, fantasma, peligro, icono) con `type` explícito
   y un solo color primario.
3. **Campo, select y textarea** con una altura y un color de foco.
4. **Tabla** con cabecera única, scroll horizontal visible, columna de acciones
   fija y paginación.
5. **Modal y confirmación**, que sustituyan los 38 `alert`/`confirm` nativos, con
   `role="dialog"`.
6. **Aviso y toast**: un sistema, cuatro tonos.
7. **Estados vacío, cargando y error**, con Reintentar y sin ceros falsos.
8. **Pestañas y segmentados**, con `role="tab"`.
9. **Badge/chip**, **tarjeta** y **cabecera de página** (el «hero» copiado 7 veces).
10. **Zona de carga de archivos** (5 implementaciones) y **chat** (2).
11. **Tokens**: color, tipografía (cargada de verdad), radios, sombras, espaciado.
    Hoy el `tailwind.config.js` solo define 7 colores.

---

## 8. Lo que no se pudo auditar

| Qué | Por qué |
|---|---|
| Roles analista y visor en navegador | No hay usuarios de desarrollo para ellos; los analistas son personas reales. Cubierto desde el código (§1d) |
| Una sesión de monitoreo con datos | Hay 0; el GET de métricas escribe en la base. Se auditó el estado «no encontrada» |
| El Editor IA con un diseño abierto | Necesita `POST /parse-jmx`, abortado por la regla de solo GET |
| Los paneles de Grafana con datos | Sus consultas son `POST /api/ds/query`, abortadas |
| Estados vacíos reales | Hay datos en todas las listas; no se borró nada para provocarlos. Descritos desde el código (§1h, «Estado vacío») |
| Los exportados en ejecución | Por instrucción: leídos, no ejecutados |
| Llamadas salientes reales a OpenAI de `/ai-config/estado` y `/models/live` | Con caché en el backend; no se midió cuántas salieron |
| Foco dentro de los iframes | Otro documento |
| Una pasada final de títulos y columnas | El login 7 chocó con el límite de 5/15 min (§0.5); se hizo desde el código |

---

## 9. Inventario de información y acciones por pantalla

*(Lo que el rediseño debe conservar.)*

Salido de **leer el código** (§0.5), contrastado con las capturas. Rutas relativas a
`frontend/src/`. **[ADMIN]** = solo lo ve admin; **[DESTR]** = borra o no se puede
deshacer.

### General

**`/login` — `auth/Login.tsx`.** Marca «sqa_», lema, tarjeta «Iniciar Sesion».
Campos Usuario o Email y Contraseña. Ingresar («Ingresando...»). Aviso de sesión
expirada con cierre (:115) y error. Sin tildes.

**`/dashboard` — `dashboard/DashboardHome.tsx`.**
- Información: KPI Total Reportes, Usuarios Registrados [ADMIN], Último Análisis
  y Reportes Recientes (:85-120); estado de Grafana e InfluxDB; lista de reportes
  recientes con nombre, JTL, muestras, % error en verde/ámbar/rojo (cortes 1 % y
  5 %) y fecha (:178-218).
- Acciones: Nuevo Reporte (admin, analista), Monitoreo Real-Time, Historial y abrir
  un reporte.
- Vacío: «No hay reportes aun» con «Crear primer reporte».

**`/profile` — `profile/Profile.tsx`.**
- Información: avatar, nombre, @usuario e insignia de rol.
- Formularios: Datos personales (el usuario no se puede cambiar) y Cambiar
  contraseña (actual, nueva, confirmar). Cada uno con su alerta de éxito o error.

### Análisis

**`/performance/new` — `dashboard/UploadJTL.tsx`.**
- Entradas:
  - 6 tarjetas de tipo de prueba (nombres en inglés).
  - Cliente y Proyecto.
  - Zona de arrastre de 1-5 JTL (.jtl, .csv de Locust, .xml de WAPT).
  - Criterios globales: concurrencia, tiempo en ms y disponibilidad en %.
  - Unidad TPS o UVC.
  - Tabla «Transacciones del JTL»: selección, transacción con chip «crítica»,
    muestras, promedio, TPS, errores y criterios propios por fila (:638-673).
- Acciones:
  - Seleccionar o quitar archivos; marcar todas, la sugerencia o ninguna.
  - **Generar Reporte**.
  - Modal de compatibilidad, con «Continuar de todas formas».
  - Panel «IA no disponible», con «Generar sin IA» (`AvisoRespaldo.tsx:214`).
- Estados: «Procesando N archivo(s)…», «Detectando transacciones…» y los errores
  de tipo y de número de archivos.

**`/performance/analista(/:id)` — `AnalistaIAPage.tsx` + `analista/*`.**
- Sin sesión: «Nueva prueba» (cliente, proyecto, tipo, JTL) y «Retomar una
  conversación».
- Con sesión:
  - Cabecera cliente · proyecto · tipo · unidad.
  - Chat de 2.000 caracteres (Ctrl+Enter) con respuestas rápidas y adjuntar CSV/XML
    de errores.
  - **Ficha del informe** («Listo para generar: n de m»): la prueba, criterios,
    lo que contaste, detalle de errores, transacciones con informe propio y el
    bloque opcional.
  - MiniGráfico de usuarios frente a fallos.
- Acciones: **Generar informe**, Cambiar datos de la prueba (modal), Nueva
  conversación, y quitar o editar criterios y elementos del relato.
- Estados: «Esta conversación no existe o no es tuya», «La IA está leyendo tu
  mensaje…» y conversación cerrada tras generar.

**`/performance/report/:id` — `Dashboard.tsx` ⚠ + `ReportBody`, `SummaryTable`, `TransactionReportSection`, `ExportScopeDialog`, `AvisoRespaldo`.**
- Información:
  - **Cabecera**: realizado por, generado, cliente, proyecto, duración, tipo,
    **veredicto** (APTO / NO APTO), archivo, inicio y fin.
  - Franja de respaldo.
  - **KPI**: Total Requests, Avg RT, Error Rate, Throughput, P50, P90, P95 y P99.
  - **Veredicto por transacción**.
  - **Tabla resumen** de 14 columnas (:47-60).
  - Redirecciones.
  - **Análisis de errores**: distribución de códigos y detalle por transacción.
  - **6 gráficas**: Response Times (con capas), Latency, Error Rate, Response
    Codes, TPS y Active Threads.
  - **Textos de IA editables** tras cada sección, más Conclusiones y
    Recomendaciones.
  - **Un bloque por transacción**, con progreso de generación.
- Controles: tiempo transcurrido / hora real; capas Ambas · Promedio · Máximo;
  leyenda que oculta series; zoom del eje Y.
- Acciones:
  - Generar o Regenerar por transacción.
  - Indicador de autoguardado con Reintentar.
  - Guardar todos los cambios.
  - **Exportar HTML/PDF** → diálogo «¿qué incluyo?» (general o general más
    transacciones, por casillas), con «Exportar igualmente» si hay secciones sin IA.
  - Ver el error del proveedor.
- Estados: cargando; error con Reintentar y «Volver al historial»; «No se
  encontraron datos»; toast del modelo usado; `alert()` al guardar o al fallar el
  PDF.
- Idioma: KPI y títulos de gráfica en inglés; las secciones, en español.

**`/performance/history` — `performance/History.tsx`.**
- Tabla: Fecha, Tipo, Cliente, Proyecto, **Origen del texto** (marca si hay
  secciones sin IA), Archivo JTL, Muestras, Error %, Avg RT, TPS, Contenido
  (reporte, n.º de métricas, n.º de evidencias) y Acciones.
- Filtros: búsqueda; tipo, cliente y proyecto; «Con secciones sin IA (N)».
- Acciones: Ver, Exportar HTML, Exportar PDF y **Eliminar [ADMIN][DESTR]**, con
  modal de confirmación propio.

**`/performance/monitoring` y `/performance/evidence` — `MonitoringPage.tsx`, `EvidencePage.tsx` (casi copias).**
- Pasos: 1. ejecución, 2. adjuntar (categoría y título).
- Contenido: tarjetas de imagen con análisis IA editable y el «Análisis global».
- Acciones:
  - Adjuntar, «Analizar Todas (n/m)» y analizar o editar por tarjeta.
  - **Eliminar adjunto [ADMIN][DESTR]** (`confirm` nativo).
  - Generar el análisis global.
- Categorías:
  - Monitoreo: CPU, Memoria, BD, APM, Red/I/O, Logs, Otro.
  - Evidencias: Screenshot de error, Log, Hallazgo, Configuración, Otro.

**`/performance/integrated(/:id)` — `IntegratedReportPage.tsx` + `integrated/*`.**
- Construcción:
  - Historial disponible: + Reporte, + Monitor (n), + Evidencia (n).
  - Secciones arrastrables, con «Incluye:» por sección.
  - Renombrar (modal).
  - **Generar Informe Integrado**.
- Informe:
  - El informe individual embebido por ejecución.
  - Capturas con su análisis.
  - **Análisis consolidado** (Generar o Regenerar; si hay ediciones, modal
    «Regenerar y reemplazar» [DESTR]).
  - Exportar HTML/PDF con aviso de secciones sin IA.
  - Autoguardado con Reintentar.
  - Banner de copia local: «Recuperar y guardar» o «Descartar».

**`/performance/integrated/history` — `IntegratedReportsHistory.tsx`.**
- Tabla ordenable: Nombre, Secciones, Estado (Consolidado o Borrador), Trabajo
  guardado, Contenido, Creado, Modificado y Acciones.
- Filtros: nombre, fechas y estado.
- Acciones: Nuevo, Ver, Renombrar y **Eliminar [ADMIN][DESTR]** (modal).

### Horas

**`/horas/registro` — `RegistroPage.tsx` + `CalendarioMes`, `PopupRegistro`.**
- Información:
  - KPI: Jornada del mes, Registradas, Horas extra y Días pendientes.
  - **Calendario** con estado por día: fin de semana, festivo, ausencia, faltan X
    h y extra.
  - Detalle del día: chips y total x / jornada.
  - Tabla del día: proyecto, actividad, horas, marcas y acciones.
- Entradas:
  - Persona (solo el admin la cambia) y navegación por mes.
  - Popup: fecha, cliente → proyecto → actividad en cascada; horas en pasos de
    0,25; facturable o no; extra; observaciones.
- Acciones:
  - Registrar.
  - Editar (admin o el dueño).
  - **Borrar [ADMIN][DESTR]** (`confirm`).
  - En el popup: «Guardar y añadir otra».

**`/horas/consulta` — `ConsultaPage.tsx`.**
- Información:
  - KPI del rango.
  - **Tabla de tres niveles**: proyecto (estado, en el rango, estimadas,
    consumidas, restantes y barra de consumo) → persona → registros.
  - Aviso de desfasados con «Ver solo los desfasados».
- Filtros: fechas, cliente, proyecto, persona y «incluir finalizados y no
  viables».

**`/horas/proyectos` — `ProyectosPage.tsx` + `EstadoProyecto`.**
- Lista: cliente, proyecto, **estado** (selector de 5; «No viable» y «Finalizado»
  son [ADMIN]), estimadas, consumidas y consumo.
- Detalle:
  - Actividades con su total.
  - Historial de estados e historial de estimaciones.
  - Renombrar.
  - Añadir actividad.
  - **Quitar actividad [DESTR]**.
- Alta: «Proyecto nuevo», con las horas estimadas de cada actividad.

**`/horas/actividades` — `ActividadesPage.tsx`.**
- Tabla: actividad, n.º de proyectos y estado.
- Acciones: Crear, Renombrar en línea, Desactivar/Activar y **Borrar
  [ADMIN][DESTR]** (deshabilitado con su motivo si no eres admin).

**`/horas/importar` — `ImportarPage.tsx` + `ImportarProyectos`, `BorrarPeriodo`.**
- Pestañas «Registros de horas» y «Proyectos y estimaciones».
- Flujo: archivo y persona → «Ver qué va a pasar» → previa por bloques →
  «Importar N filas».
- Plantilla descargable.
- **Borrar un periodo [ADMIN][DESTR]**:
  - Previa por persona.
  - Comando de copia.
  - Casilla «Ya hice la copia».
  - Frase tecleada.
  - Botón rojo.

**`/horas/informes` — `InformesPage.tsx`.**
- Pestañas: Vista previa (iframe PDF/HTML, paginada), Actividades por proyecto,
  Mensual por persona y Ocupación y facturación.
- Filtros: fechas, cliente, proyecto, solo facturables, «Dirigido a», personas y
  secciones del documento.
- Acciones: descargar PDF o CSV, modo PDF/HTML, Rehacer y paginación.

### Observabilidad

**`/observabilidad/sesiones` — `SesionesPage.tsx`.**
- Tarjetas: nombre, estado, cliente · proyecto · servidores, y fechas.
- Aviso de token de lectura con campo para pegarlo.
- Filtro por cliente.
- Acciones: Nueva sesión, Ver y **Borrar [DESTR]**: `confirm`, **sin límite de
  rol**.

**`/observabilidad/sesiones/nueva` — `SesionNuevaPage.tsx`.**
- Asistente de 3 pasos:
  1. Nombre, cliente, proyecto y servidores.
  2. «Conecta tu JMeter»: el `.jmx` con el listener puesto, o la tabla de
     parámetros con Copiar.
  3. Ver la sesión.

**`/observabilidad/sesiones/:id` — `SesionPage.tsx`.**
- Métricas de la prueba y una sección por servidor, con sus gráficas.
- Rango: 15 min, 1 h, 3 h o 12 h.
- Controles: En vivo/Pausado, refrescar y **Terminar sesión** (sin confirmación).

**`/observabilidad/servidores` — `ServidoresPage.tsx` + `TokensIngesta`.**
- Lista de servidores: tipo, modo, dirección, usuario, credencial guardada o no, y
  notas.
- Alta y edición en modal: cliente, nombre, tipo, modo, dirección, puerto,
  usuario, BD o notas, credencial y activo.
- Por servidor: **Probar conexión** y **Generar configuración** (modal con el
  comando y Copiar).
- **Dar de baja [DESTR]**.
- Tokens de ingesta:
  - **Crear [ADMIN]**: modal de un solo uso.
  - **Revocar [ADMIN][DESTR]**.
- Token de InfluxDB [ADMIN].

**`/observabilidad/vivo` — `MonitoreoVivoPage.tsx`.**
- Cliente y proyecto → Generar configuración.
- Resultado: nombre de la corrida, la tabla del Backend Listener con Copiar y
  ver/ocultar el token, y el **Grafana embebido** con rango y refresco.

### Monitoreo (sin entrada en el menú)

**`/monitoring/realtime`.**
- Estado de Grafana e InfluxDB, Grafana embebido, rangos de 5 min a 24 h y
  refresco automático.
- Controles: recargar y pantalla completa.
- Estado: «Monitoreo no configurado».

**`/monitoring/settings` [ADMIN].**
- Grafana: URL y UID.
- InfluxDB: URL, org, bucket y token cifrado.
- Acciones: Guardar y Probar conexión.

### Administración [ADMIN]

**`/users`.**
- Tabla: usuario, email, rol (en inglés), estado y creado.
- Búsqueda.
- Acciones: Nuevo, Editar, **Desactivar** (sin confirmación) y **Resetear
  contraseña** (modal). No hay borrado.

**`/users/new`, `/users/:id`.** Nombre, usuario, email, contraseña, rol (Admin,
Analyst, Viewer) y estado. Acciones: Cancelar, Crear o Actualizar.

**`/admin/clients`.**
- Tabla con logo, descripción, contacto, email y estado (la insignia cambia el
  estado al pulsarla).
- Modal de alta y edición con **logo** (PNG, JPG o WebP de hasta 2 MB).
- **Eliminar [DESTR]**: modal propio («y todas sus asignaciones»).

**`/admin/assignments`.**
- KPI.
- Una tarjeta por usuario, con chips de cliente.
- Acciones: Asignar y **Remover [DESTR]** (sin confirmación).

**`/admin/ai-config`.**
- Proveedor, modelo (con «Modelos en vivo» y Refrescar), **esfuerzo de
  razonamiento**, API key, activo y límites diario y mensual.
- Barras de consumo.
- Acciones: Probar conexión (**llama a la IA**), Guardar y **Resetear contadores**
  (sin confirmación).

### Diseño y ejecución

**`/script-designer(/:id)` — `ScriptDesigner.tsx` ⚠ + `script-designer/*`.**
- Barra: nombre y Saved/Error.
- Izquierda: pestañas Requests (N) y Variables (N), con 6 tipos de variable.
- Derecha: `RequestEditor` con Request, Params, Assertions, Extractors y Result;
  dentro, URL, método, headers, body con más de 30 generadores y query params.
- Resultado: `JMeterResultDetail` e historial de ejecuciones.
- Acciones:
  - Scripts Guardados: asistente de 3 pasos.
  - **Import**: HAR, Postman, OpenAPI, WSDL o extensión de Chrome.
  - Data Files (borrar [DESTR]).
  - Smoke.
  - **Correlate** y **Debug** (IA, con modal).
  - **Limpiar [DESTR]**, con confirmación en línea.
  - JMX y Guardar.
  - Add request.
- Idioma: **muy mezclado**.

**`/script-designer/history` — `ScriptHistory.tsx`.** Tabla: nombre, cliente,
tipo, origen, requests, actualizado y Abrir. Filtros. Sin borrado.

**`/ai-script-designer` — `AIScriptDesigner.tsx`.**
- Chat y «Preview JMX» (Válido o Inválido, más la lista de componentes).
- Adjuntar HAR, Postman o Swagger.
- Modales: elegir cliente, guardar diseño, cambiar cliente y «¿Continuar diseño
  anterior?» (aparece al entrar).
- Acciones: Generar, Generar desde archivos o Refinar; Abrir en Editor IA;
  Guardar como; Nueva conversación; Descargar JMX.

**`/ai-script-designer/history` — `AIDesignerHistory.tsx`.**
- Tabla ordenable: nombre, cliente, borrador o guardado, mensajes, JMX,
  referencia y modificado.
- Filtros.
- Acciones: Nuevo, Abrir, Abrir en Editor IA y **Eliminar [ADMIN][DESTR]**.

**`/ai-script-editor` — `AIScriptEditorList.tsx`.** Diseños con JMX. Acciones:
Descargar JMX y Editar.

**`/ai-script-designer/editor/:id` — `AIScriptEditor.tsx` (7.375 líneas).**
- Árbol JMX con buscador.
- Panel de detalle con un editor por tipo de elemento: Thread Group con gráfico
  de carga, sampler HTTP, headers, aserciones, 4 extractores, 3 timers, CSV,
  defaults, cookies, caché y data files.
- Visor de listeners: Summary, Aggregate, View Results Tree y 6 gráficas.
- Panel e historial de ejecución.
- Acciones:
  - Ejecutar (modal «Esto NO es un smoke test»).
  - Smoke y Pedir a IA.
  - Ver XML.
  - Añadir, activar o **eliminar** elementos.
  - **Detener ejecución**.
- Hay textos de pantalla a medias: «Edición disponible próximamente», «vendrán en
  Sprint 2.6».

**`/execution-dashboard` — `ExecutionDashboard.tsx` + `execution/*`.**
- Pestañas New Test y History.
- Formulario: tipo, script, nombre y **perfil de carga** de 8 parámetros.
- **Live Metrics**: VUs, TPS, RT, errores y 3 gráficas.
- Historial con Download JTL y Generate Report.
- Acciones: Start, Pause/Resume y **Stop** (sin confirmación).
- **Todo en inglés.**

### Transversal

- **Confirmar un borrado** se hace de tres formas: `confirm` nativo, modal propio
  y confirmación en línea.
- **Acciones destructivas sin confirmación**: Stop, Terminar sesión, Resetear
  contadores, Remover asignación, y desactivar un usuario o un cliente.
- **Se repiten en varias pantallas, y deben sobrevivir al rediseño**:
  - El aviso de textos que no escribió la IA (franja, rótulo por sección, panel
    «IA no disponible», aviso tras generar y al exportar).
  - El indicador de autoguardado con Reintentar.

