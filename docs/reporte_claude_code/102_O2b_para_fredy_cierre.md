75cb593 · 2026-09-22

# O2b para Fredy — un guion: los dos modos en el mismo tablero

El laboratorio está levantado, el agente instalado y corriendo. Esto es para que
lo veas tú.

---

## Qué se hizo, en tres frases

1. Hay un **Agente Kinetix** —Telegraf 1.29.5— que se instala **dentro** del
   servidor con una orden, corre con un usuario sin privilegios, y mide **una
   vez por segundo** en vez de una cada diez.
2. Escribe **con los mismos nombres** que el modo sin agente, así que el mismo
   tablero sirve para los dos: solo cambia de dónde vienen los datos.
3. Y se quita con otra orden, que **comprueba** que no ha dejado nada.

---

## El guion

### Paso 1 — lanza una prueba con los dos modos a la vez

```
cd C:\proyectos\Kinetix
bash scripts/lab_comparar_modos.sh
```

Tarda unos **cuatro minutos**. Hace, a la vista:

- pone la misma corrida en los dos modos;
- mide lo que cuesta el agente **en reposo**;
- provoca **un pico de CPU de tres segundos a propósito**;
- enseña qué vio cada modo de ese pico;
- lanza una prueba de carga de 90 s;
- y mide lo que cuesta el agente **durante** la prueba.

### Paso 2 — míralo en Grafana

```
http://localhost:3000/d/kinetix-infraestructura
```

Arriba hay **dos selectores**: «Modo» y «Corrida». Elige la corrida que acabe de
salir y pon el rango en «Last 15 minutes».

**Baja del todo, a la fila «Los dos modos, lado a lado».** Ahí están las dos
curvas de la misma máquina, medida de las dos formas. Donde la carga es
sostenida se pisan; donde se separan es en los picos.

Y al lado, el panel de cuántos puntos escribe cada modo por minuto: **60 y 6**.

### Paso 3 — el selector «Modo», arriba

Cámbialo de `sin_agente` a `agente` y mira la fila de arriba, la del servidor.
**Los paneles no cambian de consulta**: las mismas medidas, los mismos campos,
los mismos nombres. Solo cambia la resolución.

Eso es toda la promesa de la etapa: **si mañana instalas el agente en un
cliente que hoy se mide sin agente, no hay que rehacer un solo tablero ni una
sola alerta.**

---

## Los tres números que vas a querer citar

### 1. Qué ve el agente que el otro no

Un pico de CPU de **tres segundos**, con la máquina en reposo:

| Modo | El máximo que reportó |
|---|---|
| **Con agente** (1 s) | **96,3 %** |
| Sin agente (10 s) | **25,9 %** |

Los dos son correctos. El de diez segundos promedia, y un pico de tres segundos
dentro de una ventana de diez sale dividido por cuatro. **Quien mirase solo la
segunda cifra diría que el servidor iba holgado.**

### 2. Qué cuesta el agente

| | |
|---|---|
| CPU | **0,5 % de un núcleo** (0,07 % de una máquina de 8) |
| Memoria propia | **~60 MB** |
| Red | **~3 kB/s** |
| Disco | nada |

Y hay un **techo que hace cumplir el núcleo**, no nosotros: 256 MB y el 20 % de
un núcleo. Si el agente intentara pasarse, el sistema lo frena.

Ojo con un detalle que te van a preguntar: `top` dirá **155 MB**, no 60. Los
otros 92 MB son el propio programa mapeado desde disco (el ejecutable de
Telegraf pesa 218 MB) y el sistema los descarta en cuanto necesita memoria. La
cifra honesta es 60.

### 3. Qué pasa si se cae la red

Cortamos la red del servidor **tres minutos** mientras trabajaba. Al volver:

```
puntos del agente durante el corte: 183 de 183 esperados
el agente recupero el 100 % del corte
```

**No se perdió un segundo.** El agente guarda en memoria y lo manda al volver.
Con lo que entregamos aguanta unos 40 minutos — pero eso último es una cuenta,
no una prueba: **lo probado son tres minutos**, y así está dicho en el documento
del cliente.

---

## Lo que quiero que mires con ojo crítico

1. **El panel de abajo del tablero, el de los dos modos.** ¿Se entiende que son
   la misma máquina medida de dos formas? Si no se entiende de un vistazo, hay
   que rehacerlo.
2. **`docs/observabilidad/requisitos-con-agente.md`.** Léelo como si fueras el
   área de infraestructura del cliente. Fíjate sobre todo en §1 (por qué un
   agente), §3 (lo que consume) y §8 (la tabla que compara los dos modos), que
   es la que se usa para decidir.
3. **Los dos guiones de instalación y desinstalación.** Son lo que le vamos a
   pedir a un cliente que ejecute en su servidor. ¿Te parecen suficientemente
   claros y suficientemente reversibles?

---

## Lo que NO está hecho, para que no te lleves sorpresas

- **El instalador de Windows está escrito pero NO probado.** Nuestro
  laboratorio es Linux. Se ha comprobado que los dos guiones de PowerShell
  analizan sin errores de sintaxis, y nada más: **no se han ejecutado nunca
  contra un Windows Server**. La huella del paquete de Windows está sin fijar, a
  propósito, con un aviso dentro. No lo instales en ningún sitio hasta que lo
  probemos.
- **El corte de red probado es de tres minutos.** Los 40 son una cuenta.
- **Nada de esto ha visto un servidor de verdad**, sigue siendo el laboratorio.
  En un contenedor, la CPU y la memoria que se leen son las del portátil, no las
  del «servidor»; en una máquina virtual de un cliente no hay esa ambigüedad.
- **El paquete de Telegraf no viene con firma del fabricante.** Verificamos su
  huella, pero esa huella la calculamos nosotros. El camino bueno —el
  repositorio firmado con GPG de InfluxData— existe y responde, y lo comprobé,
  pero no está implementado. Si un cliente lo exige, es una tarde de trabajo.
- **No se ha medido el agente en un servidor grande** (cientos de discos, miles
  de procesos). Las cifras son de un servidor pequeño.

---

## Un fallo mío que conviene que sepas

En la primera versión, el agente arrancaba pasando el token de InfluxDB en la
línea de órdenes. **Cualquiera con acceso al servidor lo habría visto con `ps`**
— y es exactamente la fuga contra la que avisa, escrito por mí, el documento de
permisos del otro modo.

Está arreglado: el proceso lee el token él mismo de un fichero que solo él
puede leer, y el instalador **comprueba al terminar** que el token no aparece en
la línea de órdenes de ningún proceso. Se añadió además `--token-fichero`, para
que ni siquiera durante la instalación esté expuesto.

Lo cuento porque si esto hubiera llegado a un cliente sin que nadie lo mirara,
habría sido un hallazgo de auditoría.

---

## Si quieres quitar el agente

```
docker exec lab_servidor bash /opt/kinetix-instalador/desinstalar_agente.sh
```

Te va a enseñar, línea por línea, qué comprueba que ya no está. Y si quieres
volver a ponerlo, el guion de instalación está al lado.

---

## Estado

**Etapa O2b implementada, pendiente de validación de Fredy.**

La regresión completa quedó en **507 comprobaciones, 13 suites, cero fallos**, y
la huella de tu base de datos es **idéntica antes y después**.
