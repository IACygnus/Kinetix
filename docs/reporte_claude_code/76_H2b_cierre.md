a2c3ee3 · 2026-09-17

# ETAPA H2b — Cierre: el registro por calendario

**0 llamadas a la IA en toda la etapa.** El módulo de horas no las usa.

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **H-D23** | Calendario mensual con navegación, «Hoy» y leyenda | Hecho |
| **H-D24** | Cada casilla dice su estado: completo, incompleto, festivo, fin de semana | Hecho, con color **y con palabras** |
| **H-D25** | Detalle del día elegido, debajo del calendario | Hecho |
| **H-D26** | Popup de registro: franja del día, fecha editable, encadenado, facturable explícito, «Guardar y añadir otra» | Hecho |
| **H-D27** | «Desfase», no «exceso», en todo el producto | Hecho y **comprobado en las tres pantallas** |
| **H-D28** | Alerta de desfase en Proyectos | Hecho: listado, cabecera y por actividad |
| **H-D29** | Botones de 44 px, `<label>` en cada campo, formato español | Hecho |
| **H-D30** | La especificación pasa a v1.1 | Hecho, con su tabla de versiones |
| **La vista semanal se retira** | «Es la única vista… no convive con ella» | Retirada entera |
| **El backend de H2 se conserva** | No se rehace nada de H2 | Cumplido: `/time/week` sigue en uso |

---

## 2. Los sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| H2b.1 La especificación a v1.1 | 73 | `ca80f4a` |
| H2b.2 Backend: el mes y el desfase | 74 | `b65f4b4` |
| H2b.3, H2b.4 y H2b.5 Pantalla, alerta y validación | 75 | `a2c3ee3` |
| H2b.6 Cierre | 76 (este), 77 | — |

---

## 3. Lo que se construyó

**Backend** — dos piezas nuevas y ninguna columna nueva en la base:

- `services/horas/desfase.py` (93 líneas): los tres estados de §5.1 en un solo
  sitio, con sus bordes declarados.
- `GET /time/month`: el mes casilla a casilla, reusando `calendario.py`.
- Cuatro campos **añadidos** a proyectos y actividades (`consumed_pct`,
  `overrun_status`, `overrun_hours`, `overrun_label`): el contrato que cerraron
  H1 y H2 no cambia.

**Frontend** — la pantalla se parte en tres y **baja de 546 a 335 líneas**
haciendo más cosas:

- `pages/horas/RegistroPage.tsx`: decide qué se carga y qué se ve.
- `components/horas/CalendarioMes.tsx`: pinta la rejilla y la leyenda.
- `components/horas/PopupRegistro.tsx`: registra y edita, un solo formulario.
- `components/horas/AvisoDesfase.tsx`: el aviso de §5.1, compartido por las dos
  vistas de Proyectos.

---

## 4. Verificación — 138 comprobaciones propias, todas pasan

| Prueba | Qué mira | Resultado |
|---|---|---|
| `test_horas_desfase.py` | 26 tests: el porcentaje, los cuatro bordes, las horas de más y la etiqueta | 26 pasan |
| `test_horas_calendario.py` | 6 nuevos sobre el futuro y lo que no se reclama (+29 de H2 intactos) | 35 pasan |
| `h2b2_backend.py` | 53 por HTTP: el mes con festivo, día incompleto, extras y desfase; los tres estados en proyectos | TODO PASA |
| `h2b5_pantalla.py` | 53 de punta a punta en la pantalla real, en 10 bloques | TODO PASA |

### El resto del producto no se movió

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — diez pasos, **cuatro salidas** | **LAS CUATRO SALIDAS PASAN** |
| `h15_pantallas.py` (H1) | TODO PASA |
| `h22_backend.py` (backend de H2) | TODO PASA |
| `pytest tests/` | **582 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |

`h24_pantalla.py`, que conducía la vista semanal, **ya no aplica**: lo sustituye
`h2b5_pantalla.py` sobre el calendario. Es la consecuencia buscada de retirar esa
vista, no una regresión.

---

## 5. Las decisiones técnicas de la etapa

| Decisión | Justificación |
|---|---|
| **El desfase en un solo módulo** (`desfase.py`) | lo necesitan el listado, el detalle y mañana los reportes; escrito tres veces daría tres respuestas para el mismo proyecto |
| **El 90 % exacto ya avisa** | el aviso llega al llegar al umbral; si no, el umbral no sirve |
| **El 100 % exacto NO es desfase** | consumir justo lo estimado es cumplir, no pasarse |
| **Sin estimación no hay desfase** | los proyectos que crea la importación (§6.2.4) nacen sin horas: no hay contra qué compararlos, y dividir por cero habría tumbado el listado |
| **`hoy` opcional en `construir_dias`** | recorta el futuro donde hace falta sin cambiar lo que H2 tenía validado; sus 29 tests siguen pasando sin tocarlos |
| **`esperadas` y `se_reclaman` separadas** | la jornada que le tocaba a un festivo sigue siendo un dato útil; lo que no puede es sumarse al total del mes |
| **El detalle del día se pide a `/time/week`** | es el único sitio donde vienen los registros completos; un endpoint nuevo para un solo día habría sido una definición más que mantener |
| **Registrar y editar, el mismo popup** | mismos campos; dos formularios se separan al primer cambio |
| **«Facturable» ya no se hereda** | v1.1 pide elegirlo; se gana un clic y se pierde una facturación equivocada por inercia |
| **Los nombres internos `over_estimate` se conservan** | lo que Fredy pidió cambiar es lo que se lee, no lo que se llama por dentro; renombrarlos habría tocado el contrato cerrado de H1 y H2 |
| **El panel de pendientes desaparece** | en un calendario, los días pendientes son las casillas ámbar y el enlace de §4.2.6 es pulsarlas |

---

## 6. Tres defectos que la etapa destapó, y se arreglaron

Los tres venían de H2 y ninguno se veía en una vista semanal.

1. **El resto del mes salía en rojo.** `dias_pendientes` sabía no listar el
   futuro, pero el día en sí no lo sabía: un calendario abierto el día 1 habría
   pintado el mes entero como incompleto. La regla sube al día, junto a las otras
   tres.
2. **Un festivo sumaba su jornada al total del mes.** 185 h esperadas en un
   septiembre que solo pide 177.
3. **El detalle de un proyecto decía «En rango» de un proyecto desfasado.** El
   estado se calculaba por actividad pero no para el proyecto entero.

---

## 7. Lo que NO se tocó

- Ningún archivo protegido (§11 de CLAUDE.md).
- Ningún compose, ningún servidor, ningún despliegue.
- Ninguna columna nueva: los cuatro campos de desfase se calculan.
- El módulo de análisis, entero.
- El botón que pliega la barra lateral mide 24 px y es el único de la página por
  debajo de 44; es de `layout/Sidebar.tsx`, lo comparten todas las pantallas de
  Kinetix y arreglarlo se sale de esta etapa. **Queda anotado.**

---

**Estado: Etapa H2b implementada, pendiente validación de Fredy.**
