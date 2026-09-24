# Las suites de punta a punta

**Regla 36:** ninguna prueba vive solo dentro de un contenedor. Todo lo de esta
carpeta esta versionado; `/tmp/e2e` es una copia de trabajo que se regenera.

## Por que existe esta carpeta

El 22 de septiembre de 2026 un `docker compose up -d --build backend` recreo el
contenedor y `/tmp/e2e` se fue con el: cuarenta y tantas suites acumuladas desde
H1, las de las Etapas 2 a 6, los relevos de red y la herramienta de sesion.

Se recuperaron casi todas del respaldo de `C:\proyectos\Kinetix_pruebas\e2e\`
—el mismo del que ya se repuso en H3 tras un incidente parecido, reporte 81—,
pero eso fue suerte, no diseno. Ahora la fuente de verdad es el repositorio.

## Como se corre

**Desde el anfitrion, y con esto basta** (ETAPA H8.6):

```sh
bash scripts/regresion_h8.sh
```

Encadena las tres partes y no se salta nada:

1. **El laboratorio (O2a.3)** — unos cinco minutos, lanza carga de verdad. Va
   primero porque deja una corrida recien escrita en los dos cubos, y
   `o2a4_tablero` la necesita **fresca**: los paneles miran los ultimos 40
   minutos.
2. **Las suites de dentro del contenedor** — `cierre_h8.sh`, que sincroniza,
   renueva la sesion, toma la huella de la base de Fredy antes y despues, y la
   compara al final.
3. **Las cifras del informe** — `d1_cifras.sh`, que saca su referencia de git.

Con `--rapido` se salta la 1 y la 3.

Solo la parte de dentro del contenedor, si es lo que hace falta:

```sh
docker exec jmeter_backend sh /app/pruebas_e2e/sincronizar.sh
docker exec jmeter_backend sh /app/pruebas_e2e/cierre_h8.sh
```

Asi se saltan tres suites de observabilidad: sus credenciales viven en
`lab/lab.env`, que no se versiona, y `cierre_h8.sh` **no las lleva escritas
dentro** —`cierre_o2d.sh` si llevaba el token de InfluxDB en claro—. Se saltan
diciendolo, no cuentan como fallo.

### Tres cosas que NO pueden correr desde dentro del contenedor

No es un olvido y no tiene arreglo:

| Qué | Por qué | Cómo |
|---|---|---|
| `o2a3_config.py` · `o2a3_correlacion.py` | Ponen la etiqueta de corrida con `docker kill -s HUP lab_colector` y preguntan a `lab_db` con su psql | `bash scripts/lab_prueba_correlacion.sh` |
| `diseno/d1_cifras.py` | Saca su generador de referencia **de git**, y el contenedor monta `./backend`, no el repositorio | `bash scripts/d1_cifras.sh` |

Las tres, lanzadas sueltas y sin sus requisitos, **dicen que les falta y quien
se lo da**. Antes soltaban un `KeyError` y un `FileNotFoundError`, que no le
cuentan eso a nadie.

## Lo que hace falta en el contenedor, y no esta en `requirements.txt`

Estas dos cosas se instalan a mano y **se pierden en cada reconstruccion del
backend**. No estan en `requirements.txt` a proposito: son de prueba, no del
producto, y no tienen por que viajar a produccion.

```sh
docker exec jmeter_backend pip install playwright
docker exec jmeter_backend playwright install --with-deps chromium

# ETAPA D1: rasterizar un PDF para mirarlo (pruebas_e2e/diseno/pdf_a_png.py)
docker exec jmeter_backend pip install pypdfium2
```

Si una suite de navegador falla con `ModuleNotFoundError: No module named
'playwright'`, es esto. Lo mismo con `pypdfium2` y las comprobaciones de
diseno de `pruebas_e2e/diseno/`.

## Antes de cualquier `--build` del backend

```sh
# ¿Hay algo en /tmp/e2e que no este versionado aqui?
docker exec jmeter_backend sh -c 'ls /tmp/e2e' | sort > /tmp/alla.txt
ls backend/pruebas_e2e | sort > /tmp/aqui.txt
diff /tmp/aqui.txt /tmp/alla.txt
```

Lo que aparezca solo del lado del contenedor, se copia aqui **antes** de
reconstruir. Despues ya no se puede.

## Las suites de la regresion

Las que corre `cierre_o2c.sh`, en orden:

| Suite | Qué protege |
|---|---|
| `h13_backend.sh` | Actividades y proyectos del modulo de horas |
| `h15_pantallas.py` | Las dos pantallas de H1 |
| `h22_backend.py` | El registro de horas |
| `h2b2_backend.py` | El calendario del mes y el estado de desfase |
| `h2b3_pantalla.py` | El calendario de registro, de punta a punta |
| `h32_consulta.py` | La consulta de proyectos |
| `h52_informe.py` | Los datos del informe de horas |
| `h53_h54_documento.py` | El documento HTML y el PDF |
| `h6_ajustes.py` | Los ajustes del veredicto |
| `h71_portada.py` | La portada |
| `h7_pantallas_horas.py` | Consulta, importacion e informe en pantalla |
| `o16_pantalla.py` | Monitoreo en vivo (O1) |
| `probar_tablero.py` | Que los paneles del tablero de infraestructura den datos (O2a) |
| `o2c1_backend.py` | Los servidores observados y O-D26 (O2c) |
| `h82_estados.py` | Los cinco estados del proyecto y qué bloquea cada uno (H8) |
| `h83_pantallas.py` | Estado y consumo, las dos columnas, en pantalla (H8) |
| `h84_mapa.py` | Las horas extra en el mapa del mes (H8) |
| `h85_borrado.py` · `h85_pantalla.py` | El borrado de un periodo y sus tres frenos (H8) |
| `h85b_proyectos.py` · `h85b_pantalla.py` | El importador de proyectos y estimaciones (H8) |
| `carga_borrado_proyecto.py` | `DELETE /time/projects/{id}` y sus guardas (carga real) |
| `carga_actividades_nuevas.py` | La tabla de sinónimos y el aviso de actividades nuevas |
| `corrida_para_tablero.py` | No es una suite: **busca** la corrida con la que probar el tablero |

Y fuera del corredor, porque protegen el informe de JMeter y cuestan mas:
`verificar_etapa2.py` (las cuatro salidas), `captura_informe.py`,
`cableado_c2.py`, `capas_*.py`, `hf4_check.py`, `dialogo_export.py`.

## Lo que se perdio y no estaba en el respaldo

Ninguna de las catorce de la regresion. Si estas, y son suites de paso
—superadas por las que vinieron despues— o herramientas de un rato:

`h2b5_pantalla.py`, `h33_pantalla.py`, `h36_importacion.py`, `h56_pantalla.py`,
`cierre_h7.sh`, `cierre_o1.sh`, `dbg_importar.py`, `dbg_pantallas.py`,
`dbg_previa.py`, `recuperar.py`, `ver_logo.py`, `ver_portada.py`,
`ver_portada2.py`, `probar_orientacion.py`, `prueba_desvio.py`.

Los dos `cierre_*.sh` se reconstruyeron: `cierre_o2c.sh` viene de
`cierre_o2a.sh`, que a su vez venia de `cierre_o1.sh`.
