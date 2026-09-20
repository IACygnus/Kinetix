37c6685 · 2026-09-20

# ETAPA H7 — cierre del módulo de horas

**0 llamadas a la IA.** `pg_dump` antes de empezar (regla 32).

---

## 0. La copia de seguridad, primero

```
C:\proyectos\Kinetix_pruebas\backup_20260920_133704.sql   6.727.253 bytes
```

Sin ella no se empezaba. Es la regla 32, escrita después del 18 de septiembre.

---

## 1. H7.1 — la portada aprobada, el destinatario y la capacidad base

### 1.1 La portada (H-D73)

`_encabezado()` en `backend/app/services/horas/informe.py` se reescribió entero.
Lo que sale ahora, de arriba abajo:

| Bloque | Qué lleva |
|---|---|
| `<table class="cab">` | el logo a la izquierda · «Centro de Excelencia · **Performance**» · «Generado el 20 de septiembre de 2026» a la derecha |
| `<div class="banda">` | la banda azul con su tramo naranja (`.banda-naranja`) |
| Título | «Informe de horas» a 26 pt y, debajo, el período en naranja a 16 pt |
| `<table class="portada">` | **Dirigido a** · **Período** · **Equipo** · **Capacidad base** |

Es una tabla, no una rejilla: la rama de impresión sigue sin `flex` ni `grid` ni
`rem` (regla 11 y regla 17), y ningún texto baja de 8 pt. Comprobado midiendo el
CSS del producto, no de una copia.

### 1.2 El destinatario (H-D74)

`time_informe.py` define una sola vez:

```python
DIRIGIDO_A = "José Javier Rodríguez Santos · Delivery Manager"
```

y los cuatro endpoints (`/informe`, `/html`, `/pdf`, `/csv`) aceptan
`?dirigido_a=`. En blanco o con solo espacios, vuelve el de por defecto: no se
publica un informe sin destinatario por un descuido de teclado.

En pantalla es el campo `inf-dirigido-a` de `InformesPage.tsx`. **Antes de
tocarlo se pidió permiso a Fredy** (regla 31) y él contestó «Sí, edita ahora».

### 1.3 La capacidad base (H-D75)

`informe_datos.py` la calcula con el **mismo** `construir_dias()` que el
calendario, no con una cuenta aparte:

```python
dias_base = construir_dias(desde, hasta, calendario, {}, nacionales)
habiles   = [d for d in dias_base if d.se_reclaman > 0]
horas_analista = sum((d.se_reclaman for d in habiles), CERO)
```

Para septiembre de 2026: **22 días hábiles · 185,00 h por analista** (18 días de
lunes a jueves a 8,5 h más 4 viernes a 8,0 h). La cifra se cruzó contra
`/time/month`, que da los mismos 22 días hábiles.

Solo entran los festivos **nacionales** (`user_id is null`): la capacidad base es
del equipo, no de las vacaciones de nadie.

---

## 2. H7.2 — la base de pruebas separada (H-D76)

El incidente del 18 de septiembre tuvo una causa de fondo: mis pruebas y el
trabajo de Fredy compartían base. Ya no.

`scripts/preparar_base_de_pruebas.sh` crea `jmeter_analyzer_test` en el mismo
Postgres y levanta un **segundo backend en el puerto 8002** apuntando a ella. El
8001 sigue intacto sobre la base de siempre. Comprueba las 7 tablas de horas, las
5 actividades y los 40 festivos sembrados, y añade el juego de datos marcado:
`ZZTEST-Cliente uno`, `ZZTEST-Cliente dos` y el usuario `zztest_analista`.

### 2.1 Las suites de navegador también

El frontend apunta al 8001 y cambiarlo pide reconstruir el contenedor, que es
decisión de Fredy (regla 7). En vez de eso, **el navegador desvía sus propias
llamadas**:

```python
page.route("http://localhost:8001/**",
           lambda r: r.continue_(url=r.request.url.replace("localhost:8001",
                                                           "localhost:8002")))
```

La pantalla es la real, sin tocar una línea de frontend, y lo que escribe cae en
la base de pruebas. Se comprobó de la única forma que vale: el desplegable de
clientes de la pantalla de Proyectos enseña `ZZTEST-Cliente uno` y
`ZZTEST-Cliente dos`, que **solo existen en la base de pruebas**.

### 2.2 Todas las suites llevan freno

Cada `limpiar()` empieza igual:

```python
if "test" not in BASE:
    sys.exit(f"PARADA: '{BASE}' no es una base de pruebas. No se borra nada.")
```

y borra **solo** lo que la propia prueba marcó con `ZZTEST-` (reglas 29 y 30).
Apuntada a la base de Fredy, una suite se niega a borrar en vez de hacerlo.

---

## 3. H7.3 — la documentación

| Documento | Qué cambió |
|---|---|
| `docs/ESPECIFICACION-horas.md` | **v1.4**: nueva §7.3 «La portada», §7.4–7.8 renumeradas, fila de historia |
| `CLAUDE.md` | §1 el tag y el estado del módulo · §2 openpyxl · §4 la tabla de `/time` y los módulos de definición única · §5.1 las siete tablas · §13.1 reglas 28–34 (la 34 es la base de pruebas) · §14 lo que el despliegue añade |
| `PROJECT_STATUS.md` | tabla H1–H7, el incidente y lo que queda pendiente de Fredy |

---

## 4. H7.4 — la regresión completa, en serie

Las suites de horas van **en serie, nunca en paralelo**: es la lección del
reporte 88, donde tres fallos falsos salieron de correr dos suites a la vez sobre
los mismos datos.

### 4.1 Lo que corrió, en este orden

| # | Suite | Qué cubre | Comprobaciones |
|---|---|---|---|
| 1 | `pytest` (backend) | 671 pruebas unitarias | 670 pasan · 1 falla, ajena a horas (§6) |
| 2 | `tsc --noEmit` | todo el TypeScript | limpio |
| 3 | `h13_backend.sh` | actividades y proyectos por HTTP | 24 |
| 4 | `h15_pantallas.py` | las pantallas de Actividades y Proyectos | 22 |
| 5 | `h22_backend.py` | el registro de horas por HTTP | 45 |
| 6 | `h2b2_backend.py` | el calendario del mes y el desfase | 53 |
| 7 | `h2b3_pantalla.py` | **nueva** — el calendario en pantalla | 36 |
| 8 | `h32_consulta.py` | la consulta de proyectos | 53 |
| 9 | `h52_informe.py` | los datos del informe | 60 |
| 10 | `h53_h54_documento.py` | el HTML y el PDF | 54 |
| 11 | `h6_ajustes.py` | los diez ajustes del veredicto | 54 |
| 12 | `h71_portada.py` | **nueva** — la portada, el destinatario y la capacidad | 27 |
| 13 | `h7_pantallas_horas.py` | **nueva** — consulta, importar e informes en pantalla | 36 |
| 14 | `verificar_etapa2.py` | las cuatro salidas del informe de JMeter | pasa |

**464 comprobaciones de horas, todas verdes.** Ninguna suite corrió a la vez que
otra.

### 4.2 Y la base de Fredy no se movió

Huella de `time_entries` y seis cuentas, antes y después de la corrida entera:

```
=== LA BASE DE FREDY, ANTES ===
86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5

  … las once suites …

=== LA BASE DE FREDY, DESPUES ===
86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5

SI — la base de Fredy no cambio ni una fila
suites: 11 · con fallo: 0
```

Las cuentas son, en orden: `time_entries`, `projects`, `activities`, `clients`,
`project_activities`, `project_activity_changes`. La huella es el `md5` del
`string_agg` de id, fecha, horas y proyecto de **todos** los registros: si
hubiera cambiado una sola hora de un solo día, sería otra.

---

## 5. Lo que hubo que arreglar por el camino

### 5.1 `h24_pantalla.py` llevaba rota desde H2b, y no desde H7

Probaba la vista **semanal** del registro. H2b.3 la sustituyó por el calendario
del mes y con ella desaparecieron sus `data-testid`: `dia`, `salto-fecha`,
`alta-*`, `editar-*`. La suite no volvió a correr desde entonces, así que nadie
se enteró.

Se retiró y en su lugar está **`h2b3_pantalla.py`**, contra la pantalla que
existe: el calendario, el detalle del día y el popup de registro. Nueve bloques,
36 comprobaciones.

De paso apareció algo que ninguna suite miraba: **«¿Se cobra?» nace sin nada
marcado** y hasta que no se elige, el botón de guardar está apagado. Es
deliberado —facturable o no es una decisión, no un valor por defecto— y ahora
está probado.

### 5.2 Tres pantallas del módulo no tenían prueba de navegador

Registro, Actividades y Proyectos sí. Consulta, Importar e Informes no: sus
comprobaciones de H3.7 y H5.6 se hicieron con guiones que nunca se guardaron.
Cerrar el módulo dejando tres de cinco pantallas sin regresión no es cerrarlo.

**`h7_pantallas_horas.py`**, nueva: la consulta con sus seis filtros y el
desglose por persona; la importación de punta a punta (archivo → vista previa →
confirmar → el proyecto existe en la base); y el informe con sus cuatro
pestañas, el destinatario escrito a mano saliendo en la portada y la capacidad
base. 36 comprobaciones.

### 5.3 Una comprobación que solo valía en la base de Fredy

`h15_pantallas.py` exigía que el historial dijera «Fredy» o «Bonilla». En la base
de pruebas el admin se llama «Administrador SQA», así que fallaba por el motivo
equivocado. Ahora le pregunta al propio producto quién es:

```python
nombre = page.evaluate("async () => (await (await fetch('…/auth/me',"
                       " {credentials:'include'})).json()).full_name")
ok(bool(nombre) and nombre in primera, …)
```

Comprueba lo mismo —que el historial nombra a la persona, no al usuario— y vale
en las dos bases.

### 5.4 Una comprobación que se saltaba por falta de contraseña

`h13_backend.sh` no podía probar el 403 del analyst porque no tenía la clave de
«Moni», una persona real. Con `zztest_analista` en la base de pruebas, se prueba:

```
PASA  | un analyst NO puede cerrar (403)
```

Era un `OMIT` desde H1.3.

---

## 6. Un fallo de `pytest` que no es de este módulo

```
FAILED tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas
AttributeError: module 'app.services.ai.analysis_pipeline' has no attribute 'time'
```

No lo trae H7 ni el módulo de horas. El commit **`c3e3bb4` (13 de agosto de
2026)**, «quitar sleeps del pipeline», retiró `import time` del módulo y dejó en
la prueba el `patch(...analysis_pipeline.time)` que ya no tiene a qué agarrarse.
Ni el módulo ni la prueba tienen cambios locales. **Queda como está**: arreglarlo
es de la parte de IA, no de horas, y se avisa en vez de tocarlo de paso.

---

## 7. Lo que no se ha comprobado (regla 33)

- **Fredy no ha validado H5, H6 ni H7.** Nada de lo de estas tres etapas está
  validado visualmente por él, que es el único criterio de éxito (regla 9). Lo
  que aquí se afirma es lo que miden las pruebas.
- **Las 14 estimaciones siguen sin teclear.** Se recuperaron los 21 registros, 9
  proyectos, 14 actividades y 3 clientes; las estimaciones las vuelve a poner
  Fredy.
- **El logo sigue a 135 × 90 px** (≈ 104 ppp a 22 mm de ancho). Se ve bien en
  pantalla y aceptable impreso; si Fredy quiere más resolución, hace falta el
  original.
- **En `jmeter_analyzer_test` quedó una fila suelta**, el proyecto vacío
  `proyecto h1.3`, de la primera corrida de `h13_backend.sh` antes de ponerle la
  marca `ZZTEST-`. No estorba a ninguna suite y **no se borra**: la regla 28 dice
  que si hay que borrar algo, se para y se pide. Queda dicho aquí.

---

## 8. Estado

**Módulo de horas completo — H5, H6 y H7 pendientes de validación de Fredy.**

Etiqueta `v4.1.0` sobre el commit de cierre, empujada a `github` junto con la
rama `backup-trabajo-local`.
