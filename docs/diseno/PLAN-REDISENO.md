# Plan del rediseño de la interfaz de Kinetix

> **Léase entero antes de empezar cualquier etapa.** Fredy aprobó un mockup
> navegable que redefine toda la interfaz: `docs/diseno/kinetix-mockup.html`. Se
> lleva al frontend real (React 18 + TypeScript + Vite + Tailwind 3.4) por
> etapas. El sistema de diseño que sale de él está en `docs/DESIGN_SYSTEM.md`.
>
> Es un rediseño **visual**. No cambia lógica de negocio, flujos, llamadas a la
> API, estados ni datos. No se toca el backend ni los exportadores (PDF, HTML,
> integrado). Si algo del mockup necesita un dato que la API no entrega, **no se
> inventa**: se omite y se anota en el reporte.

---

## 1. Cómo leer el mockup

- Solo vale la variante **`data-dir="i"` (Índigo)**. Las reglas `[data-dir=s]` y
  `[data-dir=t]` y las ramas de JS `S.dir==="s"` / `"t"` son de versiones
  descartadas.
- Tokens: `[data-dir=i],[data-dir=i] .light{…}` (claro),
  `[data-dir=i][data-theme=dark]{…}` (oscuro), `[data-dir=i]{…}` (tipografías y
  radios). Ya están en `frontend/src/styles/tokens.css`.
- Armazón: bloque «Armazón de Telemetría aplicado a Índigo». Ya está hecho.
- Movimiento: bloques `zz-motion` (CSS y JS) y `AFTER.login`. Ya están en
  `LoadFx` y en el sistema de movimiento.
- **Es solo del prototipo y NO se implementa**: la barra oscura «Prototipo
  Kinetix», las etiquetas `[DATO SIMULADO]`, «Mapa de pantallas», «Tokens y
  contraste», «Recorrido guiado», los selectores de rol, estado y tamaño de letra
  y los datos de `DB`.
- Cada pantalla del mockup tiene su bloque de CSS (`/* ===== admin ===== */`,
  `analisis-a`, `analisis-b`, `diseno`, `horas`, `observ`) y su vista en JS
  (`V["<id>"]`). Para leerlo sin el base64 de las fuentes, quitar los `data:` con
  un script antes de abrirlo como texto.

## 2. Reglas que no se negocian

1. **Rama.** El trabajo vive en `rediseno-ui`. Cada etapa trabaja en una **rama
   temporal** `rediseno-ui-eN` en un `git worktree` **fuera** de `./frontend`
   (ver §4), y Fredy aprueba antes del avance rápido de `rediseno-ui`. Push solo
   con `git push github rediseno-ui`. **Nunca** `git push origin`.
2. **Respaldo** `.bak_rediseno-eN_<fecha-hora>` junto a cada archivo antes de
   modificarlo (`.gitignore` ya ignora `*.bak_*`).
3. **Protegidos**: no se tocan `Dashboard.tsx`, `ScriptDesigner.tsx`,
   `jtl_parser.py`, `report_generator.py`, `export_html.py`, `export_pdf.py` ni
   `AIScriptEditor.tsx` (7.375 líneas). Van en la última etapa y solo con
   autorización expresa de Fredy.
4. **Todo estilo sale de tokens.** En los archivos nuevos o migrados no puede
   quedar ningún hex, `rgb()` con números, valor arbitrario de Tailwind
   (`bg-[#…]`, `text-[11px]`) ni clase de la paleta por defecto (`bg-indigo-600`,
   `text-gray-500`, `bg-white`). Las pantallas que aún no se migran conservan sus
   clases: **la paleta de Tailwind no se retira** hasta la última etapa. Lo
   comprueba `tools/check_tokens.py`, cuyo `ALCANCE` amplía cada etapa.
5. **Sin dependencias nuevas.** No se modifica `package.json`. El movimiento es
   CSS y `<canvas>` propios. **No hay Node en el equipo anfitrión**: todo `npm`,
   `tsc` y `vite` se ejecutan dentro de `jmeter_frontend`.
6. **Fredy controla `docker compose build frontend`.** No se reconstruyen ni
   reinician contenedores.
7. **Cero llamadas a la IA.** En las pruebas de navegador se aborta toda petición
   que no sea GET (salvo el POST de `/auth/login`) y no se pulsa Generar,
   Analizar, Regenerar, Guardar ni Eliminar. **Un solo inicio de sesión por
   corrida**, reutilizando el estado guardado: el límite es 5 cada 15 minutos.
8. **Accesibilidad WCAG 2.2 AA**: contraste, foco visible, teclado completo,
   objetivos ≥ 24 px, `role="dialog"` en modales, `role="tab"` en pestañas,
   «Saltar al contenido». Todo movimiento se detiene con la pausa y con
   `prefers-reduced-motion`.
9. **Nada se oculta ni se corta entre 834 y 2560 px** de ancho.
10. **Español con tildes** en todo texto nuevo. Los términos del oficio (JTL,
    JMX, TPS, Smoke, Thread Group) no se traducen.
11. No se toca, mueve ni versiona nada fuera de lo que nombra el prompt de la
    etapa; tampoco otras carpetas de reportes.
12. **Se decide y se avanza en lo técnico**, con una línea de justificación por
    decisión. Se para y se pregunta solo por: decisión de producto fuera del
    mockup, archivo protegido, hallazgo que cambie el plan o bloqueo real.

Y las del proyecto que más tocan aquí (`CLAUDE.md` §13): diagnóstico de solo
lectura antes de escribir (regla 2), aviso si la etapa pasa de 3 archivos o 50
líneas (regla 4), hooks de React antes de cualquier `return` (regla 16), la
validación visual de Fredy como único criterio de éxito (regla 9), reportes
numerados en `docs/reporte_claude_code/` (regla 19) y **nunca editar el frontend
mientras Fredy tiene la aplicación abierta** (regla 31): por eso el worktree.

## 3. Etapas

| Etapa | Pantallas | Estado |
|---|---|---|
| 0 | Tokens, tipografías, biblioteca base, armazón, inicio de sesión | **Hecha** (reportes 155-156), pendiente de la validación de Fredy |
| 1 | Perfil, Usuarios y su formulario, Clientes, Asignaciones, Configuración IA | Pendiente |
| 2 | Dashboard de inicio, Historial de reportes, Historial integrado, Guardados, Mis Diseños IA, lista del Editor IA | Pendiente |
| 3 | Horas (6) y Observabilidad (5), Monitoreo (2) | Pendiente |
| 4 | Analista IA, Nuevo Reporte, Capturas de infraestructura, Evidencias, Informe Integrado | Pendiente |
| 5 | Diseñador IA, Ejecución | Pendiente |
| 6 | Protegidos: informe (`Dashboard.tsx`), Script Designer, Editor IA. **Solo con autorización de Fredy** | Pendiente |

En **cada** etapa:

- **Un commit por pantalla migrada.**
- Los `alert` / `confirm` nativos que toque (38 en total, auditoría 153 §1h) se
  sustituyen por `ConfirmDialog` o `Toast`.
- Los estados de error **dejan de mostrar ceros** como si fueran datos:
  `ErrorState` (con Reintentar) en lugar de los indicadores y tablas; `Kpi` con
  `valor={null}` pinta «—».
- La pantalla migrada **sale de `.tema-claro`** (ver `DESIGN_SYSTEM.md` §2.2) y
  se añade a `ALCANCE` de `tools/check_tokens.py`.
- Se conserva todo lo que el inventario de la auditoría dice de esa pantalla
  (`docs/reporte_claude_code/153-auditoria-ui.md` §9).

## 4. Cómo se trabaja sin tocar la pantalla de Fredy

`jmeter_frontend` sirve `./frontend` con `vite dev` y recarga con cada guardado:
cualquier edición en la copia de trabajo de Fredy le cambia la pantalla al
instante (regla 31). Por eso, el método de la Etapa 0:

1. **Worktree** en una rama temporal, en la carpeta temporal de la sesión:
   `git worktree add -b rediseno-ui-eN <tmp>/wt-eN rediseno-ui`.
2. **Compilación aislada** dentro del contenedor, sin tocar `/app`: copiar el
   `frontend` del worktree (sin `node_modules`) a `/tmp/eN`, enlazar
   `node_modules` → `/app/node_modules`, y ejecutar allí `tsc` y
   `vite build --outDir /tmp/eN/dist`. `VITE_API_BASE_URL` ya está en el entorno
   del contenedor (`http://localhost:8001/api/v1`): el build apunta al 8001 real.
   Con Git Bash hace falta `MSYS_NO_PATHCONV=1` para que `docker exec -w /tmp/…`
   no reciba una ruta de Windows.
3. **Vista previa**: copiar `dist` al anfitrión y servirlo con un servidor
   estático que devuelva `index.html` en cualquier ruta (SPA), en un puerto
   propio (5190). Chromium se lanza con
   `--host-resolver-rules=MAP localhost:5173 127.0.0.1:5190`: la página cree estar
   en `localhost:5173`, así que CORS y las cookies funcionan contra el 8001.
4. **Verificación**: `C:\proyectos\kinetix-audit-tools\etapa0.py` (armazón,
   login, menú por rol, pantallas sin migrar, mockup) y `etapa0_galeria.py` (la
   biblioteca base en una galería temporal que se compila aparte en `/tmp/e0` y
   nunca entra al repositorio). Sirven de plantilla para las siguientes etapas.
5. **Parada única al final**: reportes y capturas a Fredy. Solo cuando él
   aprueba: `git merge --ff-only rediseno-ui-eN` en su copia y
   `git push github rediseno-ui`.

## 5. Deuda conocida que el rediseño hereda

- **El visor ve dos ítems que lo devuelven al inicio**: «Nuevo Reporte» e
  «Historial Integrado» (sus rutas exigen admin o analista). Se dejó así a
  propósito en la Etapa 0, por decisión de Fredy; está anotado en
  `navegacion.ts`.
- `Sidebar.tsx` y `Footer.tsx` siguen en el árbol **sin importar** hasta que
  Fredy valide el armazón; después se borran.
- El aviso de sesión expirada vive en `AuthContext.tsx` y sigue sin tildes
  («Tu sesion se cerro…»): no era de la Etapa 0.
- El favicon (`/vite.svg`) no existe: 404 desde antes del rediseño.
- Las pantallas que abren un modal propio al entrar (Script Designer, Diseñador
  IA) lo pintan con `z-50` por encima de la cabecera, como antes.
- `ExecutionDashboard.tsx` tiene una tarjeta `sticky top-4` que, con la cabecera
  fija de 60 px, se mete debajo al desplazar. Se corrige al migrarla (Etapa 5).
