Commit base `22b027f` (sin commit propio todavía) · 29 de septiembre de 2026

# O2e.2a — El token y la validación de la ingesta

Primera mitad de O2e.2. Contiene el modelo, las reglas puras y sus pruebas. **No hay ruta, `main.py` no
cambia y la tabla todavía no se crea**: el import del modelo llega en O2e.2b junto con la exención CSRF,
para que `ingest_tokens` no aparezca en la base de Fredy antes de que algo la use.

Decisiones aprobadas por Fredy tras el reporte 126: vía B (O-D48); O-D49 a O-D53; opción **a** para el
token de escritura de `infra` (columna y SQL, en O2e.2b); **300 por minuto y token, aproximado**; 400 con el
recuento por cliente; tope aplicado **después** de descomprimir; **413** para un lote grande.

## 1. Qué hay

| Archivo | Líneas | Qué |
|---|---|---|
| `backend/app/db/models/ingest_token.py` | 59 | Tabla `ingest_tokens`: `client_id` (CASCADE), `huella` SHA-256 **única**, `prefijo` visible, `creado_en/por`, `ultimo_uso`, `revocado_en/por`. **No hay columna para el token** |
| `backend/app/services/observabilidad/ingesta.py` | 277 | Token, descompresión con tope, lectura de la etiqueta `cliente`, revisión del lote con su motivo y limitador |
| `backend/pruebas_e2e/o2e2a_ingesta.py` | 201 | 50 comprobaciones en proceso. No escribe en ninguna parte |
| `frontend/.../IntegratedReportPage.tsx:619`, `MonitoringPage.tsx:168` | 1 + 1 | «Capturas de infraestructura» (O-D42), con la aplicación cerrada |

**Estimación superada.** `ingesta.py` iba a tener unas 120 líneas y tiene 277. Más de la mitad son
docstrings y comentarios; entre ellos, los que explican el tope y el 413, que Fredy pidió que quedaran
escritos. Ningún archivo protegido.

## 2. Las decisiones que el código deja explicadas

- **Tope después de descomprimir.** Telegraf manda gzip por defecto. Descomprimir entero y medir después
  ya es el daño, así que se descomprime con `max_length = tope + 1`. Prueba: una bomba de **20.406 bytes**
  comprimidos, que serían 20 MB, sale como 413 sin llegar a expandirse.
- **413, no 400.** Ante un 413, Telegraf parte el lote en dos y reenvía cada mitad. Ante cualquier otro
  4xx que no sea 429, lo tira.
- **La comparación del cliente es exacta** con el nombre del cliente en Kinetix, que es lo que la orden
  de instalación pone en `--cliente`. Si se renombra el cliente, sus agentes empiezan a ser rechazados.
  Es lo correcto: con el nombre nuevo nadie encontraría sus métricas.
- **Una barra al final de una etiqueta** (`device=C:\,cliente=acme`) se come la coma, igual que en la
  lección de O2a. La línea queda sin cliente y el lote se rechaza. Así debe ser, porque esa línea ya
  estaba rota para InfluxDB.

## 3. El ritmo: una corrección de mi propia cifra

Cada agente hace 12 peticiones por minuto, así que **300 por minuto son exactamente 25 agentes, en el
límite**. La simulación con 25 agentes durante 10 minutos dio **7 respuestas 429**. Con 20 no dio
ninguna y con 30 frena, como debe. **El techo cómodo con un solo token son unos 20 servidores.** Un
cliente con más necesita un segundo token. El comentario del código lo dice así. Mi primera versión decía
25, y era falsa.

Es un límite **aproximado**: vive en memoria y en producción hay dos workers, así que el tope real puede
llegar al doble. Esto tiene que aparecer igual en `requisitos-con-agente.md` v1.2 (O2e.5).

## 4. El motivo del 400, tal como sale

> Lote rechazado entero: 5 de 6 lineas no son del cliente «acme» (3 lineas con cliente=«otro»; 2 lineas
> sin la etiqueta cliente). No se ha escrito nada.

## 5. Cómo se corre

```
docker exec jmeter_backend python3 /app/pruebas_e2e/o2e2a_ingesta.py
```

Resultado: **TODO BIEN**, 50 de 50. No toca ninguna base, ni la de pruebas, porque no hay nada que
persistir hasta O2e.2b.

## 6. Lo que queda para O2e.2b

La ruta `POST /api/v1/ingesta/api/v2/write`, que exige `bucket=infra` y reenvía a InfluxDB. La línea de
log por lote con cliente, puntos, resultado y motivo, sin el token. Una línea de `main.py` para la
exención CSRF y otra para el import del modelo. Además, la columna del token de escritura de `infra`, que
necesita `docs/sql/o2e_infra_write_token.sql` y el `PUT` de admin, y los endpoints de alta, lista y
revocación. Las pruebas de la ruta contra el backend de pruebas (8002).
