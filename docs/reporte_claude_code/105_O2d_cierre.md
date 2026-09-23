7b14aa2 · 2026-09-22

# ETAPA O2d — la pantalla que faltaba

**0 llamadas a la IA.** `pg_dump` antes de empezar. Etapas previas: reportes
**96** a **104**.

---

## 0. El punto de partida: Fredy tenía razón

Revisó la pantalla de Monitoreo en vivo y no entendió qué hacía. No sabía cómo
conectarse a los servidores, no entendía qué pintaba un `.jmx` en
observabilidad, perdía todo al cambiar de pestaña, y no veía ni una gráfica de
CPU.

**O1 a O2c construyeron la tubería y nadie construyó el grifo.** El diagnóstico
que abre esta etapa lo dice con números, no con adjetivos.

### 0.1 ¿Alcanza el backend a los servidores? — Sí

Comprobado **desde el backend**, no desde una prueba:

```
SI  lab_servidor:22 · lab_servidor:8080 · lab_db:5432 · influxdb:8086 · grafana:3000
```

Y no por casualidad: en O2c quedó declarado en `docker-compose.lab.yml`, así que
sobrevive a un recreate. **No hay parada.**

### 0.2 ¿Qué veía Fredy de sus servidores desde Kinetix? — Nada

| En su instancia (el 8001) | |
|---|---|
| Servidores dados de alta | **0** |
| Token de lectura cargado | **ninguno** |

Kinetix no podía leer el cubo `infra` ni aunque quisiera. Todo lo de O2a y O2b
existía, pero solo se veía en Grafana y solo si alguien abría el tablero y
acertaba la corrida.

### 0.3 Lo reutilizable

Cubo `infra` con cuatro hosts · el token de lectura de O-D33 · los tableros ·
los endpoints de O2c · `services/jmx_parser.py`, que se usa **en solo lectura** ·
y **recharts, que ya estaba en el producto**: ni una librería nueva.

---

## 1. Los documentos, escritos ANTES que la pantalla

Era la condición del sub-paso O2d.1: si no se pueden escribir con datos reales,
la pantalla no se puede usar.

- **`docs/observabilidad/datos-de-prueba.md`** (O-D43) — dirección, puerto y
  usuario exactos de los dos servidores del laboratorio. **Las credenciales no
  están escritas ahí**: este documento va al repositorio y el repositorio va a
  GitHub. En su lugar, un comando de PowerShell por cada una que la deja en el
  portapapeles. Probados los dos: 28 caracteres la de la base, 88 el token.
- **`docs/observabilidad/manual-de-pruebas.md`** (O-D44) — paso a paso, y en
  cada paso **qué número tiene que ver y cuál sería un valor equivocado**.
  Las cifras son medidas, no inventadas, y se actualizaron al terminar con lo
  que dio la prueba de punta a punta.
- **O-D47** — el manual dice, en su propia sección, lo que el producto **no**
  hace: el agente no sirve para un servidor de un cliente hasta que exista el
  punto de entrada HTTPS (la etapa O2e), Windows no se puede probar, y las
  alertas no existen.

---

## 2. La sesión de monitoreo (O-D35, O-D36, O-D37, O-D40)

`monitoring_sessions` y su tabla de unión, creadas por `create_all` sin un
`ALTER` a mano. Una sesión guarda nombre, cliente, proyecto, **qué servidores se
miran**, su corrida, su estado y sus fechas.

**Eso es lo que Fredy perdía.** Hasta O2c, una corrida era una cadena que había
que copiar antes de cambiar de pestaña.

El asistente son tres pasos (O-D37), y el segundo es el que no existía:

```
1. Qué se va a probar     cliente, proyecto y qué servidores se observan
2. Conecta tu JMeter      <-- el que faltaba
3. Ver la sesión
```

### 2.1 Un fallo de producto que salió al probar

`nombre_de_corrida()` (O-D4) tiene resolución de **minuto**. Dos sesiones del
mismo cliente y proyecto creadas en el mismo minuto daban la misma cadena,
chocaban contra el índice único y devolvían **500 Internal Server Error**.

No es rebuscado: creas una sesión, ves que le pusiste mal el nombre, creas otra.

Arreglado sin tocar el formato de O-D4 —que es la definición única que comparten
el Backend Listener y el recolector—: si la cadena está cogida, se le añade un
sufijo. Comprobado con tres sesiones seguidas:

```
zztest-...-2334      zztest-...-2334-2      zztest-...-2334-3
```

Y se vio funcionar solo en la prueba de punta a punta, que al correr dos veces
seguidas generó una corrida terminada en `-2`.

---

## 3. Conectar JMeter (O-D45, O-D46)

**Por qué hacía falta.** JMeter no envía sus métricas a ningún sitio por su
cuenta. Hasta ahora, la pantalla daba diez parámetros y alguien tenía que
copiarlos uno a uno dentro de JMeter. Eso es lo que Fredy no entendió, y no es
trabajo de una persona.

Ahora se sube el `.jmx` y **Kinetix le pone el Backend Listener**, ya configurado
con los valores de la sesión, y devuelve una copia lista para ejecutar. Copiar
los parámetros a mano sigue estando, **plegado**, como lo que es: la salida de
emergencia.

`services/observabilidad/jmx_listener.py`, módulo nuevo (O-D46): no toca
`jmx_parser.py` —que solo lee— ni ninguna carpeta protegida.

### 3.1 Los tres casos, probados con archivos de verdad

```
1. Un .jmx SIN Backend Listener   -> se le anade, dentro del grupo de hilos
2. Uno que YA lo trae             -> se REEMPLAZA, no se duplica, y se avisa
3. Un XML que no vale             -> error claro, no un volcado de pila
```

Y lo que de verdad importa, que no se comprueba leyendo el XML:

```
PASA | JMeter carga el plan sin quejarse
PASA | y lo ejecuta hasta el final
     summary = 4 in 00:00:01 = 7.1/s  Err: 0 (0.00%)
```

El original **nunca se modifica**: lo que baja es una copia, y la pantalla lo
dice con esas palabras.

---

## 4. Las gráficas dentro de Kinetix (O-D38, O-D39, O-D41)

`SesionPage.tsx`. Arriba **«Métricas de la prueba»**, abajo **«Métricas de la
infraestructura»**, con el mismo eje de tiempo y a todo el ancho.

Por cada servidor Linux: CPU, memoria, disco y red. Por cada PostgreSQL:
conexiones y transacciones por segundo. Con recharts, que ya usaba el producto.

### 4.1 La corrección que decide la etapa

La primera versión filtraba las métricas de infraestructura por la etiqueta
`corrida`, siguiendo O-D14. **Y la mitad de abajo salía siempre vacía.**

La causa, medida y no supuesta:

```
etiquetas `corrida` en el cubo infra:  sin-corrida, zztest-comparacion-..., ...
la corrida de la sesion:               zztest-observabilidad-...-2346   <-- no esta
```

**La etiqueta la pone el recolector, y ponérsela exige ir a reconfigurarlo antes
de cada prueba** (en el laboratorio, `scripts/lab_corrida.sh`). Desde una
pantalla nadie se acuerda de eso — y en casa de un cliente Kinetix **no tiene
ningún canal** para tocarle el recolector.

Así que se cruza por **servidor y ventana de tiempo**, que además es lo correcto
conceptualmente: las métricas de infraestructura son continuas —el servidor
existe antes y después de la prueba— y una sesión es una **ventana** sobre
ellas. La etiqueta se sigue escribiendo y el tablero de Grafana la sigue usando;
aquí no hace falta.

> **Consecuencia que conviene tener presente:** el tablero de Grafana de O2a
> **sigue** filtrando por `corrida`, así que para usarlo sigue haciendo falta
> el paso manual. La pantalla de sesiones ya no.

### 4.2 Y el aviso, cuando no hay nada

Una gráfica vacía sin explicación es el peor resultado posible: parece que el
producto no va. Hay tres mensajes distintos, y cada uno dice qué hacer: falta el
token de lectura · la sesión no tiene servidores · llegan las de la prueba pero
no las del servidor.

---

## 5. El menú (O-D42)

**«Metricas Monitoreo» pasa a llamarse «Capturas de infraestructura»** y se
queda en Análisis. Con una sección llamada Observabilidad al lado, el nombre
viejo era una trampa: quien buscara las métricas de sus servidores pincharía
ahí. Estaba anotado en el reporte 103 §5 y ahora está hecho.

«Sesiones de monitoreo» pasa a ser **la primera entrada** de Observabilidad: es
lo que se usa para una prueba normal. «Monitoreo en vivo» queda debajo.

---

## 6. La prueba de punta a punta (O2d.5)

El recorrido entero desde el navegador, **el que Fredy no podía hacer**. Y la
comprobación que decide si esto sirve no es que un endpoint devuelva números,
sino que **se vean en la pantalla**:

```
PASA | las graficas del servidor tienen trazos dibujados (5)
PASA | y las de la prueba tambien (10)

CPU:         minimo  5.0 %  ·  maximo 94.6 %
Conexiones:  minimo  0     ·  maximo 21
```

La CPU sube a **94,6 %** durante la prueba y las conexiones a la base pasan de 0
a **21**. Se cierra la sesión, se vuelve a la lista, se abre otra vez, y **sigue
enseñando lo que pasó** (O-D40): 5 trazos, no una pantalla vacía.

---

## 7. La regresión

```
=== LA BASE DE FREDY, ANTES ===        === LA BASE DE FREDY, DESPUES ===
86f88bf73ffe47f15226188e5c58caaa       86f88bf73ffe47f15226188e5c58caaa
24 10 8 13 5 5                         24 10 8 13 5 5

SI — la base de Fredy no cambio ni una fila
suites: 18 · con fallo: 0    ·    654 comprobaciones
```

Una suite falló por el camino y **falló con razón**: `o2c_pantalla.py`
comprobaba que Análisis conservara «Metricas Monitoreo», que es justo lo que
O-D42 renombró. El desfasado era el script. Es la tercera vez que pasa —los
títulos acentuados, el menú de O2c— y por eso queda escrito otra vez.

---

## 8. Dos fallos míos, de los que enseñan

### 8.1 Poner una cabecera en la respuesta no basta

El mensaje de qué se le hizo al `.jmx` llegaba **vacío** a la pantalla. Lo
mandaba en `X-Kinetix-Mensaje` y hasta ponía `Access-Control-Expose-Headers` en
la propia respuesta. No sirve de nada: **lo que manda es la lista
`expose_headers` del `CORSMiddleware`**, y sin estar ahí el navegador recibe la
cabecera y no deja leerla.

### 8.2 Arrastrar una decisión a un sitio donde ya no vale

O-D14 —la etiqueta `corrida` como llave de la correlación— es correcta para el
tablero de Grafana, donde eliges una corrida de una lista. La llevé tal cual a
la pantalla de sesiones sin preguntarme **quién le pone esa etiqueta al
recolector**, y la respuesta era «una persona, a mano, antes de cada prueba».
La consecuencia fue reproducir exactamente la queja que abrió la etapa: media
pantalla vacía. Lo cazó la prueba de punta a punta, no la revisión del código.

---

## 9. Lo que no se ha comprobado (regla 33)

- **Fredy no ha validado nada**: ni O2d, ni O2c, O2b, O2a, O1, H5, H6 o H7.
- **El punto de entrada HTTPS sigue sin existir** (O-D47). El modo con agente
  solo sirve en red compartida. Es la etapa **O2e**.
- **El tablero de Grafana sigue exigiendo el paso manual** de la corrida (§4.1).
  La pantalla de sesiones ya no, pero el tablero no se tocó.
- **No hay alertas.** Ver que la CPU llegó al 94 % es una cosa; que alguien
  avise es otra, y no está hecha.
- **El nombre del servidor tiene que coincidir** con la etiqueta `host` que
  publica el recolector. En el laboratorio coinciden; con un cliente hay que
  cuidarlo, y si no coinciden la pantalla lo dice pero no lo arregla sola.
- **Windows sigue sin poder probarse** desde la pantalla de Servidores.
- **Una sesión no arranca ni para el JMeter**: lo lanza una persona. Kinetix
  genera el archivo (O-D28 sigue mandando).
- **No se tocó el servidor de Azure**, ni `services/engine/`, ni ningún archivo
  protegido.

---

## 10. Estado

**Etapa O2d implementada, pendiente de validación de Fredy.**
