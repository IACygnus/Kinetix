fe1394d · 2026-09-17

# ETAPA H2b.1 — La especificación de horas pasa a v1.1

**0 llamadas a la IA. Solo documento**: no se tocó ni una línea de código.

---

## 1. Qué cambió

`docs/ESPECIFICACION-horas.md` → **v1.1**. Ocho puntos del diff, todos dentro de H-D30.

### §4.1 — el calendario sustituye a la vista semanal

Se reescribió entero. Lo que antes eran tres líneas describiendo una vista por semana ahora
describe las tres piezas del diseño aprobado:

- **El calendario mensual**, con la tabla de estados por casilla (completa, incompleto, sin
  registro, festivo **con su nombre**, fin de semana, día seleccionado), navegación por mes,
  botón «Hoy», leyenda y el resumen del mes encima.
- **El detalle del día seleccionado** debajo, con su tabla y el total frente a la jornada.
- **El popup de registro**, con la franja de jornada, la **fecha editable**, los selectores
  encadenados con las horas restantes a la vista, **Facturable / No facturable como dos
  opciones explícitas** y los tres botones, incluido **«Guardar y añadir otra»**.

La primera frase deja escrito que **la vista semanal se retira y no convive**: la
justificación —dos formas de hacer lo mismo confunden— queda en el documento, no solo en el
prompt.

### §4.2.4 — «desfase», no «exceso»

La regla conserva lo que ya decía —avisar, permitir guardar, marcar— y añade el párrafo que
fija la palabra:

> **Se dice «desfase», no «exceso».** Un registro se marca *«Desfase +1,0 h»* y un proyecto
> queda *«Desfasado +9,0 h»*. La palabra describe el proyecto —va por encima de lo
> estimado—, no culpa a quien registró las horas.

La razón está escrita, que es lo que la hace defendible cuando alguien pregunte por qué no se
llama «exceso».

### §5.1 — las alertas de desfase

Sección nueva, con la tabla de los tres estados y sus umbrales:

| Estado | Cuándo |
|---|---|
| **En rango** | por debajo del 90 % |
| **Por agotarse** | entre el 90 % y el 100 % |
| **Desfasado +X h** | por encima del 100 % |

Más las filas resaltadas, el aviso con cuántos proyectos están desfasados, el filtro para ver
solo esos, y **el mismo estado por actividad dentro del detalle** — porque saber que un
proyecto va mal sin saber qué actividad lo está tirando no sirve de mucho.

### Las otras cuatro

- **§5** y **§7.2**: las dos menciones sueltas de «exceso» pasan a «desfase». Ya no queda
  ninguna en el documento salvo la del párrafo que explica por qué no se usa.
- **Cabecera**: `Versión 1.1 · Aprobada por Fredy Bonilla`.
- **§10**: «Fuera de alcance de la versión 1.0» → «Fuera de alcance», que es lo que era; esos
  cuatro puntos no dependen de la versión.
- **Historial de versiones**: sección nueva al final, con el mismo formato que la de
  `ESPECIFICACION-informe.md`, para que se pueda seguir qué cambió y cuándo.

## 2. El diff, acotado

```
docs/ESPECIFICACION-horas.md | 71 insertions(+), 9 deletions(-)

@@ -3      cabecera: v1.1
@@ -92     §4.1 — el calendario, el detalle y el popup
@@ -102    §4.2.4 — desfase
@@ -118    §5 — «exceso» -> «desfase»
@@ -122    §5.1 — alertas de desfase (sección nueva)
@@ -182    §7.2 — «exceso» -> «desfase»
@@ -217    §10 — título
@@ -224    historial de versiones (sección nueva)
```

**Ningún otro punto del documento se tocó.** El modelo de datos, las reglas de permisos, la
importación y los reportes quedan exactamente como estaban.

Copia de seguridad: `ESPECIFICACION-horas.md.bak_h2b_H2b.1_20260917`.

## 3. Lo que esto implica para los sub-pasos siguientes

| Sub-paso | Qué le pide la v1.1 |
|---|---|
| H2b.2 | `GET /time/month`, los totales del mes, y el estado de desfase por proyecto con los umbrales de §5.1 |
| H2b.3 | reescribir `RegistroPage.tsx` como calendario y **retirar** la vista semanal |
| H2b.4 | las alertas de §5.1 en Proyectos y en el detalle |
| H2b.5 | comprobar, entre otras cosas, que **la palabra «exceso» no aparece en ninguna pantalla** |

El backend de H2 **se conserva entero**: los siete endpoints, el módulo `calendario.py` y sus
29 tests siguen valiendo. H2b añade encima, no sustituye.

---

**Estado:** H2b.1 cerrado. La especificación está en v1.1 y el diff se limita a los puntos de
H-D30. Sigue H2b.2 — backend del calendario y del desfase.
