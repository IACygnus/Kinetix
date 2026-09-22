#!/bin/sh
# O-D12 — el rol de solo lectura del recolector.
#
# `pg_monitor` da acceso a las VISTAS DE ESTADISTICA (pg_stat_*), no a los datos.
# Este rol no tiene SELECT sobre `productos` ni sobre `pedidos`, y eso se
# comprueba en el cierre de la etapa: es el argumento que se le ensena a un
# cliente cuando pregunta que vamos a ver de su base.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE kinetix_lector LOGIN PASSWORD '${LAB_PG_LECTOR_PASSWORD}';
GRANT pg_monitor TO kinetix_lector;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO kinetix_lector;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kinetix_lector;
SQL
