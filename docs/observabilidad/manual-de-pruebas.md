# Manual de pruebas de Observabilidad

**Para probarlo sin haber visto el código.** Cada paso dice **qué número tienes
que ver** y **cuál sería un valor equivocado**, para que sepas si funciona o si
está fingiendo que funciona.

Tarda unos **20 minutos** la primera vez.

---

## Qué estás probando, en una frase

Que mientras corre una prueba de carga puedas ver, **en la misma pantalla y con
el mismo eje de tiempo**, el tiempo de respuesta de tu prueba arriba y lo que le
está pasando al servidor abajo. Eso es todo el módulo.

---

## Antes de empezar

### 1. El laboratorio en pie

```powershell
docker ps --filter name=lab_
```

**Tienes que ver tres:** `lab_db`, `lab_servidor` y `lab_colector`.
**Si ves menos de tres**, levántalo:

```powershell
cd C:\proyectos\Kinetix
bash scripts/lab_preparar.sh
docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml up -d --build
```

### 2. La aplicación del laboratorio responde

```powershell
curl http://127.0.0.1:8090/salud
```

**Tienes que ver** `{"estado": "ok"}`.
**Valor equivocado:** un error de conexión. Entonces `lab_servidor` no está.

### 3. La búsqueda pesada tarda de verdad

```powershell
Measure-Command { curl http://127.0.0.1:8090/buscar?q=a1b } | Select-Object TotalMilliseconds
```

**Tienes que ver entre 500 y 900 milisegundos.**
**Valor equivocado:** menos de 100 ms. Eso significa que la base se sembró con
pocas filas y la prueba no va a hacer sudar a nadie; rehaz el laboratorio.

---

## Paso 1 — El token de lectura

Sin esto **no hay gráficas**, y es el fallo número uno.

Entra en **Observabilidad → Sesiones de monitoreo**. Si arriba sale un aviso
naranja diciendo que falta el token de lectura, copia el token y pégalo ahí:

```powershell
docker exec jmeter_influxdb influx auth list --host http://localhost:8086 `
  -t jmeter-token-2024-super-secret |
  Select-String 'kinetix-lectura' |
  ForEach-Object { ($_ -split '\s+')[2] } | Set-Clipboard
```

**Tienes que ver** que el aviso desaparece.
**Valor equivocado:** si dice que el token no sirve, es que copiaste el de
escritura. El de lectura es el que se llama `kinetix-lectura`; el de escritura lleva `escritura` en el nombre.

> **¿Por qué dos tokens?** El que ya había solo puede *escribir*, y eso es una
> virtud: es el que se le da a JMeter, y si alguien se lo queda no puede leer
> nada. Para dibujar gráficas hace falta otro que solo pueda *leer*, y que lea
> **los dos depósitos** —el de la prueba y el de los servidores—, porque la
> pantalla los pinta juntos.

---

## Paso 2 — Dar de alta los dos servidores

**Observabilidad → Servidores → Añadir servidor.** Los datos exactos están en
`docs/observabilidad/datos-de-prueba.md`, con el comando para poner cada
credencial en el portapapeles.

Da de alta **`lab_servidor`** y **`lab_db`**.

### Prueba la conexión de `lab_servidor`

**Tienes que ver cuatro líneas con ✓:**

```
Se llega al servidor (unos 500 ms)
  ✓ el puerto 22 responde: SSH-2.0-OpenSSH_8.9p1
  ✓ habla SSH
  ✓ la credencial sirve y /proc se lee: sesion abierta como «kinetix_lector»;
    el servidor dice tener 8 nucleos
  ✓ llegan metricas de este servidor: la ultima, hace 0 segundos
```

**Valores equivocados y qué significan:**

| Lo que ves | Qué pasa |
|---|---|
| `Permission denied (publickey)` | La llave está mal pegada. Tiene que incluir las líneas `-----BEGIN` y `-----END` |
| `Connection refused` | El puerto o la dirección están mal |
| `la credencial (sin comprobar)` | El backend no tiene cliente SSH. Reconstrúyelo: `docker compose up -d --build backend` |
| `ninguna en las ultimas 24 horas` | El recolector no está mirando ese servidor. Mira `docker logs lab_colector` |

### Prueba la conexión de `lab_db`

**Tienes que ver cinco líneas con ✓**, y esta en concreto:

```
  ✓ pg_stat_statements (consultas lentas): 18 filas visibles
```

**Valor equivocado:** `0 filas visibles` en `pg_stat_statements`. Significa que
la extensión no está cargada y el panel de consultas lentas saldrá vacío.

---

## Paso 3 — Crear una sesión de monitoreo

**Observabilidad → Sesiones de monitoreo → Nueva sesión.**

1. **Cliente y proyecto**, y marca **los dos servidores**.
2. **Conecta tu JMeter.** Sube `C:\proyectos\Kinetix\lab\prueba\zztest_lab.jmx`
   y pulsa **«Descargar con el listener puesto»**.
3. **Ver la sesión.**

**Tienes que ver**, al subir el `.jmx`:

```
Listo. Se le insertó el Backend Listener con los valores de esta sesión.
El archivo original no se ha tocado: esto es una copia.
```

**Valor equivocado:** si dice «ya tenía un Backend Listener y se ha
reemplazado», no es un fallo — es lo correcto, y te está avisando. Si dice que
el XML no es un plan de JMeter, subiste otro archivo.

> **¿Por qué hace falta esto?** JMeter no envía sus métricas a ningún sitio por
> su cuenta. El Backend Listener es la pieza que se las manda a Kinetix. Antes
> había que copiar diez parámetros a mano; ahora se los pone Kinetix.

---

## Paso 4 — Lanzar la prueba y mirar

Ejecuta el `.jmx` que acabas de descargar:

```powershell
cd C:\proyectos\Kinetix
docker cp "$HOME\Downloads\<el fichero descargado>" jmeter_backend:/tmp/prueba.jmx
docker exec jmeter_backend /opt/apache-jmeter-5.6.3/bin/jmeter -n -t /tmp/prueba.jmx -l /tmp/prueba.jtl
```

Y **quédate mirando la pantalla de la sesión**.

### Las cifras que tienes que ver

| Cuándo | Qué | Valor correcto | Valor equivocado |
|---|---|---|---|
| **Antes** | CPU de `lab_servidor` | **5-15 %** | más de 40 % → algo más está usando tu máquina; espera a que baje |
| **Antes** | Conexiones a `lab_db` | **0-5** | — |
| **Antes** | Memoria | **10-20 %** | — |
| **Durante** | **CPU de `lab_servidor`** | **por encima del 80 %**. En la última medición: **94,6 %** | si se queda por debajo del 40 %, la prueba no está llegando al servidor |
| **Durante** | Conexiones a `lab_db` | **sube a 15-25**. En la última medición: **21** | si no se mueve, la prueba no está tocando la base |
| **Durante** | Tiempo de respuesta (arriba) | **entre 600 y 1.500 ms** | menos de 100 ms → estás mirando otra corrida |
| **Después** | CPU | **vuelve a 5-15 %** en menos de un minuto | si se queda arriba, quedó algo corriendo |

**La comprobación que importa de verdad:** las dos gráficas —la de arriba, del
tiempo de respuesta, y la de abajo, de la CPU— **suben y bajan a la vez**. Si
una sube y la otra no, o van desfasadas más de diez segundos, hay algo mal.

### Si no ves ninguna gráfica

En este orden:

1. ¿Salió el aviso del token de lectura? → Paso 1.
2. ¿La sesión tiene servidores marcados? → edítala.
3. `docker logs lab_colector --tail 20` → ¿hay errores?
4. ¿El rango de tiempo de la pantalla incluye el momento de la prueba?

---

## Paso 5 — Volver a abrirla

Cierra la pestaña. Vuelve a **Sesiones de monitoreo** y abre la misma.

**Tienes que ver** la sesión con estado **«terminada»** y **las mismas gráficas
con los mismos datos**.
**Valor equivocado:** una pantalla vacía o un error. Una sesión terminada tiene
que poder consultarse; es el registro de lo que pasó.

---

## Lo que el producto NO hace todavía

Esto no son limitaciones ocultas: es lo que falta, dicho aquí para que no te lo
encuentres en una reunión.

- **El agente no se puede usar en un servidor de un cliente.** Hoy solo funciona
  si el servidor y Kinetix comparten red — un laboratorio, o Kinetix desplegado
  dentro de casa del cliente. Para un servidor suyo con Kinetix en nuestra
  infraestructura **hace falta un punto de entrada HTTPS en `kinetix.sqasa.co`
  que todavía no existe**. Es la etapa **O2e**. Mientras tanto, para un cliente
  remoto el modo que sirve es **sin agente**.
- **Windows no se puede probar** desde la pantalla de Servidores. El tipo existe
  y la prueba lo dice con esas palabras; haría falta WinRM.
- **El instalador del agente para Windows está escrito y nunca se ha ejecutado.**
  No lo instales en ningún servidor hasta que lo probemos.
- **Las alertas no existen.** Ver que la CPU llegó al 90 % es una cosa; que
  alguien te avise es otra, y no está hecha.
- **Solo se guarda lo del cubo de infraestructura.** Si borras una sesión, sus
  métricas siguen en InfluxDB: lo que se borra es la sesión, no los datos.

---

## Si quieres dejarlo todo como estaba

```powershell
docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml down -v
```

Se lleva los tres contenedores del laboratorio y su millón y medio de filas. **No
toca nada de Kinetix.** Las sesiones que hayas creado se quedan; bórralas desde
la pantalla si quieres.
