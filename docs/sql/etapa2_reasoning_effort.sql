-- ETAPA 2.2 (D13b) — reasoning_effort configurable en la config de IA.
--
-- El proyecto no usa Alembic (regla 10): `Base.metadata.create_all` solo CREA
-- tablas nuevas, nunca anade columnas a una existente. Por eso esta columna se
-- anade con un script idempotente, que puede ejecutarse las veces que haga falta.
--
-- Aplicar en local y en el servidor ANTES de desplegar el codigo de la etapa 2:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < docs/sql/etapa2_reasoning_effort.sql
--
-- NULL significa "low" (D13b): no hace falta rellenar las filas existentes.

ALTER TABLE ai_config
    ADD COLUMN IF NOT EXISTS reasoning_effort VARCHAR(20);

COMMENT ON COLUMN ai_config.reasoning_effort IS
    'ETAPA 2 D13: low | medium | high. NULL = low. Solo se envia a modelos OpenAI que lo soportan.';
