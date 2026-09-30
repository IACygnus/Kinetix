Commit base `4832052` · 30 de septiembre de 2026

# 131 — El token de InfluxDB en claro de `cierre_o2a.sh` y `cierre_o2d.sh`

El hallazgo del reporte 130 §6, cerrado. **El token viejo está muerto** (InfluxDB contesta 401) y ya no
aparece en el árbol de trabajo ni en los `/tmp` de los contenedores. **El historial no se reescribió**
(Fredy): el valor sigue en los commits `ce837e9`, `f5bf053` y `679f186`, pero ya no sirve para nada.

## 1. Qué token era (comprobado por huella, sin imprimir valores)

| Dónde | sha256 (12) |
|---|---|
| `backend/pruebas_e2e/cierre_o2a.sh:11` y `cierre_o2d.sh:11` | `c766c3875da0` |
| `lab/lab.env` → `KX_TOKEN_ESCRITURA` | `c766c3875da0` |
| `monitoring_config.influxdb_token_encrypted`, base de Fredy (fila `88d5bc44`) | `c766c3875da0` |
| Lo mismo, base de pruebas (fila `f252ebe2`) | `c766c3875da0` |
| InfluxDB: autorización **`kinetix-jmeter-escritura`**, id `115d29f5e0945000` | `c766c3875da0` |

Su alcance era **solo escribir en el cubo `jmeter`**: no leía nada y no tocaba `infra`. Es el token de
O-D2, el que se le da a JMeter.

**Un fallo mío:** al buscar quién leía la variable, un `grep` sacó en pantalla el principio de las dos
líneas `export` con el valor. El valor ya era público, porque estaba en GitHub, y ahora está muerto.
Aun así debía no haber salido. Desde ahí todo se buscó con `grep -l` o contando.

## 2. Los consumidores, y qué se hizo con cada uno

| Consumidor | Qué se hizo |
|---|---|
| `lab/lab.env` → `KX_TOKEN_ESCRITURA` | El token nuevo, escrito por tubería. **Sigue sin versionarse**: `lab/.gitignore:4` |
| `monitoring_config` de la base de Fredy | `PUT /monitoring/config` con solo `influxdb_token`, tras **un** login de desarrollo en el 8001 (200). **Sin SQL a mano** |
| `monitoring_config` de la base de pruebas | El mismo `PUT`, en el 8002 |
| `cierre_o2a.sh` y `cierre_o2d.sh` | Ya no llevan el token (§3) |
| `regresion_h8.sh`, `lab_prueba_correlacion.sh`, `lab_comparar_modos.sh`, `cierre_h8.sh`, `o16_pantalla.py`, `o2a3_config.py` | Nada: lo toman de `lab/lab.env` o del entorno. **0 coincidencias del valor viejo** en cada uno |
| `lab_preparar.sh` | Nada: busca la autorización **por su descripción**, y la nueva lleva la misma |
| Grafana, `lab_colector`, el agente y el motor propio | **No lo usaban.** Grafana lee con el token maestro, y los otros escriben en `infra` con otro token |

Tras el `PUT`, `/monitoring/jmeter-config` entrega en las dos bases el token nuevo, comprobado
comparando huellas. Eso es lo que copia la pantalla de Monitoreo en vivo y lo que llevan los `.jmx` de
las sesiones.

**Los `.jmx` ya descargados llevan el token viejo y darán 401.** Los del equipo de Fredy no se tocaron:
él los vuelve a descargar.

## 3. Los dos guiones

El valor literal se sustituyó por esta comprobación:

```sh
if [ -z "${KX_TOKEN_ESCRITURA:-}" ]; then
  echo "PARADA: falta KX_TOKEN_ESCRITURA (el token de escritura del cubo jmeter)." >&2
  echo "Esta en lab/lab.env, que no se versiona. Lanza el guion asi:" >&2
  echo "  docker exec --env-file lab/lab.env jmeter_backend sh /app/pruebas_e2e/cierre_o2d.sh" >&2
  exit 1
fi
export KX_TOKEN_ESCRITURA
```

**Un matiz frente a lo pedido:** estos guiones corren **dentro** de `jmeter_backend`, y ahí `lab/` no
existe, porque solo está montado `./backend`. No pueden abrir `lab/lab.env` por sí mismos. Hacen lo
mismo que `regresion_h8.sh`: `lab.env` se lee en el anfitrión y se pasa con `--env-file`, y el guion
para si no le llega.

**Comprobado:**
- los dos paran con ese mensaje y código 1 si no les llega el token, y no llegan a correr ninguna suite;
- `--env-file lab/lab.env` entrega en el contenedor el token nuevo (sha `5ced8a1fda99`).

No se corrió la regresión completa de ninguno de los dos.

## 4. La rotación

1. **Copia previa (regla 32):** `C:\proyectos\Kinetix_pruebas\backup_20260930_token.sql`, 7 MB y 33
   tablas. Además se copió `lab/lab.env` antes de tocarlo, para poder dar marcha atrás. **Esa copia se
   borró al terminar**, porque lleva otros secretos que siguen vigentes.
2. **Autorización nueva:** `kinetix-jmeter-escritura`, id `1167ec6a2ee0d000`, sha `5ced8a1fda99`, 88
   caracteres. **El mismo permiso que la vieja:** `write:orgs/fea51f27d2fe936f/buckets/b944c355e16718f0`
   (el cubo `jmeter`). Su token fue de `influx auth create --json` a `lab/lab.env` y a los dos `PUT`
   solo por variables y tuberías, sin mostrarse.
3. **Comprobaciones:**

| Qué | Resultado |
|---|---|
| Escritura vacía en `jmeter` con el token nuevo | **204** |
| Escritura vacía con el viejo, antes de borrarlo | 204, como se esperaba |
| `influx auth delete --id 115d29f5e0945000` | borrada |
| Escritura vacía con el viejo, después | **401** |
| Escritura vacía con el nuevo, después | **204** |
| Base de Fredy y base de pruebas, `influxdb_token_encrypted` | las dos `5ced8a1fda99` |

**Un detalle de método:** la primera escritura de prueba puso el token en la línea de órdenes de `curl`
**dentro del contenedor** (`-H "Authorization: Token …"`), visible con `ps` mientras duraba. Las
siguientes usaron `-H @fichero`. No salió de `jmeter_backend`.

## 5. Los restos (borrados por nombre, después del 401)

En `jmeter_backend`, exactamente estos y nada más:
- `/tmp/zztest_o2d5.jmx`, `/tmp/o2a3_config.json` y `/tmp/jmeter.log`;
- `/tmp/descargas_o2d/con_listener.jmx`, y después `rmdir` del directorio, que quedó vacío;
- `/tmp/e2e/cierre_o2a.sh`, `/tmp/e2e/cierre_o2c.sh` y `/tmp/e2e/cierre_o2d.sh`.

`backend/jmeter.log` (no versionado) vaciado: tenía 11.574 bytes y ahora 0.

**La comprobación final**, contando coincidencias del valor viejo sin imprimirlas:

| Dónde | Coincidencias |
|---|---|
| Árbol de trabajo (versionado o no, sin `.git` ni `node_modules`) | **0 archivos** |
| `/tmp` de `jmeter_backend`, `lab_servidor`, `lab_db`, `jmeter_grafana`, `jmeter_influxdb`, `jmeter_postgres` y `jmeter_frontend` | **0 archivos** en cada uno |
| Los seis que lo toman de `lab.env` | **0** en cada uno |

## 6. `kinetix-lectura`, sin tocar (para O2e.5)

`influx auth list` dice hoy:

```
115edc944ee6b000  kinetix-lectura  active
  read:orgs/fea51f27d2fe936f/buckets/339a1d628e46bae9   (infra)
  read:orgs/fea51f27d2fe936f/buckets/b944c355e16718f0   (jmeter)
```

**Lee también el cubo `jmeter`**, y CLAUDE.md §16 dice que «no ve el cubo `jmeter` (404)». Se corrige
en O2e.5. No se sabe si la documentación estuvo mal desde O2c o si el token cambió después.

## 7. Otros secretos en claro en el repositorio (solo la lista, nada tocado)

Búsqueda en los archivos **versionados** (`git grep`, sin `*.bak*` ni `package-lock.json`). Solo
archivo y línea.

### 7.1 Secretos que funcionan hoy en desarrollo

**El token maestro de InfluxDB, `jmeter-token-2024-super-secret`.** Es la autorización «admin's Token»,
con **todos los permisos** (44). Es el valor por defecto del compose. Aparece en:
- `docker-compose.yml:107` y `:145`;
- `CLAUDE.md:1181`;
- `GRAFANA_SETUP.md:29`, `:117`, `:192`, `:219`, `:450`, `:456`, `:462`, `:474`, `:517` y `:551`;
- `backend/app/services/engine/refine_operations_applier.py:820` y `:840` (protegido);
- `frontend/src/pages/AIScriptEditor.tsx:644`;
- `backend/pruebas_e2e/corrida_para_tablero.py:44`, `o16_pantalla.py:38`, `o2a3_correlacion.py:27` y
  `probar_tablero.py:16`;
- `scripts/lab_comparar_modos.sh:23`, `lab_corte_de_red.sh:26`, `lab_ingesta_o2e3.sh:38` y
  `lab_preparar.sh:24`;
- `docs/observabilidad/datos-de-prueba.md:102` y `manual-de-pruebas.md:66`;
- `docs/reporte_claude_code/96_O1_1_diagnostico_monitoreo.md:59` y `:100`, `97_O1_cierre.md:47` y
  `:77`, y `106_O2d_para_fredy_cierre.md:33`;
- `docs/reports/repo/sprint-2.4-hf7b-listeners.md:53`.

**Lo más serio de la lista son las dos apariciones en código del producto:**
`refine_operations_applier.py` y `AIScriptEditor.tsx`. Si ese valor acaba dentro de los `.jmx` que
genera el diseñador, un script entregado llevaría el token **con todos los permisos**. No lo he
comprobado.

**La contraseña de Postgres de desarrollo, `jmeter_secure_2024`:**
- `docker-compose.yml:11` y `:36`;
- `backend/app/core/config.py:16`;
- `CLAUDE.md:1157` y `:1159`;
- `DOCUMENTACION_TECNICA.md:566` y `:571`;
- `scripts/preparar_base_de_pruebas.sh:23`;
- `docs/reporte_claude_code/96_O1_1_diagnostico_monitoreo.md:445`;
- y **33 suites** de `backend/pruebas_e2e/`: `analista_de_pruebas.py:74`,
  `carga_actividades_nuevas.py:63`, `carga_borrado_proyecto.py:53`, `cierre_h8.sh:45`,
  `cierre_o2a.sh:25`, `cierre_o2d.sh:25`, `f2_pantallas.py:44`, `h13_backend.sh:161`,
  `h15_pantallas.py:73`, `h22_backend.py:40` y `:170`, `h2b2_backend.py:40`, `h2b3_pantalla.py:59`,
  `h32_consulta.py:41`, `h52_informe.py:39`, `h53_h54_documento.py:43`, `h6_ajustes.py:41`,
  `h7_pantallas_horas.py:55`, `h82_estados.py:56`, `h83_pantallas.py:59`, `h83b_datos_informe.py:41`,
  `h84_mapa.py:55`, `h85_borrado.py:66`, `h85_pantalla.py:56`, `h85b_pantalla.py:56`,
  `h85b_proyectos.py:51` y `:273`, `o2e2b_ingesta.py:102`, `r1_datos.py:29`, `r1_historial.py:35`,
  `r1_integrado.py:45`, `r1_punta_a_punta.py:46` y `:204`, `r1_seleccion.py:42` y `:187`,
  `r1_sesion_test.py:7` y `verificar_etapa2.py:61`.

**La contraseña del admin de la aplicación, `sqa2024`:**
- `backend/app/core/config.py:24` y `docker-compose.yml:43`;
- `CLAUDE.md:1169` y `:1461`, y `README.md:108`;
- `backend/pruebas_e2e/cierre_h8.sh:42`, `cierre_o2a.sh:9` y `cierre_o2d.sh:9`;
- `scripts/preparar_base_de_pruebas.sh:85`;
- `docs/reporte_claude_code/19_ETAPA2_checkpoint_2_6.md:139`;
- `docs/reports/repo/sprint-2.4e-cierre.md:119`, `reporte-para-fredy-fundacion-2.md:259` y
  `reporte-para-fredy-hf21.md:106`.

**Hoy es también la contraseña del admin en la base de desarrollo de Fredy:** el login de §2 entró con
ella.

**La contraseña del admin de InfluxDB, `admin123`:** `docker-compose.yml:103` y `CLAUDE.md:1178`.

**La contraseña del admin de Grafana:** `docker-compose.yml:131` la toma por defecto como `admin`
(`${GRAFANA_ADMIN_PASSWORD:-admin}`).

**Las de los analistas de prueba** (`zztest2026` y `ZZtest-h8-2026`), usuarios de la base de pruebas:
- `backend/pruebas_e2e/analista_de_pruebas.py:30`, `cierre_h8.sh:43`, `cierre_o2a.sh:10`,
  `cierre_o2d.sh:10` y `h82_estados.py:33`;
- `scripts/preparar_base_de_pruebas.sh:109`.

### 7.2 Encontrados por la búsqueda, pero comprobado que NO son secretos

| Dónde | Por qué no |
|---|---|
| `backend/pruebas_e2e/f1_respaldo.py:174` y `:176`, una clave `sk-proj-…` | Es **inventada**: 30 caracteres, la suite la usa para provocar el rechazo de OpenAI, y es distinta de la clave real de `ai_config` (164 caracteres), comparada descifrando en proceso |
| `docs/observabilidad/datos-de-prueba.md:48` y `frontend/src/pages/ServidoresPage.tsx:474` | Es el texto `-----BEGIN OPENSSH PRIVATE KEY-----` como indicación y como marcador de campo, sin llave |
| `.env.example` | Todos los valores son `<your…>` |
| `DOCUMENTACION_TECNICA.md:565-567` (`GEMINI_API_KEY`, `SECRET_KEY`) | Son de ejemplo: `AIza…` de 9 caracteres y `your…` |

### 7.3 Lo que no está en el repositorio

- La clave real de OpenAI: solo existe cifrada en `ai_config`.
- `lab/lab.env` (`lab/.gitignore:4`) y `lab/llaves/` (`lab/.gitignore:3`; 0 archivos versionados).
- No hay ningún `.env` versionado. No aparece ninguna cadena con forma de token de InfluxDB (80 o más
  caracteres acabados en `==`), ni ninguna clave `AIza` real.

## 8. Archivos del commit

| Archivo | Cambio |
|---|---|
| `backend/pruebas_e2e/cierre_o2a.sh` | −1 +12: el `export` literal sustituido por la comprobación |
| `backend/pruebas_e2e/cierre_o2d.sh` | lo mismo |
| `docs/reporte_claude_code/131_token_en_claro.md` | este reporte |

Los archivos de O2e.4a (`TokensIngesta.tsx`, `api.ts`, `ServidoresPage.tsx`, `o2e4a_pantalla.py` y el
reporte 130) **se quedan fuera, sin commit**, a la espera de la decisión sobre la suite de O2c.
