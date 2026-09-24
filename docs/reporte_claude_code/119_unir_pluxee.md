Commit `2190829` · 24 de septiembre de 2026

# Unir «Pluxee shop» en «Carga masiva_Performance»

Los dos proyectos de SODEXO (Pluxee) eran el mismo trabajo. Queda uno:
**`Carga masiva_Performance`**, con **142 h consumidas** y **200 h estimadas**.

Todo por endpoints del producto. **Ni una línea de SQL** (regla 28).
**0 llamadas a la IA.**

Copia previa: `backup_antes_unir_pluxee_20260924.sql`, 6.806.540 bytes.

---

## 1. Lo que había antes

| Proyecto | Actividad | Estimadas | Consumidas | Reg. |
|---|---|---|---|---|
| **Pluxee shop** | Diseño de script | 100,00 | 61,50 | 9 |
| | Análisis de resultados | 76,00 | 46,50 | 6 |
| | Ejecución | 10,00 | 14,00 | 3 |
| | Gestión de proyectos | 8,00 | 6,00 | 1 |
| | Planeación | 6,00 | 0 | 0 |
| | **Total** | **200,00** | **128,00** | **19** |
| **Carga masiva_Performance** | Análisis de resultados | 76,00 | 14,00 | 3 |
| | **Total** | **76,00** | **14,00** | **3** |

Los registros, por persona:

| Proyecto | Persona | Actividad | Reg. | Horas | Fechas |
|---|---|---|---|---|---|
| Pluxee shop | Rubén Darío Flórez | Diseño de script | 9 | 61,50 | 1 – 17 sep |
| | | Análisis de resultados | 6 | 46,50 | 8 – 23 sep |
| | | Ejecución | 3 | 14,00 | 17 – 21 sep |
| | | Gestión de proyectos | 1 | 6,00 | 14 sep |
| Carga masiva_Performance | Mónica Alejandra Archila Córdoba | Análisis de resultados | 2 | 9,50 | 21 – 22 sep |
| | Fredy Gabriel Bonilla Becerra | Análisis de resultados | 1 | 4,50 | 21 sep |

**Los 19 de `Pluxee shop` son todos de Rubén**, y los 3 de `Carga masiva` son de
Fredy y Mónica. Es coherente con que sea el mismo trabajo visto desde dos sitios.

> `Carga masiva_Performance` **ya tenía puestas sus 76 h de Análisis**, a mano,
> antes de empezar. Son las mismas 76 del cuadro, lo que confirma lo que decía
> el encargo: el cuadro estimaba **un solo proyecto**, y por eso esa cifra no se
> suma dos veces.

---

## 2. El producto sí permite mover un registro de proyecto

No hubo que parar. `PUT /time/entries/{id}` acepta `project_id`, y el endpoint
contempla el caso expresamente:

```python
# H-D20 en los dos proyectos: el de origen y el de destino si se mueve.
await _proyecto_abierto(db, registro.project_id)
if data.project_id and str(data.project_id) != str(registro.project_id):
    await _proyecto_abierto(db, data.project_id)
await _actividad_del_proyecto(db, proyecto_id, actividad_id)
```

**Esa última guarda fijó el orden de la operación**: la actividad tiene que
estar ya en el proyecto de destino, o el movimiento da un 400. Con
`Carga masiva_Performance` teniendo solo `Análisis de resultados`, mover un
registro de `Diseño de script` habría fallado.

Así que primero las estimaciones y después los registros:

| Paso | Endpoint | Resultado |
|---|---|---|
| 1. Las cinco del cuadro en el destino | `PUT /time/projects/{id}/actividades` ×5 | 200 (las cinco) · 200,00 h |
| 2. Los registros se mudan | `PUT /time/entries/{id}` ×19 | **19 movidos, 0 fallidos** |
| 3. `Pluxee shop` desaparece | `DELETE /time/projects/{id}` | 200 · 5 estimaciones y 5 cambios de estimación con él |

### Un tropiezo por el camino, que vale la pena contar

El primer intento movió **0 registros** y dijo que no había ninguno, mientras el
borrado contestaba que había 19. No era una contradicción: **`GET /time/entries`
devuelve los de UNA persona** —por defecto, la que pregunta—, y los 19 son de
Rubén, no del admin. Se recorren los usuarios y aparecen.

Lo cazó el 409 del borrado, que dice **cuántos** registros estorban en vez de un
«no se puede». Si solo hubiera dicho que no, el listado vacío habría parecido
que el trabajo ya estaba hecho.

---

## 3. Cómo quedó el proyecto unido

**`SODEXO (Pluxee) / Carga masiva_Performance`** — 22 registros

| Actividad | Estimadas | Consumidas | Reg. |
|---|---|---|---|
| Diseño de script | 100,00 | 61,50 | 9 |
| Análisis de resultados | 76,00 | **60,50** | 9 |
| Ejecución | 10,00 | 14,00 | 3 |
| Gestión de proyectos | 8,00 | 6,00 | 1 |
| Planeación | 6,00 | 0 | 0 |
| **Total** | **200,00** | **142,00** | **22** |

**142,00 = 128,00 + 14,00** ✓ y **200,00 estimadas** ✓, como pedía el encargo.
`Análisis de resultados` es la única que fusiona horas de los dos: 46,50 de
Rubén más 14,00 de Fredy y Mónica.

`Pluxee shop` **ya no existe**, y dejó su constancia en `project_deletions`:
nombre, cliente, 5 estimaciones, quién y cuándo.

---

## 4. Las estimaciones a mano, intactas

Es lo que más importaba. Se fotografiaron **las 48 filas de estimación** antes de
tocar nada y se compararon al terminar:

```
antes: 48 filas · despues: 47 filas

=== diferencias FUERA de los dos proyectos de SODEXO ===
  NINGUNA — las 42 filas de los demas proyectos estan identicas
```

Lo único que cambió, y es exactamente lo que tenía que cambiar:

```
- SODEXO (Pluxee)|Pluxee shop|Análisis de resultados|76.00
- SODEXO (Pluxee)|Pluxee shop|Diseño de script|100.00
- SODEXO (Pluxee)|Pluxee shop|Ejecución|10.00
- SODEXO (Pluxee)|Pluxee shop|Gestión de proyectos|8.00
- SODEXO (Pluxee)|Pluxee shop|Planeación|6.00
+ SODEXO (Pluxee)|Carga masiva_Performance|Diseño de script|100.00
+ SODEXO (Pluxee)|Carga masiva_Performance|Ejecución|10.00
+ SODEXO (Pluxee)|Carga masiva_Performance|Gestión de proyectos|8.00
+ SODEXO (Pluxee)|Carga masiva_Performance|Planeación|6.00
```

Las 76,00 de `Análisis` del destino **no aparecen en el diff**: ya estaban y no
se tocaron.

### Los 15 proyectos

| Cliente | Proyecto | Estimadas | Consumidas | % |
|---|---|---|---|---|
| Software Quality Assurance | COE - UEN Financial | 7,00 | 7,00 | **100,0 %** |
| Software Quality Assurance | COE - UEN Total | 5,00 | 5,00 | **100,0 %** |
| MEDICINA PREPAGADA COOMEVA | 24355 Brebia_Performance | 2,00 | 2,00 | **100,0 %** |
| BANCO POPULAR | Banco Popular - Proyecto Bus | 17,00 | 16,50 | **97,1 %** |
| Software Quality Assurance | COE - Corporativo | 2,00 | 1,75 | **87,5 %** |
| Software Quality Assurance | 24352 sq-ai v2_Performance | 65,00 | 51,00 | 78,5 % |
| Software Quality Assurance | 24354 Pruebas funcionales sq-ai | 50,00 | 37,25 | 74,5 % |
| PORVENIR | Apoyos_Performance_PORVENIR | 34,00 | 25,00 | 73,5 % |
| **SODEXO (Pluxee)** | **Carga masiva_Performance** | **200,00** | **142,00** | **71,0 %** |
| MEDICINA PREPAGADA COOMEVA | 24342-Coomeva_SendCode_Performance | 2,00 | 1,00 | 50,0 % |
| MEDICINA PREPAGADA COOMEVA | 24353 Bre-b - Pruebas de WH (Pexto) | 60,00 | 25,50 | 42,5 % |
| ALKOSTO | Migracion Manhathan_Performance | 200,00 | 58,50 | 29,3 % |
| BANCO FICOHSA | NOVA - Capa media | 375,00 | 94,50 | 25,2 % |
| BANCO FICOHSA | Paquete 1 - PCKG1 | 250,00 | 21,50 | 8,6 % |
| Compensar | COMPENSAR - Generales | 10,00 | 0,50 | 5,0 % |

**15 proyectos, los 15 con estimación**, 1.279,00 h estimadas y 489,00 h
consumidas. Las 107 horas y los 107 registros **no se movieron**: 489,00 antes y
489,00 después.

Cinco están al 87 % o más. Los tres al 100,0 % exacto son **Terminado**: la
siguiente hora que se registre ahí los pone en desfase.

---

## 5. De dónde salen las 61,50 h de Diseño de script

La comprobación que pediste aparte. **No hay nada descolocado.**

### Los 9 registros, uno a uno

Todos de **Rubén**, del **1 al 17 de septiembre**:

| Fecha | Horas | Extra | Observación |
|---|---|---|---|
| 01/09 | 8,50 | | continuacion con flujo de trabajo para consulta de b… |
| 02/09 | 8,50 | | continuacion con flujo de trabajo para consulta de b… |
| 07/09 | 8,50 | | continuacion con flujo de trabajo para consulta de b… |
| 09/09 | 8,50 | | continuacion con flujo de trabajo para cargue masivo |
| 14/09 | 2,50 | | continuacion con flujo de trabajo para Dispersion va… |
| 15/09 | 8,50 | | continuacion con flujo de trabajo para Beneficiarios |
| 16/09 | 8,50 | | continuacion con flujo de trabajo para Dispersion va… |
| 16/09 | 4,00 | **sí** | Creacion de servicios, parametrizacion y variabiliza… |
| 17/09 | 4,00 | **sí** | Creacion de servicios, parametrizacion y variabiliza… |
| | **61,50** | | |

### Salen literalmente del Excel de Rubén

Leyendo su archivo **original**, sin corregir, las filas de `Pluxee shop`:

| Tarea, como venía escrita | Filas | Horas |
|---|---|---|
| **Diseño y generación de script** | **9** | **61,50** |
| Analisis de resultados | 5 | 38,00 |
| Análisis | 1 | 8,50 |
| Ejecución | 3 | 14,00 |
| gestion de proyectos | 1 | 6,00 |
| **Total** | **19** | **128,00** |

Las 9 filas y las 61,50 h **son las del archivo**. La tabla de sinónimos las
mandó a `Diseño de script` y no perdió ni añadió ninguna.

### ¿Horas de diseño fuera de septiembre? **Ninguna**

```
rango de TODOS los registros: 2026-09-01 a 2026-09-23
fuera de septiembre 2026: 0
```

No hay una sola hora, de ninguna actividad ni proyecto, fuera de septiembre.

### ¿Horas de diseño de estos proyectos en otro proyecto? **No**

Todo el `Diseño de script` de Rubén está repartido así:

| Cliente | Proyecto | Reg. | Horas |
|---|---|---|---|
| SODEXO (Pluxee) | Carga masiva_Performance | 9 | 61,50 |
| ALKOSTO | Migracion Manhathan_Performance | 3 | 12,00 |
| BANCO POPULAR | Banco Popular - Proyecto Bus | 1 | 8,50 |
| | **Total de Rubén** | **13** | **82,00** |

Cada una está en el cliente que decía su fila del Excel. **Ninguna de SODEXO se
fue a otro proyecto, ni al revés.** Fredy y Mónica no registraron ni una hora de
diseño para SODEXO: lo suyo en `Carga masiva` fue Análisis de resultados.

### Las 94,50 no salen de ninguna agrupación de estos datos

Lo busqué y **no se reproduce**: ni una actividad de ningún proyecto suma 94,50,
ni se llega a esa cifra combinando las de SODEXO.

| Lo que sí suma | |
|---|---|
| Diseño de Rubén en SODEXO | **61,50** |
| Diseño de Rubén en todos los proyectos | 82,00 |
| Todo SODEXO menos Análisis (Diseño + Ejecución + Gestión) | 81,50 |
| Diseño de script de todo el equipo, todo septiembre | 280,50 |

**La única cifra de 94,50 h que existe en el mes es el total consumido de
`BANCO FICOHSA / NOVA - Capa media`.** Es la explicación más probable de la
expectativa —dos filas contiguas en la tabla de proyectos—, pero es una
hipótesis mía y la dejo señalada como tal, no como un hecho.

**Conclusión: los registros están donde deben.** No se cambió nada por esto,
como pedía el encargo.

---

## 6. Los archivos

Ninguno. La operación entera se hizo por endpoints ya existentes: el de
estimaciones (H1.3), el de edición de registros (H2) y el de borrado de proyecto
(la carga real). No hizo falta escribir ni cambiar código.

---

## 7. Lo que queda

- **Tu validación**, que es el único criterio (regla 9).
- **Decidir qué pasa con las 94,50** (§5): si era otra cifra, dilo y lo miro.
- Sigue pendiente **partir `NOVA - Capa media` en dos**, si quieres los paquetes
  separados (reporte 118 §2.1).
- Y **revisar `Gestión de proyectos` en Paquete 1 - PCKG1**, con 21,50 h contra
  4 estimadas (reporte 118 §4).
