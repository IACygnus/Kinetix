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

```sh
# 1. Dejar una copia de trabajo en /tmp/e2e (las suites escriben ahi)
docker exec jmeter_backend sh /app/pruebas_e2e/sincronizar.sh

# 2. La regresion completa, en serie, contra la base de PRUEBAS (regla 34)
docker exec jmeter_backend sh /app/pruebas_e2e/cierre_o2c.sh
```

El corredor renueva la sesion el mismo, toma la huella de la base de Fredy antes
y despues, y la compara al final.

## Lo que hace falta en el contenedor, y no esta en `requirements.txt`

Estas dos cosas se instalan a mano y **se pierden en cada reconstruccion del
backend**. No estan en `requirements.txt` a proposito: son de prueba, no del
producto, y no tienen por que viajar a produccion.

```sh
docker exec jmeter_backend pip install playwright
docker exec jmeter_backend playwright install --with-deps chromium
```

Si una suite de navegador falla con `ModuleNotFoundError: No module named
'playwright'`, es esto.

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
