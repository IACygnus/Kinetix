Commit `679f186` · 24 de septiembre de 2026

# H8.6 — el cierre de H8

Lo que quedaba pendiente desde H8.1: estrechar el `CHECK` a los cinco estados,
retirar los alias de H-D91, regenerar la referencia de las cifras del informe,
arreglar las dos suites del laboratorio que no corrían, y la regresión.

**0 llamadas a la IA.**

---

## 1. El `CHECK` de `projects.status`, a los cinco

`docs/sql/h8_estado_proyecto_cierre.sql` — **nuevo**, idempotente. Es la segunda
mitad de `h8_estado_proyecto.sql`, que había ampliado el `CHECK` a **siete**
valores —los cinco nuevos más `activo` y `cerrado`— para que el SQL y el código
se pudieran desplegar en cualquier orden. Con el código nuevo ya vivo, los dos
viejos sobran.

El orden importa, y aquí sí:

```
1. h8_estado_proyecto.sql      amplía a siete y migra las filas viejas
2. el código de H8.2 a H8.5    desplegado y funcionando
3. h8_estado_proyecto_cierre   estrecha a cinco
```

Aplicarlo con código viejo corriendo **rompería la creación de proyectos**: ese
código escribe `activo` y el `CHECK` ya no lo aceptaría.

### La guarda, probada de verdad

El script no toca ni una fila: solo cambia una restricción. Si quedara alguna
con un valor viejo, el `ALTER` reventaría. Por eso empieza comprobando y
abortando con un mensaje que se entiende. **Y eso se probó, no se supuso:**

1. Se creó un proyecto `ZZTEST-H86-legado` por el producto, se volvió a los
   siete valores y se le puso `status='cerrado'`.
2. El script de cierre **abortó**, con su mensaje, y la transacción se deshizo
   entera: el `CHECK` seguía en siete valores y nada había cambiado.
3. Se aplicó `h8_estado_proyecto.sql` —lo que el propio mensaje manda hacer—,
   que migró la fila a `finalizado`.
4. El script de cierre pasó.
5. El proyecto de prueba se borró **por el endpoint del producto**.

Aplicado en `jmeter_analyzer_db` y en `jmeter_analyzer_test` (regla 34), con
copia previa: `backup_antes_h86_20260924.sql`, 6.788.477 bytes.

**En producción no está aplicado ninguno de los dos**: H8 entero sigue sin
desplegar. Allí van los tres pasos seguidos, en ese orden.

### Y en el modelo

`CheckConstraint` de `time_tracking.py`, a los cinco. Solo afecta a una base
**nueva** —`create_all` no altera una tabla que ya existe—, pero tiene que
quedar igual que la de Fredy o las suites probarían otra cosa.

---

## 2. Los alias de H-D91, retirados

Existieron entre H8.2 y H8.3, mientras la pantalla todavía mandaba los nombres
viejos. Hoy la pantalla manda los nuevos —se comprobó: `incluir_cerrados` y
`estado: 'activo'` no aparecen en ningún archivo vivo del frontend, solo en un
`.bak`—, así que seguir aceptándolos solo servía para que un cliente viejo
pareciera funcionar.

| Qué | Antes | Ahora |
|---|---|---|
| `?incluir_cerrados=true` | alias de `incluir_finalizados` | **no existe**; se ignora y los finalizados no salen |
| `?estado=activo` | se traducía al filtro por defecto | **400** que dice cuáles son los cinco |
| `?estado=cerrado` | traía los finalizados | **400** |

En `time_projects.py` y en `time_consulta.py`.

### Lo que NO se retiró, y por qué

`estados.LEGADO` y `normalizar_legado()` **se quedan**. Son otra cosa: el
`CHECK` protege lo que **entra**, esto protege lo que **sale**. Mientras haya
una base sin los dos SQL aplicados —el servidor de producción, hoy, es una—, sus
filas siguen diciendo `activo`, y sin esto la API contestaría un estado que la
pantalla no entiende y la fila saldría en blanco sin explicar por qué.

Escribir: los cinco. Leer: se tolera lo viejo y se traduce.

---

## 3. Las dos suites del laboratorio

**Sí corren.** Lo que no podían era correr **solas desde dentro del
contenedor**, y eso no tiene arreglo: `o2a3_config.py` y `o2a3_correlacion.py`
necesitan poner la etiqueta de corrida en el recolector
(`docker kill -s HUP lab_colector`) y preguntarle a `lab_db` con su propio
`psql`. Las dos cosas son del anfitrión. Su recorrido es
`scripts/lab_prueba_correlacion.sh`, y funciona: se corrió entero y pasó, con
carga real contra el laboratorio.

```
CPU maquina 9,96 % -> 90,20 % -> 9,96 %     (leida por SSH)
CPU del contenedor de la base 0,02 % -> 612,52 % -> 0,01 %
Transacciones de PostgreSQL 0,74 -> 15,02 -> 0,60 tx/s
summary = 1244 in 00:02:03 = 10,1/s  Err: 0 (0,00 %)
```

Lo que estaba mal era **cómo fallaban cuando les faltaba algo**: un
`KeyError: 'KX_TOKEN_ESCRITURA'` y un `FileNotFoundError` de un archivo que no
dicen quién escribe. Un traceback no le dice a nadie que lo que falta es el
guion del anfitrión. Ahora cada una explica qué le falta, quién se lo da y con
qué orden se lanza el recorrido entero.

---

## 4. La referencia de las cifras del informe

`d1_cifras.py` compara el informe generado por **dos generadores distintos sobre
los mismos datos**. Esa forma —y no congelar las cifras en una lista— es lo que
hace que aísle el cambio de código del cambio de datos: el mes que se mire puede
traer otras horas y la prueba sigue diciendo lo mismo.

Nació en D1.5 con la referencia en `f5bf053` para comprobar que el rediseño no
movía ningún número. **Ese trabajo está hecho.** Después H8.3b quitó a propósito
una cifra —el «Desfasado +4,5 h» de la columna de consumo— y la prueba lo cazó,
que es justo para lo que estaba (reporte 111 §4).

**La referencia pasa a `v4.2.0`**, el cierre de H8. La pregunta ya no es «¿el
rediseño movió algo?» sino «¿se ha movido algo desde que H8 cerró?».

> **Honestamente: el día que se regenera, no prueba nada.** Los dos generadores
> son el mismo y pasa por construcción. Empieza a valer con el primer cambio que
> venga después. Decirlo es parte de regenerarla.

Y un dato que conviene tener claro, porque es fácil sacar la conclusión
equivocada: **hoy la comparación contra la referencia vieja (`f5bf053`) pasa
entera** — 962 de 962 cifras, las diez tablas. No es que la diferencia de H8.3b
se haya arreglado: es que **ningún proyecto está estimado** después de la carga
real, así que la sección 6 no tiene ningún desfase que imprimir y ese camino no
se ejercita. En cuanto Fredy estime un proyecto y alguno se pase, la diferencia
vuelve a salir. Por eso regenerar la referencia es lo correcto y no un atajo.

Se añadió `scripts/d1_cifras.sh`: saca la referencia de git, la mete en el
contenedor y lanza la comparación. Una orden en vez de dos rituales que había
que recordar.

Corrido ya con el tag creado: **962 de 962 cifras iguales**, las diez tablas, y
las 980 del documento entero como conjunto. Que pase hoy es lo esperado —los dos
generadores son el mismo—; lo que se ha comprobado es que **el mecanismo
funciona con la referencia nueva**.

> Por el camino, un detalle de Windows: `docker cp` de un archivo temporal del
> anfitrión no funciona aquí. Git Bash traduce a ruta de Windows todo lo que
> empiece por barra, y el temporal del anfitrión y el destino de dentro del
> contenedor **empiezan los dos por `/tmp`**: no hay forma de decirle que
> traduzca uno y el otro no. Se resolvió metiendo el archivo por la entrada
> estándar (`git show … | docker exec -i … 'cat > …'`), que no toca rutas.

---

## 5. El corredor de la regresión

`backend/pruebas_e2e/cierre_h8.sh` — sucede a `cierre_o2d.sh`. Arrastraba tres
problemas que solo se ven cuando algo falla, y en O2d no falló nada.

### 5.1 `set -e` paraba la pasada en la primera suite que fallaba

No llegaba al resto, no contaba nada, y el «suites: N · con fallo: M» del final
no se imprimía. Nunca saltó porque hasta ahora ninguna fallaba, **que es la peor
forma de tener un fallo**: el corredor parecía correcto porque nadie lo había
puesto a prueba. Se quitó; `correr` ya captura el código de cada suite.

Se vio en la primera pasada de H8.6: `h13` falló y la regresión entera se paró
ahí.

### 5.2 La corrida del tablero estaba escrita a mano, y caducó

```
export KX_CORRIDA=zztest-o2d-20260922-190026
```

Dos días después, el panel «Tiempo de respuesta de la prueba vs CPU del
servidor» devolvía cero filas y la prueba decía FALLA **con el tablero
perfectamente sano**. La etiqueta seguía en los dos cubos; lo que ya no estaba
eran los **datos dentro de la ventana que miran los paneles**, que son los
últimos 40 minutos.

Es el mismo problema que los contadores fijos que hubo que actualizar tras la
carga real —«sus 10 proyectos», «sus 24 registros»— y la misma lección: **un
valor fijo que depende de datos vivos se pudre, y cuando se pudre miente en la
dirección mala**, diciendo que algo está roto cuando no lo está.

Se escribió `corrida_para_tablero.py`: busca una corrida `zztest-` con datos en
**los dos cubos** y **dentro de la misma ventana que el panel**. Si no hay
ninguna, la suite se salta diciendo que hace falta una pasada del laboratorio —
no que el tablero falle.

### 5.3 Había un token en claro dentro de un archivo versionado

`cierre_o2d.sh` lleva el token de escritura de InfluxDB escrito en el propio
guion. `cierre_h8.sh` **no lo repite**: los tres secretos del laboratorio
—`KX_TOKEN_ESCRITURA`, `LAB_PG_LECTOR_PASSWORD`, `KX_LLAVE_SSH`— se toman del
entorno y viven en `lab/lab.env`, que no se versiona.

Las suites que los necesiten y no los tengan se **saltan con su motivo**, en vez
de contarse como fallo: un fallo es el producto roto, y que falte una credencial
no lo es. Mezclarlos hace que el resumen final no sirva para nada.

> **Queda dicho como deuda:** el token sigue en `cierre_o2d.sh`, que no se tocó.
> Es de un laboratorio que solo escucha en `127.0.0.1` y solo escribe, así que
> el riesgo es bajo; pero un secreto en un repositorio es un secreto quemado y
> conviene rotarlo cuando se limpie ese archivo.

### 5.4 Y un guion de anfitrión que lo lanza todo

`scripts/regresion_h8.sh` lee `lab/lab.env`, pasa los secretos y encadena las
tres partes. **El laboratorio va primero**, y no por gusto: deja una corrida
recién escrita en los dos cubos, y `o2a4_tablero` la necesita fresca. Al revés,
el tablero se saltaría siempre.

---

## 6. Las suites que se habían quedado atrás

Tres comprobaban cosas que H8 y la carga real cambiaron **a propósito**. Ninguna
era un fallo del producto; las tres son andamiaje desfasado.

| Suite | Qué comprobaba | Qué comprueba ahora |
|---|---|---|
| `h6_ajustes` §2 | que un proyecto cerrado dijera «Cerrado» **en la columna de consumo** | que `status` sea `finalizado` y que su **consumo se calcule aparte** (H-D82). «cerrado» ya no es un valor de consumo en ninguna fila |
| `h6_ajustes` §5 | el filtro con `?estado=activo` e `incluir_cerrados` | el filtro por defecto e `incluir_finalizados`, **y que los nombres viejos den 400** |
| `h13_backend` §1 · `h15_pantallas` §2 | que hubiera **cinco** actividades sembradas | que **estén las ocho** de `CANONICAS`, preguntándoselas al producto |

`h6_ajustes` llevaba **desfasada desde H8.2** y nadie se había dado cuenta,
porque `cierre_o2d.sh` se corrió antes de H8 y desde entonces no se había vuelto
a pasar entera.

Las dos del catálogo comprueban ahora que **estén las ocho**, no que haya ocho
filas: una base de pruebas acumula actividades de pasadas anteriores, y contar
filas las haría fallar por algo que no es el catálogo. Y la lista se la piden a
`sinonimos_actividad.CANONICAS`, que es donde vive — no la copian.

Se actualizaron además tres valores esperados de «la base de Fredy, intacta»,
que la carga real cambió a sabiendas: de 10 a **16 proyectos**, de 24 a **107
registros**, y la de `time_entry_purges` pasó de «cero purgas» a «las mismas que
al empezar» — lo que delata un borrado accidental es que el número **crezca
durante la pasada**, no que la base nunca haya tenido un borrado legítimo.

---

## 7. La regresión

```
bash scripts/regresion_h8.sh

=== LA BASE DE FREDY, ANTES ===        === LA BASE DE FREDY, DESPUES ===
a7307ec8b5bf157bb9a87fc6e811d712       a7307ec8b5bf157bb9a87fc6e811d712
107 16 8 15 0 0                        107 16 8 15 0 0

SI — la base de Fredy no cambio ni una fila
suites: 28 · con fallo: 0 · saltadas: 0
```

**1.047 comprobaciones**, más las del laboratorio.

| | Suites | Comprobaciones |
|---|---|---|
| Horas, H1 a H7 | 11 | 471 |
| **H8** | 7 | **284** |
| **La carga real** | 2 | **46** |
| Observabilidad (O1, O2a, O2c, O2d) | 7 | 190 |
| Diseño (D1) | 1 | 56 |

Y las que no corren dentro del contenedor:

| | |
|---|---|
| **El laboratorio (O2a.3)** | `TODO PASA` — carga real contra el laboratorio: la CPU de la máquina sube de 11,70 % a 90,20 % durante la prueba y vuelve a bajar; la de la base, de 0,01 % a 612,52 %; PostgreSQL de 0,70 a 15,02 tx/s. `summary = 1244 in 00:02:03 = 10,1/s  Err: 0` |
| **Las cifras del informe** | En la pasada se negó a correr, **y estuvo bien**: `«v4.2.0» no es un commit de este repositorio` — el tag se crea con este mismo commit. Ya creado, **pasa: 962 de 962 cifras iguales**, las diez tablas, y las 980 del documento entero como conjunto |

> Esa primera negativa destapó otro defecto suyo: con la sesión caducada
> reventaba con un `ValidationError` de pydantic y dos «Field required», porque
> lo que intentaba validar como informe era el `{"detail": "No se pudieron
> validar las credenciales"}`. Ahora dice **«sesión caducada»**, como las demás.
> Es el mismo arreglo del §3, encontrado por el mismo camino: lanzar una prueba
> sin sus requisitos y mirar qué contesta.

La huella de la base de Fredy es **idéntica antes y después**: mismo `md5` de los
107 registros y los mismos 16 proyectos, 8 actividades, 15 clientes, 0
estimaciones. Las suites corrieron contra `jmeter_analyzer_test` por el 8002,
que es lo que manda la regla 34.

### El fallo que encontró, y era de verdad

`d1_diseno` cazó **un párrafo del informe que se había pasado de tres líneas**:
665 letras contra un máximo de 420. Y el de al lado, 443.

No era el dato: son textos fijos. **H8.3b les añadió la explicación del estado y
H8.4 la de las horas extra**, y con esas frases se pasaron del límite que fijó
D1 sobre el informe que validaste. Nadie había vuelto a correr `d1_diseno` desde
entonces, porque `cierre_o2d.sh` se pasó antes de H8.

Se acortaron los dos párrafos —a 405 y 371—, **no el límite**: el límite es una
decisión de diseño aprobada, y esa prueba existe justo para que no se cuele un
párrafo que descuadra la página. Al recortar no se podía perder lo que H8 vino a
decir —que el estado **lo decide una persona**— ni que las dos columnas de horas
no miden lo mismo. Las dos cosas siguen.

---

## 8. Los archivos

| Archivo | Qué |
|---|---|
| `docs/sql/h8_estado_proyecto_cierre.sql` | **Nuevo.** El `CHECK` a cinco, con su guarda |
| `backend/app/db/models/time_tracking.py` | `CheckConstraint` a cinco |
| `backend/app/api/v1/endpoints/time_projects.py` | Alias de H-D91 fuera |
| `backend/app/api/v1/endpoints/time_consulta.py` | Ídem |
| `backend/app/services/horas/estados.py` | Por qué el legado se sigue **leyendo** |
| `backend/pruebas_e2e/cierre_h8.sh` | **Nuevo.** El corredor, sin `set -e` y sin secretos |
| `backend/pruebas_e2e/corrida_para_tablero.py` | **Nuevo.** La corrida se busca, no se escribe |
| `scripts/regresion_h8.sh` | **Nuevo.** Todo, desde el anfitrión |
| `scripts/d1_cifras.sh` | **Nuevo.** Las cifras del informe, en una orden |
| `backend/pruebas_e2e/diseno/d1_cifras.py` | Referencia a `v4.2.0` |
| `backend/pruebas_e2e/o2a3_config.py` · `o2a3_correlacion.py` | Dicen qué les falta |
| `backend/pruebas_e2e/h6_ajustes.py` · `h13_backend.sh` · `h15_pantallas.py` · `h82_estados.py` | Puestas al día |
| `CLAUDE.md` · `PROJECT_STATUS.md` | H8, la carga real y el SQL nuevo |
| `.gitignore` | Los Excel de horas **no se versionan** — ver §9 |
| `backend/pruebas_e2e/LEEME.md` | Cómo se corre ahora, y las tres que no van dentro |
| `lab/colector/telegraf.d/00-corrida.conf` | Queda en `sin-corrida` |

> Ese último es un archivo **generado** —`lab_corrida.sh` lo reescribe en cada
> pasada— y estaba versionado con una corrida concreta del 22 de septiembre.
> Ensuciaba el `git diff` cada vez que se usaba el laboratorio. Ahora se
> commitea en su valor neutro, `sin-corrida`, que es el estado en que lo deja
> `lab_corrida.sh --limpiar` al terminar.

---

## 9. Una decisión que no es mía

Los tres Excel de `docs/documentos carga/` llevan **nombres de clientes reales**
—SODEXO, ALKOSTO, BANCO FICOHSA, PORVENIR, COMPENSAR, MEDICINA PREPAGADA
COOMEVA— y las **horas facturables de tres personas con nombre y apellido**.

Subirlos a GitHub, aunque el repositorio sea privado, es publicarlos. **Los dejé
fuera del commit** con una entrada en `.gitignore` que dice por qué. Si quieres
incluirlos:

```
git add -f "docs/documentos carga/"
```

---

## 10. Lo que queda

- **Tu validación**, que es el único criterio (regla 9). Está pendiente de H5 en
  adelante: H5, H6, H7, D1, O1, O2a, O2b, O2c, O2d, todo H8 y la carga real.
- **Estimar los 16 proyectos.** Ninguno tiene horas estimadas, así que el
  desfase no dice nada y la sección 6 del informe sale vacía. Es para lo que se
  hizo la carga.
- **El despliegue.** H8 entero está sin desplegar, y con él **cuatro SQL
  pendientes en producción**, en orden: `etapa2_reasoning_effort`,
  `o2c_influxdb_read_token`, `h8_estado_proyecto` y `h8_estado_proyecto_cierre`.
  El checklist sigue siendo `53_checklist_despliegue.md` con la versión
  corregida en el 59 §4.
- **El token de `cierre_o2d.sh`**, que habría que rotar (§5.3).
- **O2e** —el punto de entrada HTTPS del agente— y **O3**, que no se han tocado.
