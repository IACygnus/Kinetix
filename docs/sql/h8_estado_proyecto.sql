-- ETAPA H8 (H-D80, H-D81, H-D87) — el estado del proyecto pasa a cinco valores.
--
-- El proyecto no usa Alembic (regla 10): `Base.metadata.create_all` solo CREA
-- tablas nuevas, nunca toca una columna ni una restriccion de una tabla que ya
-- existe. Por eso este script, que es idempotente y se puede ejecutar las veces
-- que haga falta sin romper nada.
--
--
-- QUE CAMBIA
-- ----------
-- `projects.status` tenia dos valores, 'activo' y 'cerrado'. Pasa a tener los
-- cinco de H-D80:
--
--     pendiente      aprobado pero aun no empezado
--     en_ejecucion   en marcha  (el valor por defecto)
--     detenido       parado por ahora; se espera retomarlo
--     no_viable      no se va a hacer
--     finalizado     terminado   (es el antiguo 'cerrado')
--
-- **No se anade una columna nueva.** H-D81 lo pide asi a proposito: dos columnas
-- que significan casi lo mismo acaban con alguien leyendo la equivocada. El
-- campo que ya existe se amplia, y 'cerrado' se convierte en 'finalizado'.
--
-- La tabla `project_status_changes` —el historial de H-D83— la crea
-- `create_all` al arrancar, por ser una tabla nueva. **Aqui no hay nada que
-- hacer con ella.**
--
--
-- POR QUE EL CHECK ACEPTA SIETE VALORES Y NO CINCO
-- -----------------------------------------------
-- Porque este script y el codigo de H8.2 se despliegan por separado, y el orden
-- no puede importar:
--
--   - si se aplica el SQL y todavia corre el codigo viejo, ese codigo escribe
--     'activo' al crear un proyecto. Con un CHECK de cinco valores, crear un
--     proyecto daria un error de base de datos.
--   - si se despliega el codigo nuevo y todavia no se aplico el SQL, el codigo
--     escribe 'en_ejecucion' y falla igual.
--
-- Aceptando los siete, las dos mitades funcionan durante el intervalo, se
-- aplique lo que se aplique primero. **En H8.6, con el codigo nuevo ya vivo, el
-- CHECK se estrecha a los cinco** con el script `h8_estado_proyecto_cierre.sql`.
--
-- Leer nunca falla, ni antes ni despues: `status` ya estaba declarada en el
-- modelo. Por eso aqui no aplica el truco de O-D33 —no declarar la columna en
-- el modelo hasta aplicar el SQL—: esa columna no es nueva.
--
--
-- APLICAR
-- -------
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_db \
--     < docs/sql/h8_estado_proyecto.sql
--
-- Y en la base de pruebas (regla 34), que tambien la tiene:
--   docker exec -i jmeter_postgres psql -U jmeter_user -d jmeter_analyzer_test \
--     < docs/sql/h8_estado_proyecto.sql
--
-- Antes de aplicarlo, la copia de seguridad (regla 32 / R5).
--
-- Al terminar imprime cuantos proyectos hay en cada estado: eso es la
-- comprobacion, no la suposicion.

BEGIN;

-- 1. El CHECK, ampliado a los siete valores del intervalo.
--    Se borra y se vuelve a crear: asi el script es idempotente de verdad,
--    tanto si la restriccion esta como si ya se habia cambiado antes.
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_project_status;

ALTER TABLE projects ADD CONSTRAINT ck_project_status
    CHECK (status IN (
        -- Los cinco de H-D80.
        'pendiente', 'en_ejecucion', 'detenido', 'no_viable', 'finalizado',
        -- Los dos viejos, solo mientras dure el despliegue. H8.6 los quita.
        'activo', 'cerrado'
    ));

-- 2. La migracion de H-D81. Solo toca las filas que siguen en los valores
--    viejos: volver a ejecutar el script no mueve nada.
UPDATE projects SET status = 'en_ejecucion' WHERE status = 'activo';
UPDATE projects SET status = 'finalizado'   WHERE status = 'cerrado';

COMMENT ON COLUMN projects.status IS
    'ETAPA H8 H-D80: pendiente | en_ejecucion | detenido | no_viable | finalizado. '
    'Lo decide una persona y es independiente del consumo (§3.1 de la '
    'especificacion v1.5). El antiguo «cerrado» es ahora «finalizado» (H-D81). '
    'Acepta ademas activo|cerrado mientras dura el despliegue de H8.';

COMMIT;

-- 3. La comprobacion. Deberia salir una fila por estado, y ninguna con
--    'activo' ni 'cerrado'.
SELECT status, count(*) AS proyectos
FROM projects
GROUP BY status
ORDER BY status;
