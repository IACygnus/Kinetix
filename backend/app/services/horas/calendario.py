"""La jornada y los días pendientes (ETAPA H2, especificación de horas §4.2.6 y §4.2.7).

**Una sola definición.** La misma cuenta la necesitan `/time/week` y
`/time/pending-days`, y escribirla dos veces acabaría discrepando en algún borde
—un festivo en viernes, un día con solo horas extra— sin que nadie lo note. Es el
mismo criterio que llevó a `services/ai/criterios.py` en la Etapa 5b, donde el
texto de la IA y la tabla de veredictos resolvían el umbral por separado y podían
contradecirse.

**La pantalla no recalcula nada**: recibe por día lo esperado, lo ordinario, lo
extra, si es festivo o ausencia, si está incompleto y por cuánto.

Las reglas viven aquí, juntas:

  1. un día por debajo de su jornada está incompleto, y falta la diferencia;
  2. un día con horas extra **nunca** se marca incompleto (H-D17);
  3. festivos y ausencias **no se reclaman** (§4.2.7);
  4. un día que todavía no ha llegado tampoco se reclama (ETAPA H2b).

La cuarta la tenía `dias_pendientes` para su lista, pero no la tenía el día en sí.
Con la vista semanal casi no se notaba; con el calendario del mes se nota mucho,
porque pintaría en rojo todo lo que queda de mes. La regla sube al día, que es
donde estaban las otras tres, y así el calendario, la semana y la lista de
pendientes no pueden discrepar.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

CERO = Decimal("0")


@dataclass
class DiaDelCalendario:
    """Un día, ya resuelto. Es lo que viaja a la pantalla."""
    fecha: date
    # Horas que se esperan ese día según `work_calendar` (0 en fin de semana).
    esperadas: Decimal
    ordinarias: Decimal = CERO
    extra: Decimal = CERO
    es_festivo: bool = False
    es_ausencia: bool = False
    motivo_no_laborable: str = ""
    # Hasta dónde ha llegado el tiempo. `None` = no se recorta el futuro, que es
    # como se comportaba H2; los endpoints pasan el día de hoy.
    hoy: Optional[date] = None

    @property
    def total(self) -> Decimal:
        return self.ordinarias + self.extra

    @property
    def no_laborable(self) -> bool:
        """Fin de semana, festivo o ausencia: no se reclama nunca."""
        return self.esperadas <= 0 or self.es_festivo or self.es_ausencia

    @property
    def futuro(self) -> bool:
        """Un día que todavía no ha llegado. Hoy NO lo es: la jornada de hoy se
        registra hoy, y el panel de pendientes ya lo contaba así."""
        return self.hoy is not None and self.fecha > self.hoy

    @property
    def se_reclaman(self) -> Decimal:
        """Las horas que de verdad se esperan ese día.

        Un festivo, una ausencia o un fin de semana no esperan ninguna (§4.2.7):
        `esperadas` guarda la jornada del calendario laboral —que sigue siendo
        útil para saber qué jornada le tocaba—, pero lo que se suma y lo que se
        enseña es esto.
        """
        return CERO if self.no_laborable else self.esperadas

    @property
    def incompleto(self) -> bool:
        """Las cuatro reglas, en el orden en que se aplican.

        El orden importa: primero se descarta lo que no se reclama —ni por
        festivo ni por no haber llegado todavía—, después las extras, y solo
        entonces se compara contra la jornada.
        """
        if self.no_laborable:
            return False
        if self.futuro:
            return False
        if self.extra > 0:          # H-D17
            return False
        return self.ordinarias < self.esperadas

    @property
    def faltan(self) -> Decimal:
        return (self.esperadas - self.ordinarias) if self.incompleto else CERO


def jornada_de(fecha: date, calendario: Dict[int, Decimal]) -> Decimal:
    """Horas esperadas ese día. `weekday()` da 0 = lunes, que es el mismo
    criterio con el que H1 sembró `work_calendar`: no hay que traducir."""
    return Decimal(str(calendario.get(fecha.weekday(), 0)))


def dias_del_rango(desde: date, hasta: date) -> List[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def semana_de(fecha: date) -> tuple:
    """El lunes y el domingo de la semana que contiene esa fecha."""
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)


def construir_dias(
    desde: date,
    hasta: date,
    calendario: Dict[int, Decimal],
    horas_por_dia: Dict[date, Dict[str, Decimal]],
    no_laborables: Dict[date, tuple],
    hoy: Optional[date] = None,
) -> List[DiaDelCalendario]:
    """Resuelve cada día del rango.

    `horas_por_dia`  : {fecha: {"ordinarias": …, "extra": …}}, lo que hay registrado.
    `no_laborables`  : {fecha: (nombre, es_ausencia)}, festivos y ausencias juntos —
                       H1 los puso en la misma tabla porque aquí se usan igual.
    `hoy`            : recorta el futuro. Sin él nada se recorta, que es lo que
                       quieren los tests de las otras tres reglas.
    """
    salida = []
    for f in dias_del_rango(desde, hasta):
        registrado = horas_por_dia.get(f, {})
        nombre, es_ausencia = no_laborables.get(f, ("", False))
        salida.append(DiaDelCalendario(
            fecha=f,
            esperadas=jornada_de(f, calendario),
            ordinarias=Decimal(str(registrado.get("ordinarias", 0))),
            extra=Decimal(str(registrado.get("extra", 0))),
            es_festivo=bool(nombre) and not es_ausencia,
            es_ausencia=es_ausencia,
            motivo_no_laborable=nombre,
            hoy=hoy,
        ))
    return salida


def dias_pendientes(dias: List[DiaDelCalendario],
                    hasta_hoy: Optional[date] = None) -> List[DiaDelCalendario]:
    """Los días que hay que reclamar (H-D18).

    `hasta_hoy` recorta el futuro: un día que todavía no ha llegado no está
    pendiente, está por venir. Sin él, abrir el panel un lunes listaría el resto
    de la semana como si fuera una deuda.
    """
    tope = hasta_hoy or date.today()
    return [d for d in dias if d.incompleto and d.fecha <= tope]
