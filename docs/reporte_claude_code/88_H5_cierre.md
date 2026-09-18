25b2897 · 2026-09-18

# ETAPA H5 — Cierre: el informe de horas

**0 llamadas a la IA en toda la etapa.**

---

## 1. Qué pedía la etapa y qué quedó

| Decisión | Qué pedía | Estado |
|---|---|---|
| **H-D50** | Un solo informe, no tres | Hecho: HTML y PDF son el mismo módulo con dos ramas |
| **H-D51** | Generador propio, sin tocar `report_generator.py` | Hecho, y sus reglas de PDF comprobadas una a una |
| **H-D52** | Las diez secciones, en orden | Hechas |
| **H-D53** | Filtros y casillas por sección | Hechos, y probado que quitar una la quita |
| **H-D54** | Logo embebido; sin él, el nombre en texto | Hecho. **El archivo aún no existe** (punto 6) |
| **H-D55** | HTML interactivo y autocontenido | Hecho: ni una referencia a la red |
| **H-D56** | PDF de orientación mixta, con selector | Hecho, medido página a página |
| **H-D57** | La previa enseña el documento real | Hecho |
| **H-D58** | El detalle no entra al PDF por defecto | Hecho |
| **H-D59** | CSV del detalle, con BOM | Hecho |
| **H-D60** | Formato español en todo | Hecho |
| **H-D61** | Nombres de archivo en minúsculas y sin tildes | Hecho |
| **H-D62** | HTML < 5 s y PDF < 15 s con ~300 registros | **0,03 s y 1,10 s** con 312 |

---

## 2. Los sub-pasos

| Sub-paso | Reporte | Commit |
|---|---|---|
| H5.1 Diagnóstico y especificación v1.2 | 84 | `2543726` |
| H5.2 Los datos del informe | 85 | `bc0f952` |
| H5.3 y H5.4 El HTML y el PDF | 86 | `25b2897` |
| H5.5 y H5.6 La pantalla y la validación | 87 | este commit |
| H5.7 Cierre | 88 (este), 89 | — |

---

## 3. Lo que se construyó

**Backend** — tres módulos nuevos, ninguna columna nueva, ninguna dependencia
nueva:

- `services/horas/informe_datos.py` (356): las diez secciones en una pasada.
- `services/horas/informe.py` (718): el documento, en sus dos ramas.
- `api/v1/endpoints/time_informe.py` (233): `/informe`, `/html`, `/pdf`, `/csv`.

**Frontend**:

- `pages/horas/InformesPage.tsx` (581): cuatro pestañas, filtros, secciones,
  orientación y las tres descargas.
- `api/horasApi.ts`: los tipos del informe, las dos llamadas y el serializador de
  listas.

**El esquema no se tocó.** El informe solo lee.

---

## 4. Verificación — 154 comprobaciones propias, todas pasan

| Prueba | Qué mira | Resultado |
|---|---|---|
| `h52_informe.py` | 60 por HTTP: las diez secciones, que **cuadren entre sí** y con la consulta y el calendario, los filtros y los bordes | TODO PASA |
| `h53_h54_documento.py` | 58: el HTML autocontenido abierto en Chromium, sus botones, el CSV con BOM, y el PDF con su orientación medida | TODO PASA |
| `h56_pantalla.py` | 36 de punta a punta: pestañas, quitar secciones, filtros, orientación, las tres descargas y el HTML descargado | TODO PASA |

### El resto del producto no se movió

| Prueba | Resultado |
|---|---|
| `verificar_etapa2.py` — las cuatro salidas | **LAS CUATRO SALIDAS PASAN** |
| H1, H2, H2b y H3 — seis suites | TODO PASA |
| `pytest tests/` | **665 pasan**, 1 falla — la anterior al plan (reporte 66) |
| `npx tsc --noEmit` | sin errores |

---

## 5. Las decisiones técnicas de la etapa

| Decisión | Justificación |
|---|---|
| **Las diez secciones se arman una sola vez** | dos salidas montando sus tablas por su cuenta acaban diciendo cosas distintas; es lo que costó la Etapa 2 entera arreglar |
| **Un endpoint de datos, no seis** | seis llamadas darían seis momentos de la base, y cuadrar es lo que se le pide a un informe |
| **La jornada esperada llega hasta hoy** | si no, el informe del mes en curso daría una ocupación del 2 % el día 2, y la ocupación y los días pendientes se medirían con reglas distintas |
| **El mapa, en papel, habla por color** | «ningún texto por debajo de 8 pt» y 31 columnas en vertical no caben juntos; las horas exactas están en la sección 9 |
| **La orientación se mide sobre el HTML de impresión** | WeasyPrint comprime los objetos del PDF y `/MediaBox` no se puede leer del archivo escrito |
| **El PDF se renderiza y se escribe en dos pasos** | es la única forma de contar sus páginas para la vista previa |
| **La previa se pide con axios y se enseña desde un blob** | la cookie de sesión viaja siempre, sin depender de cómo trate el navegador un marco de otro origen |
| **El JavaScript del HTML solo suma filas del detalle** | es el mismo dato crudo que sumó el backend; lo que depende de la jornada o de las estimaciones se filtra por fila y el documento lo dice |
| **`paramsSerializer` en las llamadas con listas** | axios manda `seccion[]=` y FastAPI espera `seccion=`; con corchetes se queda con el valor por defecto **sin dar ningún error** |

---

## 6. Lo que NO se tocó, y lo que queda pendiente

- Ningún archivo protegido. Ningún compose, ningún servidor, ningún despliegue.
- Ninguna columna nueva, ninguna dependencia nueva.
- El módulo de análisis, entero.

**El logo sigue sin existir.** `backend/app/assets/logo-sqa.png` no está, y por
H-D54 eso no es parada: el informe sale con el nombre en texto y funciona. En
cuanto el archivo esté en esa ruta lo tomará solo, sin reiniciar nada: se lee en
cada generación y se embebe en base64.

---

## 7. Tres fallos que la etapa destapó

1. **La jornada esperada contaba los días futuros**, mientras los días pendientes
   ya los excluían desde H2b: dos reglas para lo mismo.
2. **Quitar una sección no quitaba nada**, por los corchetes de axios. Silencioso:
   ni un error, ni un aviso. Afectaba también al filtro de personas.
3. **Dos aserciones mías eran malas**: una comparaba contra un contador en vez de
   contra el informe, y **otra era vacua** —`ok(True, …)`— y habría pasado con el
   orden roto.

Los dos primeros los encontró la prueba; el tercero, releer lo que había escrito.

---

## 8. Una nota de método

La primera vuelta de la regresión la lancé **mientras H5.6 seguía creando sus 312
registros**, y tres suites fallaron con totales que no cuadraban. No era el
producto: era cómo las corrí. Las pruebas de horas comparten mes y personas, así
que **van en serie**. Queda dicho para la próxima.

---

**Estado: Etapa H5 implementada, pendiente validación de Fredy.**
