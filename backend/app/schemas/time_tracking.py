"""Schemas del MÓDULO DE HORAS (ETAPA H1.3).

Mismo estilo que `schemas/client.py`: `XCreate` / `XUpdate` / `XResponse` con
`ConfigDict(from_attributes=True)`.

La validación de las horas en pasos de 0,25 (H-D8) vive aquí además de en la
base: el schema devuelve un **422 con mensaje legible** y la restricción de la
base es la última red, que devolvería un 500 feo si llegara a saltar.
"""
from datetime import date, datetime
from datetime import date as DateOnly
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

# H-D8: paso de las horas. En Decimal para no arrastrar el error del binario.
PASO_HORAS = Decimal("0.25")


def validar_paso(valor: Decimal, campo: str = "Las horas") -> Decimal:
    """Horas > 0 y múltiplo de 0,25 (H-D8)."""
    if valor is None:
        return valor
    v = Decimal(str(valor))
    if v <= 0:
        raise ValueError(f"{campo} tienen que ser mayores que cero")
    if (v % PASO_HORAS) != 0:
        raise ValueError(f"{campo} van en pasos de 0,25 (recibido: {v})")
    return v


# ===================== ACTIVIDADES =====================

class ActivityCreate(BaseModel):
    name: str


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class ActivityResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    # Cuántos proyectos la usan: es lo que decide si se puede borrar (H-D4) y lo
    # que la pantalla necesita para explicar por qué no.
    projects_count: int = 0
    # Si tiene horas registradas. Con horas NO se borra nunca, ni siendo admin.
    has_entries: bool = False

    model_config = ConfigDict(from_attributes=True)


# ===================== PROYECTOS =====================

class ProjectActivityInput(BaseModel):
    activity_id: UUID
    estimated_hours: Decimal

    @field_validator("estimated_hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v, "Las horas estimadas")


class ProjectCreate(BaseModel):
    client_id: UUID
    name: str
    description: Optional[str] = None
    # §3: al crear hace falta al menos una actividad con horas.
    activities: List[ProjectActivityInput]

    @field_validator("activities")
    @classmethod
    def _al_menos_una(cls, v):
        if not v:
            raise ValueError("Un proyecto necesita al menos una actividad con horas estimadas")
        vistas = {a.activity_id for a in v}
        if len(vistas) != len(v):
            raise ValueError("Hay una actividad repetida en la lista")
        return v


class ProjectUpdate(BaseModel):
    """Editar el proyecto. Las actividades se gestionan por su propio endpoint,
    para que cada cambio de estimación escriba su historial (H-D11)."""
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectActivityResponse(BaseModel):
    activity_id: UUID
    activity_name: str
    estimated_hours: Decimal
    # H1.3: `consumed_hours` es 0 mientras no exista el registro de horas (H2).
    # El contrato se fija YA para que H2 y H3 no tengan que cambiarlo.
    consumed_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
    # §4.2.4: marca de desfase, para pintarla en color sin recalcular en la
    # pantalla. El nombre interno se conserva (H-D27): lo que cambia es el texto.
    over_estimate: bool = False
    # ETAPA H2b (§5.1): el mismo estado por actividad, para ver CUÁL es la que
    # está tirando del proyecto, no solo que el proyecto va mal.
    consumed_pct: Decimal = Decimal("0")
    overrun_status: str = "en_rango"
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"


class ProjectResponse(BaseModel):
    """Un proyecto en el listado.

    **Estado y consumo son dos cosas** (§5.1, H-D82) y van en campos distintos:

        status / status_label     en qué punto está el trabajo (§3.1)
        overrun_status / _label   cuántas horas lleva de las estimadas

    Nunca se mezclan en un campo: dicen cosas distintas y las dos importan.
    """
    id: UUID
    client_id: UUID
    client_name: str = ""
    name: str
    description: Optional[str] = None
    # ETAPA H8 (§3.1): pendiente | en_ejecucion | detenido | no_viable | finalizado
    status: str
    status_label: str = "En ejecución"
    created_at: datetime
    total_estimated_hours: Decimal = Decimal("0")
    total_consumed_hours: Decimal = Decimal("0")
    activities_count: int = 0
    # ETAPA H2b (§5.1). Campos AÑADIDOS: el contrato que cerraron H1 y H2 no
    # cambia, así que nada de lo que ya consumía esta respuesta se entera.
    consumed_pct: Decimal = Decimal("0")
    # v1.5: CUATRO valores. `cerrado` salió de aquí y es un estado (H-D82).
    overrun_status: str = "en_rango"      # en_rango | por_agotarse | terminado | desfasado
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"
    # ETAPA H8: la tabla de §3.1, ya resuelta, para que la pantalla **no la
    # vuelva a escribir en TypeScript**. Dos copias de la misma regla acaban
    # diciendo cosas distintas en cuanto una de las dos cambia.
    can_log_hours: bool = True
    can_edit_estimates: bool = True

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(ProjectResponse):
    activities: List[ProjectActivityResponse] = []


class ProjectStatusUpdate(BaseModel):
    """Cambiar el estado del proyecto (ETAPA H8, H-D83, §3.1)."""
    status: str


class ProjectStatusChangeResponse(BaseModel):
    """Una línea del historial de estados (H-D83)."""
    id: UUID
    previous_status: Optional[str] = None
    previous_label: str = ""
    new_status: str
    new_label: str = ""
    changed_by_name: str = ""
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectActivityUpsert(BaseModel):
    """Añadir una actividad al proyecto o cambiar su estimación (H-D11/H-D12)."""
    activity_id: UUID
    estimated_hours: Decimal

    @field_validator("estimated_hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v, "Las horas estimadas")


# ===================== REGISTRO DE HORAS (ETAPA H2) =====================

class TimeEntryCreate(BaseModel):
    """§1.1. `user_id` solo lo manda el admin al registrar por otra persona
    (H-D13); si no viene, son las horas de quien registra."""
    user_id: Optional[UUID] = None
    date: DateOnly
    project_id: UUID
    activity_id: UUID
    hours: Decimal
    billable: bool
    overtime: bool = False
    notes: Optional[str] = None

    @field_validator("hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v)

    @field_validator("date")
    @classmethod
    def _sin_futuro(cls, v):
        """H-D21: hacia atrás sin límite —§4.2.3 habla del olvido—, pero no se
        adelantan horas que todavía no se han trabajado."""
        if v > date.today():
            raise ValueError("No se pueden registrar horas con fecha futura")
        return v


class TimeEntryUpdate(BaseModel):
    date: Optional[DateOnly] = None
    project_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    hours: Optional[Decimal] = None
    billable: Optional[bool] = None
    overtime: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("hours")
    @classmethod
    def _paso(cls, v):
        return validar_paso(v) if v is not None else v

    @field_validator("date")
    @classmethod
    def _sin_futuro(cls, v):
        if v is not None and v > date.today():
            raise ValueError("No se pueden registrar horas con fecha futura")
        return v


class TimeEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str = ""
    created_by: Optional[UUID] = None
    created_by_name: str = ""
    date: DateOnly
    client_id: Optional[UUID] = None
    client_name: str = ""
    project_id: UUID
    project_name: str = ""
    project_status: str = "en_ejecucion"
    project_status_label: str = "En ejecución"
    activity_id: UUID
    activity_name: str = ""
    hours: Decimal
    billable: bool
    overtime: bool
    notes: Optional[str] = None
    source: str = "manual"
    # H-D16: si esta actividad, en este proyecto, ya pasó de lo estimado. Se
    # calcula en el backend para que la pantalla no sume por su cuenta.
    over_estimate: bool = False

    model_config = ConfigDict(from_attributes=True)


class DiaResponse(BaseModel):
    """Un día ya resuelto por `services/horas/calendario.py`. La pantalla lo
    pinta tal cual: no recalcula ni la jornada ni el 'incompleto'."""
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    overtime_hours: Decimal
    total_hours: Decimal
    is_holiday: bool = False
    is_absence: bool = False
    non_working_reason: str = ""
    incomplete: bool = False
    missing_hours: Decimal = Decimal("0")
    entries: List[TimeEntryResponse] = []


class WeekResponse(BaseModel):
    user_id: UUID
    user_name: str = ""
    week_start: DateOnly
    week_end: DateOnly
    days: List[DiaResponse] = []
    total_expected: Decimal = Decimal("0")
    total_ordinary: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")


class MonthDayResponse(BaseModel):
    """Una casilla del calendario (ETAPA H2b, §4.1).

    Todo viene resuelto: la pantalla pinta, no calcula.
    """
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    overtime_hours: Decimal
    total_hours: Decimal
    is_holiday: bool = False
    is_absence: bool = False
    non_working_reason: str = ""
    incomplete: bool = False
    missing_hours: Decimal = Decimal("0")
    entries_count: int = 0
    # Si alguno de sus registros cae en una actividad desfasada (H-D27).
    has_over_estimate: bool = False


class MonthResponse(BaseModel):
    user_id: UUID
    user_name: str = ""
    year: int
    month: int
    first_day: DateOnly
    last_day: DateOnly
    days: List[MonthDayResponse] = []
    total_expected: Decimal = Decimal("0")
    total_ordinary: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")
    pending_days: int = 0


class PendingDayResponse(BaseModel):
    date: DateOnly
    expected_hours: Decimal
    ordinary_hours: Decimal
    missing_hours: Decimal
    # El lunes de su semana: es lo que el enlace de H-D18 necesita para abrir la
    # vista con ese día enfocado.
    week_start: DateOnly


class ActivityAvailabilityResponse(BaseModel):
    """Lo que necesita el aviso de exceso (H-D16) sin pedir el detalle entero."""
    activity_id: UUID
    activity_name: str
    estimated_hours: Decimal
    consumed_hours: Decimal
    remaining_hours: Decimal
    over_estimate: bool


# ===================== CONSULTA (ETAPA H3, §5) =====================

class ConsultaPersona(BaseModel):
    """Quién registró y cuántas horas, dentro del rango consultado (H-D32)."""
    user_id: UUID
    user_name: str = ""
    hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    entries_count: int = 0


class ConsultaProyecto(BaseModel):
    """Un proyecto en la consulta.

    Ojo a las dos cifras de horas, que **no son la misma** y por eso van con
    nombres distintos:

    - `hours_in_range` es lo registrado **dentro del rango consultado**;
    - `consumed_hours` es todo lo que lleva el proyecto **desde siempre**, que es
      contra lo que se mide el desfase.

    Mezclarlas daría un proyecto «en rango» solo por haber consultado una semana
    tranquila, y contradiría a la pantalla de Proyectos.
    """
    project_id: UUID
    project_name: str = ""
    client_id: UUID
    client_name: str = ""
    # ETAPA H8 (§5.1): el estado y el consumo, en campos distintos.
    status: str = "en_ejecucion"
    status_label: str = "En ejecución"
    estimated_hours: Decimal = Decimal("0")
    consumed_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
    consumed_pct: Decimal = Decimal("0")
    overrun_status: str = "en_rango"
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"
    hours_in_range: Decimal = Decimal("0")
    overtime_in_range: Decimal = Decimal("0")
    entries_in_range: int = 0
    people: List[ConsultaPersona] = []


class ConsultaResponse(BaseModel):
    desde: DateOnly
    hasta: DateOnly
    projects: List[ConsultaProyecto] = []
    total_hours: Decimal = Decimal("0")
    total_overtime: Decimal = Decimal("0")
    projects_count: int = 0
    people_count: int = 0
    # §5.1: cuántos proyectos están desfasados, para el aviso de arriba.
    overrun_count: int = 0


# ===================== IMPORTACIÓN (ETAPA H3, §6) =====================

class FilaImportacion(BaseModel):
    """Una fila del archivo, ya leída y decidida.

    `numero` es el número de fila **del archivo**, para que quien lea un aviso
    pueda ir a mirarla (H-D40).
    """
    numero: int
    accion: str = "nueva"          # nueva | actualiza | invalida
    motivo: str = ""               # por qué es inválida (H-D40)
    external_id: str = ""
    date: Optional[DateOnly] = None
    client_name: str = ""
    project_name: str = ""
    activity_name: str = ""
    # §4: lo que venía escrito en el archivo, cuando la tabla de sinónimos lo
    # tradujo a otra cosa. Vacío = el archivo ya decía el nombre del catálogo.
    # Se enseña para que se vea QUÉ se tradujo, no solo el resultado.
    activity_original: str = ""
    hours: Optional[Decimal] = None
    billable: bool = False
    overtime: bool = False
    notes: str = ""
    # Qué se crearía por culpa de esta fila (H-D36, H-D48).
    crea_cliente: bool = False
    crea_proyecto: bool = False
    crea_actividad: bool = False
    # H-D38: cómo queda esa actividad del proyecto si entra esta fila.
    overrun_status: str = "en_rango"
    overrun_hours: Decimal = Decimal("0")
    overrun_label: str = "En rango"
    # Al actualizar, si el registro cambia de persona.
    cambia_de_persona: bool = False
    # ETAPA H8 (§6.2.8): la fila entra, pero su proyecto no está en ejecución.
    # Se marca para que la previa lo diga fila a fila, no solo en el total.
    project_status: str = "en_ejecucion"
    project_status_label: str = ""


class ProyectoAImportar(BaseModel):
    client_name: str
    project_name: str


class ProyectoNoEnEjecucion(BaseModel):
    """Un proyecto que recibe filas sin estar en ejecución (ETAPA H8, §6.2.8).

    No es un error: la importación entra igual. Es lo que hace falta saber
    **antes** de confirmar, y por eso lleva el nombre, el estado y cuántas filas
    caen ahí — decir solo «hay filas en proyectos parados» no deja decidir nada.
    """
    project_name: str = ""
    client_name: str = ""
    status: str = ""
    status_label: str = ""
    filas: int = 0
    horas: Decimal = Decimal("0")


class ActividadNueva(BaseModel):
    """Una actividad del archivo que NO estaba en el catálogo.

    No es un error —se crea igual (§4)—, es lo que hay que ver antes de
    confirmar. Lleva **en qué filas aparece y cuántas horas trae**, no solo el
    nombre: con el nombre a secas no se puede decidir si falta un sinónimo o si
    de verdad es una actividad nueva. Si trae 40 horas repartidas en 12 filas,
    casi seguro es una variante de escritura de una de las ocho.

    La misma clase sirve a las dos importaciones: en la de registros `horas` son
    horas trabajadas y en la de proyectos, horas estimadas.
    """
    name: str
    filas: List[int] = []
    horas: Decimal = Decimal("0")


class VistaPreviaImportacion(BaseModel):
    """Lo que se verá ANTES de escribir nada (§6.2.5). Nada de esto toca la base."""
    sheet: str = ""
    sheets: List[str] = []
    user_id: UUID
    user_name: str = ""
    total_filas: int = 0
    nuevas: List[FilaImportacion] = []
    actualizadas: List[FilaImportacion] = []
    invalidas: List[FilaImportacion] = []
    desfasadas: List[FilaImportacion] = []
    clientes_a_crear: List[str] = []
    proyectos_a_crear: List[ProyectoAImportar] = []
    actividades_a_crear: List[str] = []
    # §4 (carga real): las mismas de `actividades_a_crear`, pero con sus filas y
    # sus horas. La lista de nombres se conserva porque la pantalla y las suites
    # de H3 ya la leen; este bloque es el que se enseña.
    actividades_nuevas: List[ActividadNueva] = []
    total_horas: Decimal = Decimal("0")
    # ETAPA H8 (§6.2.8): el aviso. Las filas SÍ entran —salvo las de un proyecto
    # `no_viable`, que van en `invalidas` con su motivo—, pero antes de
    # confirmar hay que ver cuántas son y en qué proyectos caen.
    proyectos_no_en_ejecucion: List[ProyectoNoEnEjecucion] = []
    filas_no_en_ejecucion: int = 0


class ProyectoCreado(BaseModel):
    """H-D37: con su id, para que el resumen ofrezca el enlace que lleva a
    ponerle las horas estimadas."""
    id: UUID
    name: str
    client_name: str = ""


class ResumenImportacion(BaseModel):
    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0
    total_horas: Decimal = Decimal("0")
    clientes_creados: List[str] = []
    actividades_creadas: List[str] = []
    # §4: el resumen lo repite, para que quede a la vista DESPUÉS de confirmar.
    actividades_nuevas: List[ActividadNueva] = []
    proyectos_creados: List[ProyectoCreado] = []
    user_id: UUID
    user_name: str = ""


# ===================== EL INFORME (ETAPA H5, §7) =====================

class InformeFiltros(BaseModel):
    """Los filtros aplicados, tal como hay que escribirlos en el encabezado."""
    desde: DateOnly
    hasta: DateOnly
    periodo: str = ""              # «septiembre de 2026» o «del 1 al 15 de septiembre»
    personas: List[str] = []       # nombres, para el título
    alcance: str = "Equipo"        # «Equipo» o el nombre de la persona (H-D61)
    client_name: str = ""
    project_name: str = ""
    solo_facturables: bool = False
    # H-D74: a quién va dirigido el informe. Se puede cambiar antes de generarlo.
    dirigido_a: str = ""


class InformeCapacidad(BaseModel):
    """La capacidad base del periodo (H-D75), para la portada.

    **Es del periodo entero**, no «hasta hoy»: responde a «cuánto cabe en estas
    fechas», que es otra pregunta que «cuánto se ha devengado ya». La segunda la
    contesta `InformeResumen.expected_hours`, y son cifras distintas a propósito.

    Se calcula con el calendario laboral y los festivos nacionales; las ausencias
    de cada persona no entran, porque la capacidad base es la del calendario, no
    la de quien se fue de vacaciones.
    """
    working_days: int = 0
    hours_per_analyst: Decimal = Decimal("0")
    people_count: int = 0
    total_hours: Decimal = Decimal("0")


class InformeResumen(BaseModel):
    """Sección 1: los seis indicadores."""
    total_hours: Decimal = Decimal("0")
    ordinary_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    billable_pct: Decimal = Decimal("0")
    pending_days: int = 0
    # De apoyo, para el encabezado; no son de los seis.
    expected_hours: Decimal = Decimal("0")
    people_count: int = 0
    projects_count: int = 0
    entries_count: int = 0


class InformePersona(BaseModel):
    """Sección 2: ocupación de una persona frente a su jornada."""
    user_id: UUID
    user_name: str = ""
    expected_hours: Decimal = Decimal("0")
    total_hours: Decimal = Decimal("0")
    ordinary_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    occupancy_pct: Decimal = Decimal("0")
    pending_days: int = 0


class InformeFacturacion(BaseModel):
    """Sección 3: facturable frente a no facturable, por cliente."""
    client_name: str = ""
    billable_hours: Decimal = Decimal("0")
    non_billable_hours: Decimal = Decimal("0")
    total_hours: Decimal = Decimal("0")
    billable_pct: Decimal = Decimal("0")


class InformeReparto(BaseModel):
    """Secciones 4 y 5: el reparto de las horas, por cliente o por actividad."""
    name: str = ""
    hours: Decimal = Decimal("0")
    pct: Decimal = Decimal("0")


class InformeMapaPersona(BaseModel):
    """Sección 7: una fila por persona; `por_dia` va alineado con `InformeDatos.dias`.

    `estado` por día: trabajado | incompleto | festivo | ausencia | finde | vacio.
    """
    user_id: UUID
    user_name: str = ""
    por_dia: List[Decimal] = []
    estados: List[str] = []
    # ETAPA H8 (H-D85): las horas EXTRA de cada día, alineadas con `por_dia`.
    # La casilla se parte en proporción a las de cada tipo, así que hacen falta
    # las dos cifras: `por_dia` es el total y esta es la parte de arriba.
    # El dato ya existía en `DiaDelCalendario.extra` desde H2; el mapa solo
    # usaba el total y tiraba la mitad.
    extra_por_dia: List[Decimal] = []
    total_hours: Decimal = Decimal("0")


class InformePendiente(BaseModel):
    """Sección 8: un día sin registrar o por debajo de la jornada."""
    user_name: str = ""
    date: DateOnly
    expected_hours: Decimal = Decimal("0")
    ordinary_hours: Decimal = Decimal("0")
    missing_hours: Decimal = Decimal("0")


class InformeFilaDiaria(BaseModel):
    """Sección 9: una línea de proyecto y actividad, con sus horas día a día.

    `por_dia` va alineado con `InformeDatos.dias`. Es la tabla que obliga al PDF
    a girar la hoja (H-D56): con un mes entero no cabe en vertical.
    """
    client_name: str = ""
    project_name: str = ""
    activity_name: str = ""
    por_dia: List[Decimal] = []
    total_hours: Decimal = Decimal("0")


class InformeDatos(BaseModel):
    """Las ocho secciones, **ya calculadas**. La plantilla pinta, no calcula."""
    filtros: InformeFiltros
    dias: List[DateOnly] = []              # las columnas de la sección 7
    capacidad: InformeCapacidad = InformeCapacidad()   # H-D75, para la portada
    resumen: InformeResumen = InformeResumen()
    personas: List[InformePersona] = []
    facturacion: List[InformeFacturacion] = []
    por_cliente: List[InformeReparto] = []
    por_actividad: List[InformeReparto] = []
    proyectos: List[ConsultaProyecto] = []
    mapa: List[InformeMapaPersona] = []
    pendientes: List[InformePendiente] = []
    diarias: List[InformeFilaDiaria] = []
    detalle: List[TimeEntryResponse] = []
    # Cuántos registros hay en total, aunque el detalle venga recortado.
    detalle_total: int = 0
    generado: datetime


class ProjectActivityChangeResponse(BaseModel):
    id: UUID
    activity_id: UUID
    activity_name: str = ""
    previous_hours: Optional[Decimal] = None
    new_hours: Optional[Decimal] = None
    change_type: str
    changed_by_name: str = ""
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ BORRADO DE UN PERIODO (ETAPA H8.5, §4.3, H-D88/H-D89) ============

class BorradoPersona(BaseModel):
    """Cuánto pierde cada persona si se confirma."""
    user_name: str = ""
    entries: int = 0
    hours: Decimal = Decimal("0")


class BorradoPreview(BaseModel):
    """Lo que se verá ANTES de borrar nada. **Este endpoint no escribe.**

    Lleva todo lo que hace falta para decidir, y la frase exacta que hay que
    teclear: si la pantalla la compusiera por su cuenta, podría no coincidir con
    la que el backend espera y el botón no se activaría nunca.
    """
    desde: DateOnly
    hasta: DateOnly
    periodo: str = ""
    total_entries: int = 0
    total_hours: Decimal = Decimal("0")
    por_persona: List[BorradoPersona] = []
    # De dónde vinieron: dice si se está borrando lo que se importó o algo que
    # alguien tecleó a mano.
    de_importacion: int = 0
    manuales: int = 0
    # Lo que hay que teclear, literal.
    frase_de_confirmacion: str = ""
    # El `pg_dump` ya escrito, con la fecha puesta (H-D89). Kinetix no lo ejecuta.
    comando_copia: str = ""
    # §4.3 con esas palabras: qué sobrevive, y cuánto hay de cada cosa AHORA.
    lo_que_no_se_borra: str = ""


class BorradoConfirm(BaseModel):
    """La confirmación (§4.3). Las tres condiciones viajan explícitas."""
    desde: DateOnly
    hasta: DateOnly
    # H-D88: hay que teclear el periodo. Se compara normalizado.
    confirmacion: str
    # H-D89: la copia la hace una persona; el sistema solo la exige.
    copia_hecha: bool = False


class BorradoResumen(BaseModel):
    """Lo que se borró. Es lo mismo que queda en `time_entry_purges`."""
    desde: DateOnly
    hasta: DateOnly
    periodo: str = ""
    entries_deleted: int = 0
    hours_deleted: Decimal = Decimal("0")
    performed_by: str = ""
    performed_at: datetime
    lo_que_no_se_borro: str = ""


# ====== IMPORTACIÓN DE PROYECTOS Y ESTIMACIONES (ETAPA H8.5b, H-D94 a H-D101) ======

class FilaProyectoImportacion(BaseModel):
    """Una fila del archivo de proyectos, ya leída y decidida.

    `numero` es el número de fila **del archivo**, para poder ir a mirarla.
    """
    numero: int
    accion: str = "crea"           # crea | actualiza | igual | invalida
    motivo: str = ""               # por qué no entra (H-D100)
    client_name: str = ""
    project_name: str = ""
    activity_name: str = ""
    # §4: igual que en la importación de registros — lo que decía el archivo
    # cuando la tabla de sinónimos lo tradujo.
    activity_original: str = ""
    status: str = ""
    status_label: str = ""
    estimated_hours: Optional[Decimal] = None
    # Lo que había antes, cuando la fila actualiza una estimación (H-D97).
    previous_hours: Optional[Decimal] = None
    # Qué se crearía por culpa de esta fila.
    crea_cliente: bool = False
    crea_proyecto: bool = False
    crea_actividad: bool = False


class ProyectoImportado(BaseModel):
    """Un proyecto del archivo, con sus actividades juntas (H-D96, H-D99).

    `total_hours` es **lo que suma el proyecto entero** en el archivo, que es la
    cifra con la que se comprueba de un vistazo si el Excel está bien.
    """
    client_name: str = ""
    project_name: str = ""
    status: str = ""
    status_label: str = ""
    es_nuevo: bool = False
    cambia_de_estado: bool = False
    status_anterior_label: str = ""
    actividades: int = 0
    total_hours: Decimal = Decimal("0")
    filas: List[FilaProyectoImportacion] = []


class VistaPreviaProyectos(BaseModel):
    """Lo que se verá ANTES de escribir nada (H-D99). Nada de esto toca la base."""
    sheet: str = ""
    sheets: List[str] = []
    total_filas: int = 0
    proyectos: List[ProyectoImportado] = []
    invalidas: List[FilaProyectoImportacion] = []
    proyectos_nuevos: int = 0
    proyectos_actualizados: int = 0
    estimaciones_nuevas: int = 0
    estimaciones_actualizadas: int = 0
    estimaciones_iguales: int = 0
    clientes_a_crear: List[str] = []
    actividades_a_crear: List[str] = []
    actividades_nuevas: List[ActividadNueva] = []
    total_horas: Decimal = Decimal("0")


class ResumenProyectos(BaseModel):
    """Lo que se escribió."""
    proyectos_creados: List[ProyectoCreado] = []
    proyectos_actualizados: int = 0
    estimaciones_creadas: int = 0
    estimaciones_actualizadas: int = 0
    estimaciones_iguales: int = 0
    estados_cambiados: int = 0
    clientes_creados: List[str] = []
    actividades_creadas: List[str] = []
    actividades_nuevas: List[ActividadNueva] = []
    omitidas: int = 0
    total_horas: Decimal = Decimal("0")


# ===================== BORRAR UN PROYECTO (CARGA REAL, §2) =====================

class ProyectoBorrado(BaseModel):
    """Lo que se llevó por delante el borrado de un proyecto.

    Se devuelven las tres cuentas —estimaciones, historial de estimaciones e
    historial de estados— en vez de un «borrado: sí». Las tres tablas cuelgan
    del proyecto con `ON DELETE CASCADE`, así que se van solas; decir cuántas
    filas eran es la única forma de comprobar desde fuera que se fueron.
    """
    id: UUID
    name: str
    client_name: str = ""
    status: str = ""
    estimaciones_borradas: int = 0
    historial_estimaciones_borrado: int = 0
    historial_estados_borrado: int = 0
    performed_by: str = ""
    performed_at: datetime
