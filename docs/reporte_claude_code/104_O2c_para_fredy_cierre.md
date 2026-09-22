ce837e9 · 2026-09-22

# O2c para Fredy — un guion: dar de alta un servidor y probarlo

---

## Antes de nada: las suites que se perdieron, y aparecieron

Te pedí un `docker compose up -d --build backend` y **eso borró `/tmp/e2e`**,
donde vivían todas las suites desde H1. El comando hacía falta; el aviso que
tenía que acompañarlo, no lo di.

**Aparecieron en `C:\proyectos\Kinetix_pruebas\e2e\`** —el respaldo del que ya
se repuso en H3— y están **las 12 de la regresión, íntegras**. No hubo que
reescribir ninguna.

Ahora viven en el repositorio, en `backend/pruebas_e2e/`, que se monta dentro
del contenedor. **Un `--build` ya no puede llevárselas.** Es la regla 36 nueva.

Lo que no estaba en el respaldo y no vuelve: cuatro suites de paso del módulo de
horas, superadas por `h7_pantallas_horas.py`, que cubre lo mismo en su forma
final; y nueve herramientas de un rato que no protegían nada.

---

## El guion

### Paso 1 — el menú

Entra y mira la barra de la izquierda. Hay una sección nueva,
**«Observabilidad»**, al mismo nivel que Análisis y Diseño. Dentro:

- **Monitoreo en vivo** — la que ya conocías, que estaba en Análisis.
- **Servidores** — la nueva.

**«Metricas Monitoreo» sigue en Análisis**, y a propósito: son las capturas que
la IA analiza para el informe, no monitoreo en vivo. Dicho eso, **ese nombre se
va a prestar a confusión** ahora que hay una sección que sí es monitoreo. Lo
dejo anotado para que decidas si lo renombramos.

Si tenías guardado el enlace viejo `/monitoring/vivo`, **sigue funcionando**:
te lleva a la sección nueva.

### Paso 2 — dar de alta un servidor

**Observabilidad → Servidores → Añadir servidor.**

Para probarlo con el laboratorio:

| Campo | Linux | PostgreSQL |
|---|---|---|
| Cliente | el que quieras | el mismo |
| Nombre | `lab_servidor` | `lab_db` |
| Tipo | Linux | PostgreSQL |
| Dirección | `lab_servidor` | `lab_db` |
| Puerto | 22 *(se propone solo)* | 5432 *(se propone solo)* |
| Usuario | `kinetix_lector` | `kinetix_lector` |
| Credencial | el contenido de `lab/llaves/kinetix_lector` | la de `lab/lab.env`, `LAB_PG_LECTOR_PASSWORD` |
| Notas | — | `tienda` |

**La credencial se escribe una vez y no vuelve a salir.** Si abres a editar, el
campo aparece en blanco: no es un fallo, es que no hay forma de leerla. En
blanco significa «déjala como está».

### Paso 3 — probar la conexión

Pulsa **«Probar conexión»**. No dice «ok» o «error»: dice qué se puede leer.

En el Linux:

```
Se llega al servidor (487 ms)
  ✓ el puerto 22 responde: SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.17
  ✓ la credencial sirve y /proc se lee: sesion abierta como «kinetix_lector»;
    el servidor dice tener 8 nucleos
  ✓ llegan metricas de este servidor: la ultima, hace 0 segundos
```

En la base:

```
Se conecta a la base y se leen sus estadisticas (26 ms)
  ✓ pg_stat_database (conexiones y transacciones): 5 filas visibles
  ✓ pg_stat_statements (consultas lentas): 18 filas visibles
```

**Y cuando falla, dice por qué de verdad.** Prueba a cambiar el puerto a 2222 y
verás `ConnectionRefusedError: [Errno 111] Connection refused`. Si la llave
estuviera mal: `Permission denied (publickey)`. Nada de «no se pudo conectar».

### Paso 4 — la configuración

Pulsa **«Configuración»**. Según el modo del servidor:

- **Sin agente** — los parámetros del recolector, cada uno con su explicación y
  su botón de copiar.
- **Con agente** — la orden de instalación ya rellena, con `--token-fichero`
  para que el token no quede en la línea de órdenes.

Arriba, en ámbar: **Kinetix genera esto, no lo ejecuta.** Quien lo aplica es una
persona con acceso al servidor. Kinetix no guarda credenciales de administrador
de nadie.

---

## Lo que quiero que mires con ojo crítico

1. **El nombre «Metricas Monitoreo».** Ahora que hay una sección Observabilidad,
   ¿confunde? Tú sabes cómo lo busca la gente.
2. **El resultado de la prueba de conexión.** ¿Te dice lo que necesitas cuando
   algo falla, o falta algo?
3. **El formulario de alta.** ¿Sobra o falta algún campo para un servidor de un
   cliente de verdad?

---

## Lo que NO está hecho

- **Windows no se puede probar** desde la pantalla. El tipo existe, pero la
  prueba responde que haría falta WinRM. Está dicho con esas palabras.
- **El punto de entrada HTTPS para el modo con agente sigue sin existir.**
  Corregí el documento del cliente, que decía que el agente sale al 8086: eso
  está cerrado a propósito y no se va a abrir. Hasta que exista ese componente,
  el modo con agente solo sirve cuando el servidor y Kinetix comparten red.
- **Nada de esto ha visto un servidor de verdad**, sigue siendo el laboratorio.

---

## Dos comandos que ya aplicaste, por si hay que repetirlos

```
docker compose up -d --build backend
docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db < docs/sql/o2c_influxdb_read_token.sql
```

Y si alguna vez hay que volver a reconstruir el backend, **antes**:

```
docker exec jmeter_backend sh -c 'ls /tmp/e2e' | sort > /tmp/alla.txt
ls backend/pruebas_e2e | sort > /tmp/aqui.txt
diff /tmp/aqui.txt /tmp/alla.txt
```

Lo que aparezca solo del lado del contenedor se copia al repositorio primero.

---

## Estado

**Etapa O2c implementada, pendiente de validación de Fredy.**

La regresión quedó en **578 comprobaciones, 15 suites, cero fallos**, y la
huella de tu base de datos es **idéntica antes y después**.

Eso dice que no se rompió nada. **No da por validadas H5, H6, H7, O1, O2a ni
O2b**: esas siguen esperándote a ti, que eres el único criterio.
