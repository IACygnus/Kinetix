-- ============================================================================
-- Sprint 3.0 / Fundacion 1 — Analisis multi-fase del HAR
-- Tabla: ai_script_designs
--
-- El proyecto NO usa Alembic (regla #10 de CLAUDE.md): Base.metadata.create_all
-- solo CREA tablas nuevas, nunca agrega columnas a tablas existentes. Estas 3
-- columnas se aplican con ALTER TABLE manual.
--
-- Las tres son NULLABLE: los 9 disenos HAR ya existentes quedan con NULL y el
-- flujo de generacion vigente no se entera. No hay backfill.
--
-- APLICAR:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < backend/migrations/sql/sprint-3.0-fundacion-1-har-analysis.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ADD (idempotente — IF NOT EXISTS)
-- ----------------------------------------------------------------------------
ALTER TABLE ai_script_designs
    ADD COLUMN IF NOT EXISTS har_analysis_classification JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_dependencies   JSONB,
    ADD COLUMN IF NOT EXISTS har_analysis_status         VARCHAR(32);

COMMENT ON COLUMN ai_script_designs.har_analysis_classification IS
    'Sprint 3.0 F1 — Fase 1: {version, source_sha1, total_entries, counts, entries[], phase2_error}';
COMMENT ON COLUMN ai_script_designs.har_analysis_dependencies IS
    'Sprint 3.0 F1 — Fase 2: {version, analyzed_entries, dependencies[{source_idx, target_idx, data_name, locations, extractor_hint, confidence}]}';
COMMENT ON COLUMN ai_script_designs.har_analysis_status IS
    'Sprint 3.0 F1 — completed | skipped | failed (failed retiene Fase 1)';

-- ----------------------------------------------------------------------------
-- ROLLBACK / DROP  (descomentar para revertir por completo)
-- ----------------------------------------------------------------------------
-- ALTER TABLE ai_script_designs
--     DROP COLUMN IF EXISTS har_analysis_classification,
--     DROP COLUMN IF EXISTS har_analysis_dependencies,
--     DROP COLUMN IF EXISTS har_analysis_status;
--
-- Nota: el DROP destruye los analisis persistidos, no solo el schema. Si el
-- objetivo es solo re-correr el analisis, basta con:
--     UPDATE ai_script_designs
--        SET har_analysis_classification = NULL,
--            har_analysis_dependencies   = NULL,
--            har_analysis_status         = NULL
--      WHERE reference_file_type = 'har';
-- ...o llamar al endpoint con ?force=true.
