Commit base `4832052` (O2e.4a **sin commit**: espera la validación de Fredy en pantalla) · 29 de septiembre de 2026

# O2e.4a — Los tokens de ingesta en la pantalla de Servidores

La pantalla ya hace lo que antes solo hacía la API: listar los tokens de un cliente, crearlos (se
enseñan una sola vez), revocarlos, y decir si Kinetix tiene cargado el token de escritura de `infra`.
**Nada de esto está validado por Fredy todavía** (regla 9). Lo que sigue es lo que comprobaron las
suites.

## 0. Antes de O2e.4a: los dos commits de la base, y una corrección de lo que afirmé

| Commit | Qué |
|---|---|
| `e86466a` | O2e.3 junto con el arreglo de `ZZTEST-R1` (reporte 129) |
| `4832052` | El instalador: `KX_CLIENTE='…'` entre comillas simples, y rechazo de un cliente con comillas, barras invertidas o saltos de línea |

**Cómo se comprobó el instalador.** En tres contenedores **desechables** (`docker run --rm --network
none`) con la imagen del laboratorio y el paquete de Telegraf sacado de `lab_servidor` (sha256 igual a
la `SUMA` del instalador):

| Instalador | Cliente | Etiqueta que publica Telegraf |
|---|---|---|
| viejo | `ZZTEST-Cliente con espacio` | **`cliente=${KX_CLIENTE}`**, el texto literal, y el instalador termina con código 0 |
| nuevo | `ZZTEST-Cliente con espacio` | `cliente=ZZTEST-Cliente con espacio` |
| nuevo | `laboratorio` | `cliente=laboratorio`, como hasta ahora |
| nuevo | `ZZTEST-O'Brien` | rechazado con código 2 antes de tocar nada |

**El fallo real era peor de lo que dije en el reporte 129 §5.1.** El agente no se quedaba con el
cliente vacío: publicaba la etiqueta literal `${KX_CLIENTE}`.

Lo que **no** se probó es la rama con systemd: en un contenedor no hay systemd. Que `EnvironmentFile`
quite las comillas simples es lo que dice su documentación; aquí no está comprobado.

**`instalar_agente.ps1` no tiene el mismo problema**, aunque esto sale de leer el código, no de
probarlo. Guarda las variables en el valor `Environment` del registro (tipo MultiString), y Windows
toma cada `CLAVE=valor` literal, sin que ningún shell lo interprete. Ahí **no hay que poner comillas**:
pasarían a formar parte del nombre. Sí comparte algo menor: no rechaza una comilla doble en el nombre,
que rompería la cadena TOML de `agente.conf`. No lo he tocado.

**Corrección: `lab_servidor` NO quedó byte a byte como estaba.** El contenido de todos sus ficheros es
el mismo, pero **la fecha de modificación del directorio raíz `/` cambió a las 22:38:56 UTC**, ocho
segundos después de tomar la foto previa. La hora coincide con el `docker cp` con el que saqué el
paquete de Telegraf; que la causa sea esa es una inferencia, no está demostrado (regla 33). Una
búsqueda con `find / -xdev -newermt` de todo lo modificado desde la foto solo devuelve `/`. No puedo
devolverle su fecha anterior porque de la foto solo guardé la huella, no el texto. El error fue de
método: la próxima vez hay que guardar el texto de la foto, no solo su huella.

## 1. Dónde quedó el bloque

**La lista de servidores no agrupa por cliente, así que el bloque de tokens va debajo del selector de
cliente de la pantalla (`srv-filtro-cliente`) y solo aparece con un cliente elegido.** Con «Todos los
clientes» se muestra la línea «Elige un cliente para ver y crear sus tokens de ingesta.».

La línea **«Conexión con InfluxDB (cubo infra)»** es de Kinetix, no de un cliente (lo precisó Fredy).
Va **siempre visible**, en su propia tarjeta, entre el selector y el bloque de tokens. La suite
comprueba que no está dentro del bloque.

## 2. Archivos

| Archivo | Líneas | Estimación | Qué |
|---|---|---|---|
| `frontend/src/components/observabilidad/TokensIngesta.tsx` (nuevo) | 334 | ~260 | `TokensIngesta` (lista, alta con modal, revocar) y `ConexionInflux` |
| `frontend/src/services/api.ts` | +47 | ~20 | `ingestaAPI` con sus cinco llamadas y tres tipos |
| `frontend/src/pages/ServidoresPage.tsx` | +16 | ~6 | Imports, `esAdmin` y los dos bloques bajo el selector |
| `backend/pruebas_e2e/o2e4a_pantalla.py` (nuevo) | 307 | ~280 | La suite |

`api.ts` se pasó de su estimación: los tipos, que no conté, son la mitad. El total va un 20 % por
encima. **Sin librerías nuevas, sin tocar el backend ni ningún protegido, y sin tocar el generador de la
orden de instalación (O2e.4b).** `tsc --noEmit` sobre todo el frontend: **0 errores**.

**Estilo:** las clases `BOTON` y `CAMPO` de la pantalla, sus tarjetas, sus modales
`fixed inset-0 bg-black/40`, y `window.confirm` para revocar, igual que su «Dar de baja».

## 3. Cómo se cumplen los puntos pedidos

- **La lista:**
  - prefijo `kxi_` más 8 caracteres, en gris y monoespaciado;
  - creación;
  - último uso, o «nunca»;
  - estado: «activo» o «revocado el \<fecha\>».
  - Los revocados se ven, y los activos van primero; dentro de cada grupo, por creación descendente.
- **Las fechas:** el backend las guarda en UTC y sin zona. La pantalla les añade la `Z` y las muestra
  en la hora local del navegador (`es-CO`).
- **El modal del alta:** muestra el aviso del backend, el token en monoespaciado, «Copiar» y «Ya lo
  copié».
  - No tiene manejador de Escape ni de clic en el fondo.
  - El token vive solo en un `useState` del componente, y «Ya lo copié» lo pone a `null`.
  - No pasa por ningún store, caché, `localStorage` ni `console`. `api.ts` no tiene ningún
    interceptor que registre respuestas.
- **Revocar:** pide confirmación con «Los servidores que usan este token dejan de enviar en el acto.
  No se puede deshacer.», llama al endpoint y recarga la lista.
- **La línea de InfluxDB:**
  - dice «Token de escritura cargado: sí / no», y si falta la columna, el SQL que hay que aplicar;
  - para el admin hay un botón «Cargar» con un campo de contraseña;
  - el campo se vacía al guardar, al cancelar **y también si el guardado falla**;
  - el token no se muestra nunca.
- **Analista:** ve la lista y la línea de InfluxDB, sin ningún botón.

## 4. Las suites

| Suite | Resultado |
|---|---|
| `o2e4a_pantalla.py` (nueva) | **TODO BIEN, 54 de 54** |
| `o2e2b_ingesta.py` | **TODO BIEN, 59 de 59** |
| `o16_pantalla.py` | **TODO PASA, 25 de 25** |

**`o2e4a_pantalla.py`, punto por punto:**
- **(a)** Sin cliente elegido se ve la línea que lo pide y la de InfluxDB, pero no el bloque. Con el
  cliente, el bloque aparece con su nombre, y la línea de InfluxDB sigue fuera de él.
- **(b)** Se crean dos tokens. Para cada uno: el modal muestra exactamente el token del `POST` y el
  aviso del backend; **Escape y un clic en el fondo no lo cierran**; «Copiar» lo deja en el
  portapapeles, leído con `navigator.clipboard.readText()`; «Ya lo copié» lo cierra.
- **(c)** Después, ninguno de los dos tokens está en ninguno de estos sitios:
  - el HTML, el texto ni los valores de los campos;
  - la consola del navegador;
  - `localStorage` ni `sessionStorage`;
  - **ninguna de las otras 123 respuestas de red**;
  - el log del backend de pruebas.
- **(d)** Cada fila lleva `kxi_…` con los 12 primeros caracteres del token, en gris y monoespaciado,
  «activo» y «nunca».
- **(e)** El diálogo lleva el texto pedido. La fila pasa a «revocado el 29/09/2026, 10:45 p. m.» y
  pierde su botón. El activo queda delante del revocado. Un `POST /ingesta/api/v2/write` con el token
  revocado da **401**.
- **(f)** El analista ve la línea de InfluxDB, con el mismo estado que el admin, y la lista. No
  existen «Crear token», «Revocar» ni «Cargar». **Contraprueba:** el admin sí ve «Cargar» y «Crear
  token»; sin ella, (f) pasaría aunque el botón faltara para todos.
- **(g)** «sí» en pantalla, y `GET /ingesta/token-escritura` dice `hay_token=True`. Al terminar, esa
  respuesta es la misma: no se cargó ni se reemplazó nada.

Los tokens de la suite quedan **revocados**, y la salida de la suite no lleva ningún token entero: se
buscó el patrón `kxi_` seguido de 40 o más caracteres y no aparece ninguno.

**El borrado de `o16_pantalla.py` (regla 35):**
- **Qué borró:** los puntos del cubo **`jmeter`** con
  `application="zztest-cliente-dos-zztest-corrida-o1-6-20260929-2246"`, es decir, los de su propia
  corrida.
- **Por qué:** es la limpieza que la suite trae de O1.6. Sus puntos llevan la marca `zztest-`, que es
  lo único que la regla permite borrar en `jmeter`.
- **La comprobación previa:** la misma suite verifica que «en el cubo no hay más corridas que las
  marcadas de prueba» y PASA. Además, su `limpiar()` no borra nada si el nombre no empieza por
  `zztest-`.

**Lo que hizo falta para correrlas:**
- `sincronizar.sh` para levantar el relevo del 5173, que no estaba y daba `000`.
- **Un login** contra el 8002, porque la sesión de pruebas había caducado.
- `KX_TOKEN_ESCRITURA` para `o16`, pasado con un `--env-file` temporal sacado de `lab/lab.env` y
  borrado después.

## 5. Qué NO se probó

- **La validación visual de Fredy**, que es el único criterio de éxito (regla 9).
- **«Cargar» de verdad:** la suite comprueba que el botón existe para el admin y no para el analista,
  pero **no lo pulsa**. Fredy pidió no cargar ni reemplazar nada en la base de pruebas. El `PUT` sí se
  probó por la API en O2e.2b.
- **Solo Chromium sin ventana** (el de Playwright). Ni Edge, ni Firefox, ni un navegador con ventana.
  Con el portapapeles puede haber diferencias: en un contexto no seguro, «Copiar» falla sin avisar,
  porque no hay alternativa al `navigator.clipboard`. `localhost` y `https` sí son contextos seguros.
- **La hora de las fechas:** el navegador de la suite está en UTC, así que muestra 10:45 p. m. En el
  de Fredy saldrá su hora local.
- **La memoria del navegador:** la suite demuestra que el token no está en la página, la consola, el
  almacenamiento ni la red. No puede demostrar cuándo el recolector de basura libera el objeto de la
  respuesta del alta. Eso no es observable desde la página.
- **Anchos estrechos:** la tabla lleva `overflow-x-auto`, pero no se miró a un ancho de móvil.

## 6. Un hallazgo ajeno a la etapa, sin tocar

Al buscar cómo recibe `o16_pantalla.py` su token, apareció que **`backend/pruebas_e2e/cierre_o2a.sh:11`
y `cierre_o2d.sh:11` llevan escrito en claro un token de InfluxDB** (`export KX_TOKEN_ESCRITURA="…"`).
Esos archivos están versionados y subidos a `github`. Por su uso parece el token de escritura del cubo
`jmeter` del entorno local, pero no lo he comprobado.

Hoy InfluxDB solo escucha en `127.0.0.1` (O-D1), así que desde fuera no sirve de nada. Aun así es un
secreto en el repositorio, y ya está en su historial. Conviene quitarlo de los dos guiones, que lo
lean de `lab/lab.env` como hace `regresion_h8.sh`, y **rotar el token**. Borrarlo de los archivos no lo
saca de los commits ya subidos. **La decisión es tuya; no he tocado nada.**
