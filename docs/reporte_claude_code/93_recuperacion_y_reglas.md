c012493 · 2026-09-20

# RECUPERACIÓN — los datos de Fredy, el logo y las seis reglas nuevas

**0 llamadas a la IA.**

---

## 1. Primero la copia de seguridad (R5)

Antes de tocar nada:

```
C:\proyectos\Kinetix_pruebas\backup_20260918_232433.sql   6.716.022 bytes
```

Comprobada por dentro: trae las 25 tablas y, en `time_entries`, los tres
registros manuales de Fredy con sus observaciones. Es exactamente lo que faltó el
18 de septiembre.

---

## 2. Lo recuperado

Se reimportó `horas_muestra.xlsx` **desde la pantalla**, a nombre de **Fredy
Gabriel Bonilla Becerra**, con la vista previa delante antes de confirmar —como
lo haría él, no llamando a la API a pelo—.

```
--- LA VISTA PREVIA ---
    Se crean         21
    Se actualizan    0
    No se importan   0
    Horas            75,5
    clientes a crear     5
    proyectos a crear    9
    actividades a crear  3

--- EL RESUMEN ---
    Importadas 75,5 h a nombre de Fredy Gabriel Bonilla Becerra:
    21 nuevas y 0 actualizadas.
    proyectos nuevos sin estimar: 9
```

| | Antes | Después | Recuperado |
|---|---|---|---|
| Registros | 3 | **24** | **+21** (75,5 h) |
| Proyectos | 1 | **10** | **+9** |
| Clientes | 8 | **13** | **+5** |
| Actividades | 5 | **8** | **+3** |

Y lo que importaba tanto como recuperar: **sus tres registros manuales de
«performance avion» siguen intactos**, con sus 5 actividades estimadas y sus 41 h.

```
 source | registros | horas |   desde    |   hasta
--------+-----------+-------+------------+------------
 import |        21 | 75.50 | 2026-09-01 | 2026-09-11
 manual |         3 |  6.00 | 2026-09-14 | 2026-09-17
```

Cero errores de JavaScript durante el proceso.

---

## 3. Lo que queda pendiente de teclear

**Las 14 estimaciones.** Los nueve proyectos importados están **sin horas
estimadas**, que es como nacen (§6.2.4), y los valores que Fredy tecleó el 18 a
las 22:00 no están en el archivo: los decidió él.

Los nueve, con su enlace desde el resumen de la importación:

```
SQA CoE · Preventa · SQ-AI Performance · NOVA - UAT · SQ-AI Funcional
Preventa · Brebia · SQ-AI Funcional · Bancoomeva
```

(«Preventa» y «SQ-AI Funcional» aparecen dos veces porque son de clientes
distintos.)

**No se tocó el WAL**, como se pidió. Mientras no tengan estimación, ninguno
puede salir desfasado: sin estimación no hay contra qué comparar.

---

## 4. El logo

El archivo que dejó Fredy —`logo-sqa.png.webp`— **es una imagen válida**, pero un
WEBP con extensión de PNG:

```
formato real: WEBP · modo: RGB · tamaño: (135, 90)
```

Convertido con Pillow a `backend/app/assets/logo-sqa.png`: 7.992 bytes, firma PNG
correcta, mismo tamaño. **El original se conserva**, no se borró.

| Comprobación | Resultado |
|---|---|
| El informe lo encuentra y lo embebe | sí, 10.656 caracteres en base64 |
| HTML: `<img class="logo" src="data:image/png;base64,…` | sí |
| HTML: sigue sin depender de la red | sí |
| HTML: ya no sale el nombre en texto | sí |
| PDF: lleva la imagen dentro | sí (3 páginas, 37.075 bytes) |
| En pantalla: cargada y a 125 × 83 px | sí |

Captura de la cabecera en `C:\proyectos\Kinetix_pruebas\cabecera_informe.png`, y
la de la vista previa de la recuperación en `recuperacion_previa.png`.

**Un aviso honesto sobre la calidad:** el original mide 135 × 90 px. A los 22 mm
de alto de la cabecera del PDF eso son unos 104 puntos por pulgada, por debajo de
los 300 que pide una impresión fina. En pantalla se ve perfecto y en papel se lee,
pero si se quiere impecable impreso, hace falta el logo en mayor resolución —un
SVG o un PNG de unos 400 px de alto—. No es un problema del código: el informe
tomará el archivo que haya.

---

## 5. Las seis reglas, en CLAUDE.md

Añadidas como **§13.1, reglas 28 a 33**, con el porqué delante para que no se lean
como consejos:

| # | Regla |
|---|---|
| 28 (R1) | **Prohibido borrar filas con SQL a mano.** Si hay que borrar, se para y se pide |
| 29 (R2) | **Las pruebas marcan sus datos** con el prefijo `ZZTEST-`, y limpian solo por él |
| 30 (R3) | **Nada se borra por diferencia.** Sin la marca de R2, no es mío |
| 31 (R4) | **No se edita el frontend con la aplicación abierta.** Avisar y esperar |
| 32 (R5) | **`pg_dump` antes de cualquier operación destructiva.** Sin copia no se empieza |
| 33 (R6) | **Un reporte no afirma lo que no ha comprobado.** Ante la duda, se declara |

---

## 6. El reporte 90, corregido

En §7 del reporte 90 hay ahora un aviso que dice que ese párrafo **es falso**, con
las horas y las transacciones que lo demuestran, y remite al 92 y a este. **El
texto original se deja sin borrar**: el error tiene que quedar a la vista, que es
para lo único que sirve.

---

## 7. Lo que falta, y es de Fredy

1. **Teclear las 14 estimaciones** en los nueve proyectos de arriba.
2. **Decidir si quiere el logo en más resolución** para el PDF impreso.

**Estado: datos recuperados, estimaciones pendientes de teclear.**
