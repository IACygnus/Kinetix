9332fa9 · 2026-09-18

# ETAPA H3 — Cierre: consulta de proyectos e importación del Excel

**0 llamadas a la IA en toda la etapa.**

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **H-D31** | Comprobar si se puede leer `.xlsx`; si no, **parar sin instalar nada** | Se paró. `openpyxl` lo añadió Fredy con un rebuild |
| **H-D32** | Consulta por proyecto: quién registró, cuántas horas, estimado, consumido, restante y desfase | Hecho |
| **H-D33** | Al ampliar una fila, los días de esa persona en ese proyecto | Hecho, en dos despliegues encadenados |
| **H-D34** | Importar en `/horas/importar` con **vista previa obligatoria** | Hecho |
| **H-D35** | Idempotencia por `Id`: actualiza, no duplica | Hecho y probado con el archivo real, dos veces |
| **H-D36** | Cliente, proyecto y actividad que falten se crean, comparando normalizado | Hecho |
| **H-D37** | El proyecto nuevo nace sin estimar, se señala, y el resumen da su enlace | Hecho |
| **H-D38** | La previa enseña en color lo que se pasa de lo estimado, sin bloquear | Hecho |
| **H-D39** | Se importa para la persona elegida; por otra, solo el admin | Hecho |
| **H-D40** | Fila inválida: fuera, con su número de fila y el motivo | Hecho |
| **H-D41** | Una transacción por confirmación | Hecho: un `commit`, `rollback` en cualquier fallo |
| **H-D42 – H-D49** | Las nueve características medidas del archivo real | Todas, y **medidas contra el archivo**, no supuestas |

---

## 2. Los sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| H3.1 Diagnóstico — **PARADA en H-D31** | 78 | `3e269b5` |
| H3.2 y H3.3 La consulta | 79 | `d388a34` |
| H3.4 y H3.5 La importación, escrita | 80 | `9332fa9` |
| H3.6 La importación, validada | 81 | este commit |
| H3.7 Cierre | 82 (este), 83 | — |

---

## 3. Lo que se construyó

**Backend** — tres módulos nuevos, ninguna columna nueva:

- `api/v1/endpoints/time_consulta.py` (225): los dos endpoints de §5.
- `services/horas/importacion.py` (307): el lector del `.xlsx`, partido en
  «interpretar un valor» (puro) y «abrir el libro» (lo único con `openpyxl`).
- `api/v1/endpoints/time_import.py` (383): `/preview` y `/confirm`, con **un
  solo** `_analizar()` detrás.

**Frontend** — dos pantallas nuevas y una vieja completada:

- `pages/horas/ConsultaPage.tsx` (410): proyecto → gente → días.
- `pages/horas/ImportarPage.tsx` (435): archivo → previa → confirmar → resumen.
- `components/horas/AvisoDesfase.tsx`: se le añadieron `BarraConsumo` y
  `AvisoDesfasados`, que cierran §5.1 en Consulta **y** en Proyectos.

**El esquema no se tocó.** `external_id`, `source` y `created_by` estaban desde
H1, que definió la tabla entera pensando en esta etapa. Esa decisión se cobró
aquí: ni un `ALTER` (regla 10).

**Una dependencia nueva**, y solo una: `openpyxl==3.1.2`.

---

## 4. Verificación — 219 comprobaciones propias, todas pasan

| Prueba | Qué mira | Resultado |
|---|---|---|
| `test_horas_importacion.py` | 83 tests del lector: títulos, fechas, horas, sí/no, textos, Id | 83 pasan |
| `h32_consulta.py` | 53 por HTTP: filtros, totales por persona, el detalle por días | TODO PASA |
| `h33_pantalla.py` | 33 en la pantalla de consulta | TODO PASA |
| `h36_importacion.py` | 50 con el **archivo real**: previa, confirmar, reimportar, el enlace del proyecto y la pantalla | TODO PASA |

### El resto del producto no se movió

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| `h15_pantallas.py` (H1) · `h22_backend.py` (H2) | TODO PASA |
| `h2b2_backend.py` · `h2b5_pantalla.py` (H2b) | TODO PASA |
| `pytest tests/` | **665 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |

---

## 5. Las decisiones técnicas de la etapa

| Decisión | Justificación |
|---|---|
| **`hours_in_range` y `consumed_hours` son dos cifras distintas** | el desfase se mide contra el total de siempre; contra el rango, consultar una semana tranquila dejaría «en rango» un proyecto que Proyectos marca desfasado |
| **El lector, partido en puro e impuro** | las reglas del archivo se prueban sin fabricar un `.xlsx`, y por eso los 83 tests corrieron **antes** de que existiera `openpyxl` |
| **`/preview` y `/confirm` comparten `_analizar()`** | dos códigos para lo mismo acabarían diciendo cosas distintas, y la previa dejaría de servir para decidir |
| **`Facturable` es columna obligatoria** | que falte la columna importaría un mes entero como no facturable sin que nadie lo decidiera |
| **Los seriales de Excel < 61 se rechazan** | el error del año bisiesto de 1900 los corre un día; nadie registra horas en enero de 1900 |
| **Una fecha futura es fila inválida** | mismo criterio que H-D21 en el registro a mano |
| **Un `Id` repetido en el archivo invalida la segunda fila** | si entraran las dos, el índice único tumbaría la transacción y no entraría nada |
| **Al actualizar, el registro cambia de dueño** | es la decisión recuperable: si la primera importación se hizo con la persona equivocada, reimportar es la única forma de arreglarlo desde la pantalla |
| **`MULTIPART` explícito en las subidas** | el cliente axios manda `application/json` por defecto y el multipart llega sin frontera |
| **`mensajeDeError()` devuelve siempre texto** | un `detail` de 422 es una lista de objetos y React tumba la pantalla al pintarla |

---

## 6. Cuatro defectos que la etapa destapó, y se arreglaron

Ninguno era de código nuevo: los cuatro estaban esperando.

1. **`_excedidas` marcaba desfase sin estimación.** Comparaba contra cero, así
   que **cada fila importada habría salido en ámbar**. Discrepaba de `desfase.py`
   desde H2.
2. **El detalle de proyecto escondía horas.** Sumaba solo las actividades
   estimadas: un proyecto recién importado habría enseñado 0 consumidas teniendo
   21 registros.
3. **El `FormData` viajaba como JSON.** 422 en cada subida desde el navegador.
4. **Un 422 tumbaba la pantalla entera.** `detail` como lista de objetos metida
   en el JSX: pantalla en blanco, sin mensaje.

Los dos primeros los encontró implementar H-D37; los dos últimos, **solo** la
prueba de pantalla. Las 41 comprobaciones de HTTP daban verde con la pantalla
rota de las dos formas: la validación por HTTP y la de navegador no se
sustituyen.

---

## 7. Lo que NO se tocó

- Ningún archivo protegido (§11 de CLAUDE.md).
- Ningún compose, ningún servidor, ningún despliegue.
- Ninguna columna nueva ni ningún `ALTER`.
- El módulo de análisis, entero.
- **El rebuild lo hizo Fredy**, no yo (regla 7). El primer intento no llegó a
  aplicarse —la imagen siguió siendo la de dos semanas antes— y se detectó
  comparando su fecha con la del contenedor antes de dar nada por bueno.

---

## 8. Una nota de entorno, para la próxima

**Un rebuild se lleva las herramientas de prueba.** Playwright, su Chromium, las
bibliotecas del sistema que necesita, la sesión de `/tmp/e2e_sesion.json` y los
scripts viven **dentro del contenedor**, no en la imagen. Al reconstruir hubo que
reponerlos desde `C:\proyectos\Kinetix_pruebas\e2e`. No es un fallo —es dónde
viven, y a propósito, para no meter herramientas de prueba en la imagen de
producto—, pero conviene contar ese rato antes del próximo rebuild.

---

**Estado: Etapa H3 implementada, pendiente validación de Fredy.**
