958cba9 · 2026-09-21

# ETAPA O1 — para Fredy

---

## Qué hace ahora

Antes de esta etapa, la cadena InfluxDB → Grafana **no había funcionado nunca**
—eso es lo del reporte 96—. Ahora funciona, y encima con una pantalla que le
escribe a usted la configuración en vez de pedirle que la recuerde.

**Menú → Análisis → Monitoreo en vivo.**

---

## El guion, de principio a fin

### 1. Abra «Monitoreo en vivo»

Está en el menú **Análisis**, debajo de «Metricas Monitoreo». Son cosas
distintas: aquélla son capturas de infraestructura que analiza la IA; ésta es la
prueba mientras corre.

### 2. Elija cliente y proyecto

El cliente sale de su catálogo. El proyecto lo escribe usted —el campo sugiere
los que ya ha usado con ese cliente, pero puede poner cualquiera—.

Pulse **Generar configuración**.

### 3. Copie lo que le da

Arriba, en la banda azul, sale el nombre de la corrida. Por ejemplo:

```
compensar-prueba-de-carga-q3-20260921-1600
```

Lo pone Kinetix: cliente, proyecto y el momento. En minúsculas y sin tildes,
porque va como etiqueta dentro de InfluxDB.

Debajo, los **diez parámetros** del Backend Listener de JMeter, cada uno con su
botón de copiar y una línea que dice para qué sirve. El token sale tapado; hay
un botón **«Ver el token»** para cuando lo necesite, y así no se le cuela en una
captura de pantalla.

Si prefiere no ir copiando uno a uno: **«Descargar el componente .jmx»** le da el
elemento entero ya relleno, para pegarlo dentro de su Thread Group.

### 4. Pegue eso en su JMeter y lance la prueba

En su plan de pruebas, añada un **Backend Listener**, elija la clase
`InfluxdbBackendListenerClient` y ponga los diez valores. O pegue el fragmento
que descargó.

**Importante:** el JMeter tiene que correr **en esta misma máquina**. Los puertos
de InfluxDB y de Grafana se cerraron a la red (era la decisión O-D1), así que una
inyectora de otro equipo hoy no llega. Eso se puede abrir, pero es una decisión
aparte —con su regla de cortafuegos— y no la tomé yo.

### 5. Véala en vivo

Vuelva a la pantalla: abajo está el tablero de Grafana **filtrado por su
corrida**. Nueve paneles: tiempos de respuesta, hilos activos, errores,
throughput, percentiles, y el detalle por transacción.

Si lanza dos pruebas, cada una tiene su nombre y el tablero enseña solo la que
usted eligió. Antes no: todo se superponía en el mismo panel.

Arriba del tablero puede cambiar el rango («Últimos 15 minutos») y cada cuánto
se refresca.

---

## Lo que arreglé por dentro, en una línea cada cosa

1. **La fuente de datos de Grafana.** El archivo de provisión usaba
   `${VARIABLE:-valor}`, que es sintaxis de bash y Grafana no entiende; y además
   al contenedor de Grafana no le llegaba ninguna variable de InfluxDB. La
   organización quedaba en blanco y todos los paneles salían vacíos sin decir por
   qué.
2. **El tablero al que apuntaba la pantalla no existía.** Pedía
   `jmeter-realtime`; el que hay se llama `jmeter-performance`. Eran los valores
   por defecto del modelo, puestos en marzo y nunca comprobados contra nada.
3. **El token guardado no se podía descifrar.** Se había cifrado con otra clave.
4. **Los puertos.** InfluxDB (8086) y Grafana (3000) escuchaban en todas las
   interfaces y respondían desde la red; con Grafana en anónimo, cualquiera que
   alcanzara la máquina veía los tableros. Ahora solo responden en el equipo.
5. **El token nuevo.** Solo escritura, y solo en el cubo `jmeter`. Comprobado:
   con él no se puede leer nada, ni escribir en otro cubo, ni ver la lista de
   tokens. El de operador —el que sí puede todo— no se enseña en ninguna
   pantalla.

---

## Una cosa que hice mal y conviene que sepa

Probando el alcance del token escribí un punto a mano en InfluxDB con un número
entero donde JMeter escribe decimales. **La primera escritura fija el tipo del
campo**, así que a partir de ahí InfluxDB empezó a rechazar todas las filas por
transacción de JMeter con un error 422, y borrar mi punto no bastó: el tipo
siguió fijado hasta borrar la medida entera.

Lo borré —solo datos míos, marcados `zztest-`, en un cubo que estaba vacío— y
desde entonces entra todo bien. Queda escrito en CLAUDE.md como regla: **no se
escribe a mano en una medida que produce un programa.**

---

## Lo que queda fuera, y por qué

- **Que el motor propio de Kinetix publique en InfluxDB.** Hoy no lo hace, y
  ponerlo toca `services/engine/`, que es carpeta protegida, y añade una
  dependencia nueva. Va aparte, con su permiso.
- **El WebSocket de métricas vivas del motor**, que en desarrollo no llega al
  navegador. Es del motor: mismo paquete.
- **Abrir InfluxDB a una inyectora de fuera.** Decisión suya.

---

## Lo que falta hacer, y es de usted

Para que la fuente de datos quede arreglada hay que **reiniciar dos
contenedores**, y los contenedores son suyos (regla 7). El comando exacto está
al final del reporte 97 y se lo doy también en el chat.

---

**Estado: Etapa O1 implementada, pendiente de su validación.**
