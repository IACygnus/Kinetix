Commit `a68f68a` · 24 de septiembre de 2026

# Las estimaciones de septiembre de 2026

Cargadas **1.200 horas estimadas** en **7 proyectos**, por el importador de
H8.5b. Con esto el desfase ya tiene contra qué comparar, que era lo que
bloqueaba la sección 6 del informe.

**0 llamadas a la IA.**

Copia previa: `backup_antes_estimaciones_20260924.sql`, 6.788.414 bytes.

---

## 1. Lo que entró

`docs/documentos carga/estimaciones_septiembre_2026.xlsx` — 33 filas, cinco
columnas (`Cliente · Proyecto · Estado · Actividad · Horas estimadas`), todas
con estado **En ejecución**.

La vista previa, antes de confirmar:

```
hoja «Estimaciones» · 33 filas · 1200 h
proyectos nuevos 0 · que ya existian 7
estimaciones: nuevas 33 · actualizadas 0 · iguales 0
clientes a crear: ninguno
actividades NUEVAS: ninguna
filas invalidas: 0
```

**Nada que crear.** Los siete proyectos casaron con los que ya estaban, los
clientes también y las actividades las reconoció el catálogo. Es la señal de que
los nombres eran los exactos de la base: si uno solo se hubiera escrito distinto,
el importador habría creado un proyecto nuevo en vez de estimar el que existe —y
lo habría dicho en la previa.

| Cliente | Proyecto | Actividades | Estimadas |
|---|---|---|---|
| BANCO FICOHSA | NOVA - Capa media | 6 | **375 h** |
| BANCO FICOHSA | Paquete 1 - PCKG1 | 6 | **250 h** |
| ALKOSTO | Migracion Manhathan_Performance | 4 | **200 h** |
| SODEXO (Pluxee) | Pluxee shop | 5 | **200 h** |
| Software Quality Assurance | 24352 sq-ai v2_Performance | 5 | **65 h** |
| MEDICINA PREPAGADA COOMEVA | 24353 Bre-b - Pruebas de WH (Pexto) | 6 | **60 h** |
| Software Quality Assurance | 24354 Pruebas funcionales sq-ai | 1 | **50 h** |

---

## 2. Las dos decisiones que se tomaron al emparejar

Las dos son de Fredy y quedan escritas porque **cambian lo que dice el informe**,
no solo cómo se cargó.

### 2.1 «NOVA - Capa media» suma los dos paquetes

En el cuadro de estimación de Fredy hay **dos**: PAQ1 con 112 h y PAQ2 con 263 h.
En la base hay **un solo proyecto** con ese nombre, así que las dos cifras se
sumaron: **375 h**.

Consecuencia, y conviene tenerla presente al leer el desfase: las 94,50 h
consumidas se comparan contra el trabajo de **los dos paquetes juntos**, no
contra uno. Sale un 25,2 %, que parece holgado; contra PAQ1 solo, sería un 84 %.

**Si Fredy los quiere separados**, se crea el segundo proyecto y se reparten las
horas: ni la carga ni el importador lo impiden, y el importador es idempotente
—reimportar actualiza al valor del archivo, no suma—.

### 2.2 «Entendimiento y planeación» va entera a Planeación

Los cuadros de Alkosto y Pluxee traen una sola cifra para «Entendimiento y
planeación». En el catálogo son **dos actividades** —`Etapa de conocimiento` y
`Planeación`—, y partir esa cifra por la mitad habría sido inventarse un número.

Se cargó **entera en Planeación** (6 h en cada uno de los dos proyectos). Por eso
esos dos son los únicos de los siete **sin `Etapa de conocimiento` estimada**, y
si alguien registra horas ahí saldrá desfasado desde la primera.

---

## 3. Lo que queda fuera, y por qué

### 3.1 Un proyecto del cuadro que no existe en la base

**«FICOHSA - Migracion datos»** está en el cuadro de estimación de Fredy y **no
existe como proyecto**: ninguno de los tres Excel de horas trajo un solo registro
suyo, así que la carga nunca lo creó.

No se cargó su estimación. Crearlo desde el importador habría metido un proyecto
sin una sola hora trabajada, solo porque aparecía en una hoja de cálculo.

### 3.2 Ocho proyectos con horas y sin cuadro de estimación

Tienen consumo pero no había estimación que cargarles. **Fredy los estimará a
mano.** Siguen en 0 estimadas, y su consumo no significa nada hasta entonces:

| Cliente | Proyecto | Consumidas |
|---|---|---|
| PORVENIR | Apoyos_Performance_PORVENIR | 25,00 h |
| BANCO POPULAR | Banco Popular - Proyecto Bus | 16,50 h |
| SODEXO (Pluxee) | Carga masiva_Performance | 14,00 h |
| Software Quality Assurance | COE - UEN Financial | 7,00 h |
| Software Quality Assurance | COE - UEN Total | 5,00 h |
| MEDICINA PREPAGADA COOMEVA | 24355 Brebia_Performance | 2,00 h |
| Software Quality Assurance | COE - Corporativo | 1,75 h |
| MEDICINA PREPAGADA COOMEVA | 24342-Coomeva_SendCode_Performance | 1,00 h |
| Compensar | COMPENSAR - Generales | 0,50 h |

> Son **nueve filas**, no ocho: el encargo nombraba «los tres COE» como si fueran
> tres proyectos y en la base son tres —`COE - Corporativo`, `COE - UEN
> Financial` y `COE - UEN Total`—, más Banco Popular, Porvenir, Brebia, SendCode,
> Compensar y **`Carga masiva_Performance`**, que no estaba en la lista del
> encargo pero tampoco tiene cuadro. Nueve proyectos sin estimar en total.

### 3.3 Una actividad con horas y sin fila de estimación

En **`24354 Pruebas funcionales sq-ai`** el cuadro solo traía `Ejecución` (50 h),
pero el proyecto tiene además **0,75 h en `Gestión de proyectos`**. Esa actividad
queda con consumo y sin estimar dentro de un proyecto que sí está estimado.

No es un error de la carga —es lo que decía el cuadro— pero conviene saberlo: en
el desglose por actividad sale con estimadas 0.

---

## 4. Cómo quedó

**Ningún proyecto está desfasado ni por agotarse.** Los siete estimados van por
debajo del 80 %:

| Cliente | Proyecto | Estimadas | Consumidas | % | Consumo |
|---|---|---|---|---|---|
| Software Quality Assurance | 24352 sq-ai v2_Performance | 65,00 | 51,00 | **78,5 %** | En rango |
| Software Quality Assurance | 24354 Pruebas funcionales sq-ai | 50,00 | 37,25 | **74,5 %** | En rango |
| SODEXO (Pluxee) | Pluxee shop | 200,00 | 128,00 | 64,0 % | En rango |
| MEDICINA PREPAGADA COOMEVA | 24353 Bre-b - Pruebas de WH (Pexto) | 60,00 | 25,50 | 42,5 % | En rango |
| ALKOSTO | Migracion Manhathan_Performance | 200,00 | 58,50 | 29,2 % | En rango |
| BANCO FICOHSA | NOVA - Capa media | 375,00 | 94,50 | 25,2 % | En rango |
| BANCO FICOHSA | Paquete 1 - PCKG1 | 250,00 | 21,50 | 8,6 % | En rango |

**Pero el total del proyecto esconde lo que pasa dentro.** Por actividad hay
**seis** que piden atención, y son las que interesan:

| Consumo | Cliente / Proyecto | Actividad | |
|---|---|---|---|
| **Desfasado +17,5 h** | BANCO FICOHSA / Paquete 1 - PCKG1 | Gestión de proyectos | 21,50 de **4** — el 537 % |
| **Desfasado +4 h** | SODEXO (Pluxee) / Pluxee shop | Ejecución | 14,00 de **10** |
| Terminado | Software Quality Assurance / 24352 sq-ai v2_Performance | Diseño de script | 50,00 de 50 |
| Terminado | Software Quality Assurance / 24352 sq-ai v2_Performance | Planeación | 1,00 de 1 |
| Terminado | MEDICINA PREPAGADA COOMEVA / 24353 Bre-b (Pexto) | Gestión de proyectos | 4,00 de 4 |
| Terminado | MEDICINA PREPAGADA COOMEVA / 24353 Bre-b (Pexto) | Etapa de conocimiento | 2,00 de 2 |

**«Terminado» es el 100 % exacto**, ni una hora más: son actividades que agotaron
su bolsa justa. No es una alarma, pero la siguiente hora que se registre ahí las
pone en desfase.

El caso que destaca es **Gestión de proyectos en Paquete 1 - PCKG1**: 21,50 horas
contra 4 estimadas. Las 21,50 son las tres jornadas que Fredy y Mónica
registraron ahí los días 17 y 18 de septiembre. O la estimación se quedó corta, o
esas horas eran de otra actividad.

> Merece la pena verlo en la pantalla, porque es lo que H8 vino a permitir: **el
> proyecto entero va al 8,6 %** —parecería que sobra tiempo— y una de sus
> actividades está al 537 %. El total del proyecto solo no lo habría enseñado.

---

## 5. Los archivos

| Archivo | Qué |
|---|---|
| `docs/documentos carga/estimaciones_septiembre_2026.xlsx` | Las 33 filas. **No se versiona** (lleva clientes reales), igual que los Excel de horas |

Ni una línea de código. La carga entera se hizo por los endpoints de H8.5b, con
su vista previa antes de cada confirmación.

---

## 6. Lo que queda

- **La validación de Fredy**, que es el único criterio (regla 9).
- **Estimar los nueve proyectos de §3.2** a mano.
- **Decidir si `NOVA - Capa media` se parte en dos** (§2.1).
- **Revisar `Gestión de proyectos` en Paquete 1 - PCKG1** (§4).
