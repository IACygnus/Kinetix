36cc9b5 · 2026-09-18

# ETAPA H5.1 — Diagnóstico y especificación v1.2

**0 llamadas a la IA. Solo lectura y documento**: no se tocó código de producto.

---

## 1. La orientación mixta funciona (H-D56)

Era lo único que podía hacer parar la etapa, así que se midió antes que nada. Un
HTML mínimo con dos `@page` —una sin nombre y otra llamada `apaisada`— y una
sección con `page: apaisada`. Se renderizó el PDF de verdad y **se leyeron las
dimensiones de cada página**, no se dio por bueno porque no diera error:

```
paginas: 5
 pag  ancho mm  alto mm   orientacion
   1     210.0    297.0   vertical
   2     210.0    297.0   vertical
   3     297.0    210.0   HORIZONTAL
   4     297.0    210.0   HORIZONTAL
   5     210.0    297.0   vertical

esperado: ['vertical', 'vertical', 'HORIZONTAL', 'HORIZONTAL', 'vertical']
obtenido: ['vertical', 'vertical', 'HORIZONTAL', 'HORIZONTAL', 'vertical']

==> WeasyPrint 61.2 SI admite la orientacion mixta. H-D56 es viable.
```

Lo que hace viable H-D56, dicho con precisión: **una sección con `page:` propio
cambia la orientación y la devuelve al salir**, y los saltos de página dentro de
esa sección heredan su orientación. Es exactamente lo que pide la sección 9.

**No hay PARADA.** WeasyPrint 61.2 y pydyf 0.10.0, los que ya están pinados.

---

## 2. Qué agregaciones hay y cuáles faltan

| Sección del informe | Qué existe hoy | Qué falta |
|---|---|---|
| 1 Resumen | nada agregado | los seis indicadores |
| 2 Ocupación por persona | `calendario.py` sabe la jornada de un día | sumarla **por persona** en el rango |
| 3 Facturable / no facturable | `/time/consulta` lo da **por persona y proyecto** | el total y el reparto por cliente |
| 4 Cobertura por cliente | — | horas por cliente |
| 5 En qué se fue el tiempo | — | horas por actividad |
| 6 Consumido / estimado | **`/time/consulta` ya lo da entero**, con `desfase.py` | nada |
| 7 Mapa del mes | `/time/month` lo da **de una persona** | la rejilla de **todas** las personas |
| 8 Días sin registrar | `dias_pendientes()` de `calendario.py` | por persona, en un solo paso |
| 9 Horas día a día | — | día → proyecto y actividad |
| 10 Detalle de registros | `_responder()` de H2 resuelve una lista de registros | filtrarla por los filtros del informe |

**Lo que se reutiliza es lo que importa**: `construir_dias()` para las secciones
2, 7 y 8; `desfase.py` para la 6; `_responder()` para la 10. Las tres definiciones
que ya existen —la jornada, el día incompleto y el estado de desfase— **no se
vuelven a escribir**. Es lo que evita que el informe diga una cifra y la pantalla
otra.

Lo que sí hace falta es un endpoint que lo junte todo en una sola pasada:
`GET /time/informe`. Hacerlo con seis llamadas desde la pantalla habría dado seis
momentos distintos de la base y cifras que no cuadran entre sí.

---

## 3. Ni protegidos ni dependencias nuevas

- **Ningún archivo protegido.** H-D51 ya lo dice: el generador es propio,
  `services/horas/informe.py`, y no toca `report_generator.py`. Lo que sí se copia
  de él son sus **reglas**, que están en CLAUDE.md §13: solo tablas, `mm`/`pt`,
  nada de flex ni grid en la rama de impresión, y `@page :first` si hiciera falta
  una portada.
- **Ninguna dependencia nueva.** WeasyPrint ya está —lo usa el informe de
  análisis— y el HTML no necesita nada: va autocontenido por H-D55.
- **Ningún cambio de esquema.** El informe solo lee.

---

## 4. El logo (H-D54)

`backend/app/assets/logo-sqa.png` **no existe**, y la carpeta `assets` tampoco.
H-D54 dice que eso **no es parada**: el informe saldrá con el nombre en texto
hasta que el archivo esté. Queda anotado aquí y se volverá a decir en el cierre.

Cuando Fredy deje el archivo en esa ruta, el informe lo tomará solo: se lee en
cada generación y se embebe en base64, sin caché que haya que invalidar.

---

## 5. La especificación, a v1.2

§7 reescrito entero, de ocho líneas de índice a siete apartados con las diez
secciones, los filtros, el HTML interactivo, el PDF de orientación mixta, la
vista previa que no maqueta aparte, el CSV, los nombres de archivo y los tiempos
máximos. Recoge H-D50 a H-D62.

La tabla de versiones queda así:

| Versión | Cambio |
|---|---|
| 1.0 | Versión inicial |
| 1.1 | El calendario mensual, «desfase» y las alertas de §5.1 |
| **1.2** | **§7 reescrito: un solo informe, diez secciones, PDF de orientación mixta, previa del documento real, CSV y tiempos** |

Copia de seguridad del documento anterior en `ESPECIFICACION-horas.md.bak_h5_*`.

---

## 6. Lo que viene

H5.2 construye `GET /time/informe` con las diez secciones ya calculadas, y su
validación comprueba lo único que de verdad importa de un informe: **que sus
cifras cuadren con las de la consulta y las del calendario**. Una cifra, una
fuente.
