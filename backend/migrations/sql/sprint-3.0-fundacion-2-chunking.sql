-- ============================================================================
-- Sprint 3.0 / Fundacion 2 — Generacion de JMX por chunks
-- Tabla: ai_script_designs
--
-- Sin Alembic (regla #10): Base.metadata.create_all solo CREA tablas nuevas.
-- Estas 4 columnas se aplican con ALTER TABLE manual.
--
-- Las cuatro son NULLABLE: un diseno generado por el flujo clasico de 1 sola
-- llamada las deja en NULL y nada previo se entera. No hay backfill.
--
-- APLICAR:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < backend/migrations/sql/sprint-3.0-fundacion-2-chunking.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ADD (idempotente — IF NOT EXISTS)
-- ----------------------------------------------------------------------------
ALTER TABLE ai_script_designs
    ADD COLUMN IF NOT EXISTS generation_mode         VARCHAR(32),
    ADD COLUMN IF NOT EXISTS chunks_plan             JSONB,
    ADD COLUMN IF NOT EXISTS chunks_completed_count  INTEGER,
    ADD COLUMN IF NOT EXISTS generation_status       VARCHAR(32);

COMMENT ON COLUMN ai_script_designs.generation_mode IS
    'Sprint 3.0 F2 — single | chunked. NULL = generado por el flujo clasico.';
COMMENT ON COLUMN ai_script_designs.chunks_plan IS
    'Sprint 3.0 F2 — [{chunk_id, name, entry_idxs[], categories[], status, is_skeleton, failure_reason}]';
COMMENT ON COLUMN ai_script_designs.chunks_completed_count IS
    'Sprint 3.0 F2 — chunks con status=completed; se recalcula desde chunks_plan en cada retry.';
COMMENT ON COLUMN ai_script_designs.generation_status IS
    'Sprint 3.0 F2 — completed | partial | failed';

-- ----------------------------------------------------------------------------
-- ROLLBACK / DROP  (descomentar para revertir por completo)
-- ----------------------------------------------------------------------------
-- ALTER TABLE ai_script_designs
--     DROP COLUMN IF EXISTS generation_mode,
--     DROP COLUMN IF EXISTS chunks_plan,
--     DROP COLUMN IF EXISTS chunks_completed_count,
--     DROP COLUMN IF EXISTS generation_status;
--
-- Nota: el DROP borra el plan de chunks, NO el JMX generado (current_jmx es
-- una columna aparte y no se toca). Para re-planificar sin perder el schema:
--     UPDATE ai_script_designs
--        SET generation_mode = NULL, chunks_plan = NULL,
--            chunks_completed_count = NULL, generation_status = NULL
--      WHERE id = '<design_id>';
