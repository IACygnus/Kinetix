-- ETAPA O2e (O-D48, O-D49) — token de ESCRITURA del cubo `infra`.
--
-- El proyecto no usa Alembic (regla 10): `Base.metadata.create_all` solo CREA
-- tablas nuevas, nunca anade columnas a una existente. Por eso esta columna se
-- anade con un script idempotente, que puede ejecutarse las veces que haga
-- falta sin romper nada.
--
-- POR QUE HACE FALTA
-- ------------------
-- Desde O2e, el agente de un cliente no escribe en InfluxDB: escribe en
-- Kinetix (`POST /api/v1/ingesta/api/v2/write`) con un token de ingesta de su
-- cliente, y es Kinetix quien escribe en `infra`. Para eso necesita el token de
-- escritura de `infra` de O-D15, que hasta ahora solo existia en lab/lab.env.
--
-- Los tres tokens conviven y son distintos a proposito:
--   influxdb_token_encrypted              escribe en `jmeter`.  Lo copia JMeter.
--   influxdb_read_token_encrypted         lee `infra`.          O2c.
--   influxdb_infra_write_token_encrypted  escribe en `infra`.   O2e. No sale nunca del servidor.
--
-- APLICAR
-- -------
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < docs/sql/o2e_infra_write_token.sql
--
-- Y en la base de pruebas:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_test \
--     < docs/sql/o2e_infra_write_token.sql
--
-- Despues, cargar el token desde `PUT /api/v1/ingesta/token-escritura` (admin).
--
-- NULL significa «no hay token»: la ingesta contesta 503 y el agente guarda
-- sus lotes y reintenta. No se pierde nada y no rompe ninguna otra pantalla.

ALTER TABLE monitoring_config
    ADD COLUMN IF NOT EXISTS influxdb_infra_write_token_encrypted TEXT;

COMMENT ON COLUMN monitoring_config.influxdb_infra_write_token_encrypted IS
    'ETAPA O2e: token de ESCRITURA del cubo infra, cifrado con Fernet. Con el '
    'escribe Kinetix lo que recibe de los agentes. NULL = la ingesta responde 503.';
