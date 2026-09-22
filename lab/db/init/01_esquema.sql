-- LABORATORIO O2a — el esquema de la tienda de mentira (O-D9).
--
-- Dos tablas y un detalle a proposito: `descripcion` NO tiene indice de texto.
-- La busqueda pesada del endpoint /buscar tiene que recorrer la tabla entera,
-- porque una consulta que no cuesta no sirve para ver subir una CPU.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE productos (
    id          BIGSERIAL PRIMARY KEY,
    sku         TEXT           NOT NULL,
    nombre      TEXT           NOT NULL,
    descripcion TEXT           NOT NULL,
    categoria   TEXT           NOT NULL,
    precio      NUMERIC(10, 2) NOT NULL,
    existencias INTEGER        NOT NULL
);

CREATE INDEX ix_productos_categoria ON productos (categoria);
CREATE UNIQUE INDEX ux_productos_sku ON productos (sku);

CREATE TABLE pedidos (
    id           BIGSERIAL PRIMARY KEY,
    producto_id  BIGINT      NOT NULL REFERENCES productos (id),
    cantidad     INTEGER     NOT NULL CHECK (cantidad > 0),
    cliente      TEXT        NOT NULL,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_pedidos_producto ON pedidos (producto_id);
CREATE INDEX ix_pedidos_creado ON pedidos (creado_en);
