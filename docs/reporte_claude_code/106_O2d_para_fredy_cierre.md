7b14aa2 · 2026-09-22

# O2d para Fredy — la pantalla que faltaba

Tenías razón en todo. O1 a O2c construyeron la tubería y **nadie construyó el
grifo**. Lo comprobé antes de escribir una línea: en tu instancia había **cero
servidores dados de alta** y **ningún token de lectura**, así que Kinetix no
podía enseñarte nada de tus servidores ni aunque quisiera.

Esta etapa construye la pantalla.

---

## El guion

Todo lo que necesitas está en dos documentos nuevos:

- **`docs/observabilidad/datos-de-prueba.md`** — los datos exactos de los dos
  servidores del laboratorio, con el comando que pone cada credencial en el
  portapapeles.
- **`docs/observabilidad/manual-de-pruebas.md`** — el paso a paso, y en cada
  paso **qué número tienes que ver y cuál sería un valor equivocado**.

Aquí va lo corto.

### 1. El token de lectura (una vez)

**Observabilidad → Sesiones de monitoreo.** Si sale un aviso naranja, pega ahí
el token:

```powershell
docker exec jmeter_influxdb influx auth list --host http://localhost:8086 `
  -t jmeter-token-2024-super-secret |
  Select-String 'kinetix-lectura' |
  ForEach-Object { ($_ -split '\s+')[2] } | Set-Clipboard
```

Sin esto no hay gráficas. Es el fallo número uno, y por eso la pantalla te lo
dice en vez de quedarse en blanco.

### 2. Dar de alta los servidores

**Observabilidad → Servidores.** Los datos, en `datos-de-prueba.md`.

### 3. Crear una sesión

**Sesiones de monitoreo → Nueva sesión.** Tres pasos:

1. **Qué se va a probar** — cliente, proyecto, y **qué servidores se observan**
   (salen marcados solos).
2. **Conecta tu JMeter** — aquí está lo nuevo: **sube tu `.jmx` y te lo
   devolvemos con el Backend Listener puesto**, ya configurado. Se descarga
   solo. Tu archivo original no se toca.
3. **Ver la sesión.**

> Lo de copiar diez parámetros a mano sigue estando, **plegado**, para cuando
> haga falta. Ya no es lo primero que ves, porque no es trabajo de una persona.

### 4. Lanzar y mirar

Ejecuta el `.jmx` que acabas de descargar y quédate en la pantalla de la sesión.

**Arriba, «Métricas de la prueba».** Abajo, **«Métricas de la infraestructura»**,
un bloque por servidor: CPU, memoria, disco y red; y de la base, conexiones y
transacciones. **Con el mismo eje de tiempo.** Ver la causa y el efecto juntos
es la idea entera.

### 5. Vuelve mañana

Cierra la pestaña. Vuelve a Sesiones, abre la misma. **Sigue ahí, con sus
gráficas.** Eso es lo que perdías.

---

## Las cifras que salieron en la última prueba

| | Antes | Durante | Después |
|---|---|---|---|
| CPU de `lab_servidor` | 5 % | **94,6 %** | vuelve a 5-15 % |
| Conexiones a `lab_db` | 0 | **21** | vuelve a bajar |

Si ves algo muy distinto, el manual dice qué significa cada valor equivocado.

---

## Tres cosas que quiero que sepas

**Un fallo de producto que encontré y arreglé.** El nombre de la corrida tiene
resolución de minuto, así que **dos sesiones del mismo proyecto en el mismo
minuto daban un 500**. Es un caso normal —creas una, ves que le pusiste mal el
nombre, creas otra—. Ahora se le añade un sufijo.

**Una decisión mía que estaba mal y la prueba destapó.** La primera versión
filtraba las métricas de los servidores por la etiqueta de corrida, como hace el
tablero de Grafana. **Y la mitad de abajo salía siempre vacía** — exactamente tu
queja. La causa: esa etiqueta la pone el recolector, y ponérsela exige ir a
reconfigurarlo antes de cada prueba. Nadie hace eso desde una pantalla, y en
casa de un cliente no tenemos forma de tocarles el recolector.

Ahora se cruza **por servidor y ventana de tiempo**, que además es lo correcto:
las métricas de un servidor son continuas, y una prueba es una ventana sobre
ellas. **Ojo:** el tablero de Grafana sigue como estaba, así que para usar *ese*
sigue haciendo falta el paso manual. La pantalla nueva no.

**Lo de «Metricas Monitoreo».** Lo renombré a **«Capturas de infraestructura»**
y sigue en Análisis. Con una sección llamada Observabilidad al lado, el nombre
viejo era una trampa.

---

## Lo que sigue sin hacer

- **El agente no sirve para un servidor de un cliente.** Falta el punto de
  entrada HTTPS en `kinetix.sqasa.co`. Es la **O2e**. Mientras tanto, para un
  cliente remoto el modo que sirve es sin agente.
- **No hay alertas.** Ver que la CPU llegó al 94 % es una cosa; que alguien te
  avise es otra.
- **Windows sigue sin poder probarse** desde la pantalla de Servidores.
- **Kinetix no lanza ni para tu JMeter.** Te da el archivo; lo ejecutas tú. Eso
  es a propósito: no guardamos credenciales de administrador de nadie.
- **Nada de esto ha visto un servidor de verdad**, sigue siendo el laboratorio.

---

## Estado

**Etapa O2d implementada, pendiente de validación de Fredy.**

Regresión: **654 comprobaciones, 18 suites, cero fallos**, y la huella de tu
base de datos **idéntica antes y después**.
