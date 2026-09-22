-- 1.500.000 productos. Con 200.000 no bastaba: PostgreSQL los recorre en
-- paralelo en 50 ms y la busqueda no costaba nada. Con este volumen una
-- busqueda por texto sin indice tarda medio segundo y se ve en la grafica.

INSERT INTO productos (sku, nombre, descripcion, categoria, precio, existencias)
SELECT
    'SKU-' || lpad(i::text, 8, '0'),
    'Producto ' || i,
    'Articulo numero ' || i || ' ' || md5(i::text) || ' ' || md5((i * 7)::text)
        || ' ' || md5((i * 13)::text),
    (ARRAY['herramientas', 'hogar', 'jardin', 'oficina', 'deporte', 'cocina'])[1 + (i % 6)],
    round((10 + (i % 90000) / 100.0)::numeric, 2),
    (i % 500)
FROM generate_series(1, 1500000) AS i;

INSERT INTO pedidos (producto_id, cantidad, cliente)
SELECT
    1 + (i % 1500000),
    1 + (i % 9),
    'cliente-' || (i % 500)
FROM generate_series(1, 200000) AS i;

ANALYZE productos;
ANALYZE pedidos;
