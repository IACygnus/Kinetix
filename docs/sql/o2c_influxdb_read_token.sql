-- ETAPA O2c (O-D33) — token de SOLO LECTURA del cubo `infra`.
--
-- El proyecto no usa Alembic (regla 10): `Base.metadata.create_all` solo CREA
-- tablas nuevas, nunca anade columnas a una existente. Por eso esta columna se
-- anade con un script idempotente, que puede ejecutarse las veces que haga
-- falta sin romper nada.
--
-- POR QUE HACE FALTA
-- ------------------
-- El token que ya hay en `monitoring_config.influxdb_token_encrypted` es de
-- SOLO ESCRITURA y solo sobre el cubo `jmeter` (O-D2, comprobado en el reporte
-- 97 §3.1: leer con el devuelve 404, ni siquiera ve el cubo). Eso es una
-- virtud y no se toca.
--
-- Pero significa que Kinetix no podia comprobar por si mismo si estaban
-- llegando metricas de un servidor: la prueba de conexion solo sabia decir
-- «el puerto responde». Con un token de LECTURA acotado al cubo `infra`, la
-- prueba dice ademas cuando llego la ultima metrica de ese servidor (O-D34).
--
-- Los dos tokens conviven y son distintos a proposito:
--   influxdb_token_encrypted        escribe en `jmeter`.  Lo copia JMeter.
--   influxdb_read_token_encrypted   lee `infra`.          No sale nunca a la pantalla.
--
-- APLICAR
-- -------
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < docs/sql/o2c_influxdb_read_token.sql
--
-- Y en la base de pruebas, si se usa:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_test \
--     < docs/sql/o2c_influxdb_read_token.sql
--
-- NULL significa «no hay token de lectura»: la prueba de conexion sigue
-- funcionando y dice que no puede comprobar las metricas. No rompe nada.

ALTER TABLE monitoring_config
    ADD COLUMN IF NOT EXISTS influxdb_read_token_encrypted TEXT;

COMMENT ON COLUMN monitoring_config.influxdb_read_token_encrypted IS
    'ETAPA O2c O-D33: token de SOLO LECTURA del cubo infra, cifrado con Fernet. '
    'Distinto del de escritura. NULL = no configurado; la prueba de conexion lo dice.';
