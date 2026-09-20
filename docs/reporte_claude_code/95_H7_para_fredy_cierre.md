37c6685 · 2026-09-20

# ETAPA H7 — para Fredy

---

## El módulo de horas está terminado

Cinco pantallas, cuatro salidas del informe, siete tablas y un tag: `v4.1.0`.

**Falta usted.** H5, H6 y H7 no las ha validado todavía. Lo que sigue es lo que
miden las pruebas, no su visto bueno.

---

## Qué se hizo en esta etapa

### 1. La portada, como la aprobó

Arriba, el logo a la izquierda y «Centro de Excelencia · **Performance**» al
lado, con la fecha de generación a la derecha. Debajo, la banda azul con su
tramo naranja. Luego el título, y el período en naranja. Y al pie de la portada,
una tabla con cuatro datos:

```
DIRIGIDO A     José Javier Rodríguez Santos · Delivery Manager
PERÍODO        septiembre de 2026
EQUIPO         (las personas del período)
CAPACIDAD BASE 22 días hábiles · 185 h por analista
```

Sale igual en pantalla y en el PDF.

### 2. «Dirigido a» se puede cambiar

Hay un campo en la pantalla de Informes. Escriba otro nombre y sale ese. Déjelo
en blanco y vuelve José Javier: un informe no se publica sin destinatario porque
alguien borró el campo sin querer.

### 3. La capacidad base

**22 días hábiles · 185 h por analista** para septiembre de 2026. Son 18 días de
lunes a jueves a 8,5 h más 4 viernes a 8,0 h. No es una cuenta aparte: sale del
mismo calendario que pinta la pantalla de Registro, así que las dos cifras no
pueden discrepar.

### 4. Las pruebas ya no tocan su base

Esto es lo importante de la etapa.

Hay una segunda base, `jmeter_analyzer_test`, y un segundo backend en el puerto
**8002** apuntando a ella. **Todas** las suites de horas corren ahí. La suya, el
8001, ni se abre.

Lo comprobé de la forma que vale: tomé la huella de su base antes de la corrida
completa y la volví a tomar después.

```
=== ANTES ===   86f88bf73ffe47f15226188e5c58caaa   ·   24 10 8 13 5 5

  … las once suites de horas, una detrás de otra …

=== DESPUÉS === 86f88bf73ffe47f15226188e5c58caaa   ·   24 10 8 13 5 5
```

Es el mismo `md5` de todos sus registros y las mismas seis cuentas. Si hubiera
cambiado una hora de un solo día, sería distinto.

Y por si algún día alguien apunta una suite al sitio equivocado, todas llevan
freno: si el nombre de la base no lleva «test», la prueba **se niega a borrar** y
se para.

---

## Tres cosas que aparecieron al cerrar

### La prueba de la pantalla de Registro llevaba rota desde H2b

Probaba la vista **semanal**, la que usted vio antes del calendario. Cuando en
H2b la cambiamos por el calendario del mes, esa prueba dejó de tener sentido —y
dejó de correr, así que nadie se enteró—. Está reescrita contra la pantalla que
existe hoy.

### Tres pantallas no tenían prueba de navegador

Consulta, Importar e Informes se probaron en su día con guiones que no se
guardaron. Ahora tienen la suya: la consulta con sus filtros, la importación de
un Excel de punta a punta —archivo, vista previa, confirmar, y el proyecto ya
está en la base— y el informe con sus cuatro pestañas.

### Una comprobación que llevaba desde H1.3 sin hacerse

Que un analista **no** pueda cerrar un proyecto. No se probaba porque hacía falta
la contraseña de Moni, y no la tengo ni la quiero. En la base de pruebas hay una
persona de mentira para eso, y ahora se prueba: da 403.

---

## Lo que queda en su tejado

1. **Las 14 estimaciones.** Los 21 registros, 9 proyectos, 14 actividades y 3
   clientes volvieron; las estimaciones que usted tecleó el 18 no. Hay que
   volver a ponerlas a mano.
2. **Validar H5, H6 y H7.** El informe, los diez ajustes y la portada.
3. **El logo**, si lo quiere más nítido. El que hay mide 135 × 90 px: a 22 mm de
   ancho son unos 104 puntos por pulgada. Se ve bien en pantalla y pasable
   impreso. Con el original en grande, mejora.

---

## Un fallo que verá y que no es de horas

Al correr `pytest` sale uno rojo:

```
tests/test_analysis_pipeline.py::test_pipeline_parsea_jtl_y_popula_metricas_basicas
```

Es de la parte de IA y viene del **13 de agosto**: un commit quitó un `import`
del módulo y la prueba siguió buscándolo. No lo he tocado —no es de esta etapa—
pero conviene saber que está ahí y que no lo trajo el módulo de horas.

---

## El resto, verde

| Suite | Comprobaciones |
|---|---|
| Actividades y proyectos (HTTP) | 24 |
| Actividades y proyectos (pantalla) | 22 |
| Registro de horas (HTTP) | 45 |
| Calendario y desfase | 53 |
| Calendario en pantalla | 36 |
| Consulta de proyectos | 53 |
| Datos del informe | 60 |
| El HTML y el PDF | 54 |
| Los ajustes de H6 | 54 |
| La portada | 27 |
| Consulta, importar e informes en pantalla | 36 |

**464 comprobaciones, todas verdes.** Y las cuatro salidas del informe de JMeter
—lo de antes del módulo de horas— siguen pasando: no se rompió nada de lo suyo
por el camino.

---

**Estado: módulo de horas completo — H5, H6 y H7 pendientes de su validación.**
