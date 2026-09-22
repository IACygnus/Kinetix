2ebb65b · 2026-09-22

# O2a para Fredy — un guion, tres pantallas

Todo lo de la etapa se comprueba con **un solo recorrido**: levantar el
laboratorio, lanzar una prueba desde Monitoreo en vivo, y ver en Grafana la
prueba y el servidor en la misma corrida.

El laboratorio ya está levantado y la prueba ya se corrió una vez. Esto es para
que lo veas tú.

---

## Qué se hizo, en cuatro frases

1. Hay un **laboratorio** con dos servidores de mentira —un Linux con una
   tienda y un PostgreSQL con millón y medio de filas— en un Compose aparte que
   no toca nada de Kinetix.
2. Un **recolector** los mira **sin instalarles nada**: al Linux le entra por
   SSH con un usuario sin privilegios, y a la base por su puerto con un rol de
   solo lectura.
3. Lo que recoge se escribe **con los mismos nombres que usaría un agente**, y
   con **la misma etiqueta de corrida** que la prueba de JMeter.
4. Por eso se puede poner, en la misma gráfica, **el tiempo de respuesta de tu
   prueba y la CPU del servidor que la está aguantando**.

---

## El guion

### Paso 1 — ¿está el laboratorio en pie?

```
docker ps --filter name=lab_
```

Tienen que salir tres: `lab_db`, `lab_servidor` y `lab_colector`.

Si no estuvieran, o si quieres rehacerlo desde cero:

```
cd C:\proyectos\Kinetix
bash scripts/lab_preparar.sh
docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml up -d --build
```

`lab_preparar.sh` es idempotente: se puede repetir sin miedo. Crea la pareja de
llaves SSH, el cubo `infra` en InfluxDB y su token de **solo escritura**.

Y para comprobar que la aplicación del laboratorio vive:

```
curl http://127.0.0.1:8090/salud
curl "http://127.0.0.1:8090/buscar?q=a1b"
```

La primera responde en 4 milisegundos. La segunda tarda **medio segundo largo**:
recorre el millón y medio de filas sin índice, y está hecha así a propósito.

---

### Paso 2 — lanzar la prueba

```
cd C:\proyectos\Kinetix
bash scripts/lab_prueba_correlacion.sh
```

Tarda unos **cinco minutos** y hace esto, a la vista:

- le pide a Kinetix la configuración de la corrida **por los mismos endpoints
  que usa la pantalla de Monitoreo en vivo**;
- le pone esa corrida al recolector;
- mide **70 segundos en reposo**, lanza **dos minutos de carga**, y mide otros
  **70 segundos en reposo**;
- y luego pregunta a los datos si se nota.

Lo que salió la última vez:

| | reposo antes | **durante la prueba** | reposo después |
|---|---|---|---|
| CPU de la máquina (por SSH) | 10,2 % | **89,2 %** | 20,1 % |
| CPU del contenedor de la app | 3,8 % | **12,0 %** | 3,4 % |
| CPU del contenedor de la base | 0,0 % | **672,2 %** | 0,0 % |
| Transacciones de PostgreSQL | 0,6 /s | **13,2 /s** | 0,7 /s |

La base se llevó casi siete núcleos.

---

### Paso 3 — verlo en Grafana

```
http://localhost:3000/d/kinetix-infraestructura
```

Arriba del todo, el selector **«Corrida»**. Elige
`zztest-laboratorio-o2a-zztest-tienda-20260922-1333` (o la que acabe de salir) y
pon el rango en **«Last 1 hour»**.

Cuatro bloques:

| Bloque | Qué mirar |
|---|---|
| **El servidor** | La CPU sube a 90 % durante la prueba y baja sola. La carga del sistema la sigue |
| **La base de datos** | Las transacciones por segundo, el acierto de caché, y **las diez consultas más lentas** — ahí verás la búsqueda pesada con su media |
| **Los contenedores** | Lo mismo pero por contenedor, que es más preciso |
| **La prueba y el servidor** | **El panel que importa.** Dos líneas: el tiempo de respuesta de JMeter y la CPU del servidor. Vienen de dos sitios distintos y se cruzan por una sola etiqueta |

Ese último panel es toda la etapa en una imagen: cuando la CPU llega al 90 %, el
tiempo de respuesta pasa de 618 a 1.062 milisegundos.

---

## Lo que quiero que mires con ojo crítico

1. **El panel de abajo del tablero.** ¿Se entiende de un vistazo que las dos
   líneas son la misma prueba? Si no se entiende, sobra o hay que rehacerlo.
2. **`docs/observabilidad/requisitos-sin-agente.md`.** Es lo que le mandaríamos
   al área de infraestructura de un cliente. **Léelo como si fueras ellos**: ¿te
   daría confianza, o te pondría nervioso? Sobre todo la sección 4, la de Docker,
   donde decimos con todas las letras que ese permiso equivale a administrador.
3. **Si falta algo que tú preguntarías en una prueba real.** Yo puse CPU,
   memoria, disco, red, procesos, conexiones, transacciones, bloqueos, caché,
   tamaño y consultas lentas. Tú sabes mejor que yo qué se mira cuando algo va
   lento.

---

## Lo que no está hecho, para que no te lleves sorpresas

- **Nada de esto se ha probado contra un servidor de verdad**, solo contra
  contenedores que hacen de servidores. La técnica es la misma; las cifras de
  CPU y memoria, en este laboratorio, son de tu portátil y no del «servidor»,
  porque un contenedor no separa eso. En una máquina virtual de un cliente sí
  serían del servidor. Está explicado en el reporte 99 §2.3.
- **Windows Server, Oracle, SQL Server y MySQL no están.** Ni empezados.
- **El modo con agente es la etapa siguiente (O2b).** Lo único que se hizo para
  que llegue sin dolor es que los nombres de las métricas coincidan — y eso está
  comprobado campo a campo: **cero campos que tenga el agente y no tengamos
  nosotros**.
- **La comprobación de los puertos desde otra máquina sigue pendiente**, igual
  que en O1. Desde este equipo el 8086 y el 3000 ya no responden por la IP de la
  red; falta probarlo desde otro portátil.
- El servidor de Azure **no se tocó**.

---

## Si quieres borrarlo todo

```
docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml down -v
```

Eso se lleva los tres contenedores y el millón y medio de filas. **No toca nada
de Kinetix.** El cubo `infra` de InfluxDB se queda; si también lo quieres fuera,
dímelo y lo quito — no borro nada de InfluxDB sin pedírtelo.

---

## Estado

**Etapa O2a implementada, pendiente de validación de Fredy.**

La regresión completa quedó en **504 comprobaciones, 13 suites, cero fallos**, y
la huella de tu base de datos es **idéntica antes y después**.
