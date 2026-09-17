"""Modelo de datos del MÓDULO DE HORAS (ETAPA H1, especificación de horas v1.0 §1).

Las siete tablas son **nuevas**: `Base.metadata.create_all` las crea al arrancar,
sin ALTER y sin Alembic (regla 10, H-D1). Ninguna tabla del módulo de análisis se
toca; la única que se comparte es `clients`, y se comparte **tal como está**
(H-D2).

`time_entries` se define ya, entera, aunque el registro de horas no llegue hasta
H2: así el esquema no hay que alterarlo después, que es justo lo que este
proyecto no puede hacer cómodamente.

Convenciones tomadas de `client.py`, que es el módulo más parecido: UUID como
clave, `created_at`/`updated_at` con `datetime.utcnow`, y las restricciones en
`__table_args__`.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


def normalizar(texto: str) -> str:
    """Nombre comparable: sin tildes, sin espacios de más, sin distinguir mayúsculas.

    Es la regla que pide §6.2.3 para no duplicar un cliente o una actividad por una
    diferencia de escritura, y la que usa el catálogo de actividades (H-D3). Vive
    aquí —junto a las columnas que la guardan— para que el backend y la importación
    de H4 no acaben con dos versiones distintas de "el mismo nombre".
    """
    import unicodedata
    if not texto:
        return ""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.split()).lower()


class Activity(Base):
    """Catálogo GLOBAL de actividades (§1.2, H-D3).

    Una actividad con horas registradas no se borra: se desactiva (H-D4). Por eso
    `is_active` en vez de un borrado lógico con fecha.
    """
    __tablename__ = "activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    # El nombre normalizado es el que lleva el UNIQUE: "Planeación" y "planeacion"
    # son la misma actividad.
    name_normalized = Column(String(150), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(Base):
    """Proyecto de un cliente (§3).

    `client_id` apunta a la tabla `clients` del módulo de análisis, sin cambiarla
    (H-D2). El nombre es único POR CLIENTE, no globalmente: dos clientes pueden
    tener un proyecto con el mismo nombre.
    """
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    name_normalized = Column(String(200), nullable=False)
    # 'activo' | 'cerrado'. Un proyecto cerrado no admite registros nuevos pero se
    # sigue consultando (§3).
    status = Column(String(20), default="activo", nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("client_id", "name_normalized", name="uq_project_cliente_nombre"),
        CheckConstraint("status in ('activo','cerrado')", name="ck_project_status"),
    )


class ProjectActivity(Base):
    """Horas estimadas de UNA actividad dentro de UN proyecto (§3)."""
    __tablename__ = "project_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activities.id"),
                         nullable=False, index=True)
    # Numeric, no Float: son horas y se suman. Un float acumula error y la
    # comparación "consumido vs estimado" acabaria mintiendo por decimales.
    estimated_hours = Column(Numeric(8, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "activity_id", name="uq_proyecto_actividad"),
        CheckConstraint("estimated_hours > 0", name="ck_estimacion_positiva"),
    )


class ProjectActivityChange(Base):
    """Historial de las estimaciones (§3, H-D11).

    Se escribe SIEMPRE que cambia una estimación: valor anterior, nuevo, autor y
    fecha. Nunca se pisa una estimación sin dejar rastro.

    `previous_hours` admite NULL: la primera fila de una actividad recién añadida
    al proyecto no tiene valor anterior.
    """
    __tablename__ = "project_activity_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activities.id"), nullable=False)
    previous_hours = Column(Numeric(8, 2), nullable=True)
    new_hours = Column(Numeric(8, 2), nullable=True)
    # 'alta' | 'cambio' | 'baja' — para poder leer el historial sin adivinar.
    change_type = Column(String(20), nullable=False, default="cambio")
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint("change_type in ('alta','cambio','baja')", name="ck_cambio_tipo"),
    )


class TimeEntry(Base):
    """El registro de horas (§1.1).

    Se crea ya, aunque no se use hasta H2: alterar una tabla existente en este
    proyecto exige un ALTER a mano (regla 10), y eso es justo lo que se evita
    definiéndola entera desde el principio.
    """
    __tablename__ = "time_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # §6.2.2: el `Id` del archivo importado. Único, para que subir dos veces el
    # mismo archivo actualice en vez de duplicar. NULL en los registros manuales,
    # y en Postgres varios NULL no chocan con el UNIQUE.
    external_id = Column(String(100), nullable=True, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Distinto de user_id cuando lo registra un administrador por otra persona (§4.2.1).
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    date = Column(Date, nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activities.id"), nullable=False, index=True)
    hours = Column(Numeric(6, 2), nullable=False)
    billable = Column(Boolean, nullable=False)
    overtime = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    # 'manual' | 'import'
    source = Column(String(20), default="manual", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # La consulta de cada semana filtra por persona y rango de fechas: es el
        # indice que sostiene la pantalla de registro.
        Index("ix_time_entries_user_date", "user_id", "date"),
        CheckConstraint("hours > 0", name="ck_horas_positivas"),
        # H-D8: pasos de 0,25. Se valida tambien en backend y frontend; aqui queda
        # como ultima red, para que ni una importacion ni un script metan 0,3.
        CheckConstraint("(hours * 100)::int % 25 = 0", name="ck_horas_cuarto"),
        CheckConstraint("source in ('manual','import')", name="ck_origen"),
    )


class WorkCalendar(Base):
    """La jornada esperada por día de la semana (H-D5).

    Una fila por día: lunes 8,5 … viernes 8,0, sábado y domingo 0. Es tabla y no
    constante para que cambiar la jornada no exija tocar código.
    """
    __tablename__ = "work_calendar"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 0 = lunes … 6 = domingo (el mismo criterio que `date.weekday()` de Python,
    # para no traducir en cada consulta).
    weekday = Column(Integer, nullable=False, unique=True)
    expected_hours = Column(Numeric(4, 2), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("weekday between 0 and 6", name="ck_dia_semana"),
        CheckConstraint("expected_hours >= 0", name="ck_jornada_no_negativa"),
    )


class Holiday(Base):
    """Festivos (H-D5) y ausencias por usuario (§1, `work_calendar`).

    `user_id` NULL = festivo nacional, que aplica a todos. Con `user_id` = una
    ausencia de esa persona. Los dos casos se consultan igual cuando hay que
    decidir si un día se reclama como incompleto (§4.2.7), así que comparten
    tabla en vez de duplicar la lógica.

    Los festivos se cargan de una **lista literal por fecha**, no calculados: un
    algoritmo de Ley Emiliani se equivoca en silencio y una lista se revisa
    (decisión de Fredy).
    """
    __tablename__ = "holidays"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    # NULL = festivo nacional; con valor = ausencia de esa persona.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=True, index=True)
    # 'festivo' | 'ausencia'
    kind = Column(String(20), default="festivo", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Un festivo nacional no se puede duplicar en la misma fecha. Con user_id
        # NULL, Postgres no aplica el UNIQUE, asi que el indice parcial de abajo
        # es el que de verdad protege los nacionales.
        UniqueConstraint("date", "user_id", name="uq_festivo_fecha_usuario"),
        Index("ux_festivo_nacional", "date", unique=True,
              postgresql_where=Column("user_id").is_(None)),
        CheckConstraint("kind in ('festivo','ausencia')", name="ck_tipo_dia"),
    )
