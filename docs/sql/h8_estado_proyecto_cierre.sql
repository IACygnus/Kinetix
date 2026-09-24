-- ETAPA H8.6 (H-D80, H-D81, H-D87) — el CHECK de `projects.status`, a los cinco.
--
-- Es la SEGUNDA mitad de `h8_estado_proyecto.sql`, y **no se aplica antes que
-- aquel**. Aquel amplio el CHECK a siete valores —los cinco nuevos mas los dos
-- viejos— para que el SQL y el codigo se pudieran desplegar en cualquier orden
-- sin romper nada por el camino. Este quita los dos viejos, ahora que el codigo
-- nuevo ya esta vivo y nadie escribe 'activo' ni 'cerrado'.
--
--
-- EL ORDEN, QUE AQUI SI IMPORTA
-- -----------------------------
--   1. `h8_estado_proyecto.sql`   amplia el CHECK y migra las filas viejas
--   2. el codigo de H8.2 a H8.5   ya desplegado y funcionando
--   3. **este archivo**            estrecha el CHECK a los cinco
--
-- Aplicarlo con codigo viejo todavia corriendo **romperia la creacion de
-- proyectos**: ese codigo escribe 'activo' y el CHECK ya no lo aceptaria. Por
-- eso va el ultimo y no antes.
--
-- En el servidor de produccion **`h8_estado_proyecto.sql` todavia no se ha
-- aplicado** (H8 entero esta sin desplegar). Alli el orden es el de arriba, los
-- tres pasos seguidos, no solo este.
--
--
-- QUE HACE, EXACTAMENTE
-- ---------------------
-- Solo cambia una restriccion. **No toca ni una fila**: si quedara alguna con
-- 'activo' o 'cerrado', el `ALTER` fallaria y la transaccion se desharia entera
-- sin dejar la tabla a medias. Por eso el paso 1 comprueba antes y aborta con un
-- mensaje que se entiende, en vez de dejar que reviente el `ALTER`.
--
-- Es idempotente: volver a ejecutarlo no cambia nada.
--
-- Volver atras, si hiciera falta, es ejecutar otra vez `h8_estado_proyecto.sql`,
-- que vuelve a dejar el CHECK en siete valores.
--
--
-- APLICAR
-- -------
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < docs/sql/h8_estado_proyecto_cierre.sql
--
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_test \
--     < docs/sql/h8_estado_proyecto_cierre.sql
--
-- Antes, la copia de seguridad (regla 32 / R5).

BEGIN;

-- 1. La comprobacion, ANTES de tocar nada. Si queda una fila con un valor
--    viejo, aqui se para y se dice cual: el paso 1 —`h8_estado_proyecto.sql`—
--    no se aplico, o se aplico y despues alguien escribio con codigo viejo.
DO $$
DECLARE
    viejas integer;
BEGIN
    SELECT count(*) INTO viejas FROM projects WHERE status IN ('activo', 'cerrado');
    IF viejas > 0 THEN
        RAISE EXCEPTION
            'Hay % proyecto(s) con status activo/cerrado. Aplica antes '
            'docs/sql/h8_estado_proyecto.sql, que los migra a en_ejecucion y '
            'finalizado. No se ha cambiado nada.', viejas;
    END IF;
END $$;

-- 2. El CHECK, en los cinco de H-D80 y solo esos. Se borra y se vuelve a crear
--    para que el script sea idempotente este como este la restriccion.
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_project_status;

ALTER TABLE projects ADD CONSTRAINT ck_project_status
    CHECK (status IN (
        'pendiente', 'en_ejecucion', 'detenido', 'no_viable', 'finalizado'
    ));

COMMENT ON COLUMN projects.status IS
    'ETAPA H8 H-D80: pendiente | en_ejecucion | detenido | no_viable | finalizado. '
    'Lo decide una persona y es independiente del consumo (§3.1 de la '
    'especificacion v1.5). El antiguo «cerrado» es ahora «finalizado» (H-D81). '
    'Desde H8.6 los valores viejos ya NO se aceptan al escribir.';

COMMIT;

-- 3. La comprobacion de despues: el CHECK con los cinco, y una fila por estado.
SELECT pg_get_constraintdef(oid) AS restriccion
FROM pg_constraint WHERE conname = 'ck_project_status';

SELECT status, count(*) AS proyectos
FROM projects
GROUP BY status
ORDER BY status;
