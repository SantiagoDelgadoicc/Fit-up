"""Contrato HTTP.

Estos modelos son el **borde** de la aplicación, no el dominio. Se mantienen
separados a propósito: el esquema de la API puede evolucionar sin arrastrar al
dominio, y sobre todo generan el OpenAPI del que salen los tipos del frontend
y la documentación que consumirá el agente de IA (ADR-0002, ADR-0004).
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..domain.enums import DayState, ProgressionOutcome, SessionOrigin, SessionStatus


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


class MuscleOut(Model):
    slug: str
    name: str
    region: str
    body_view: str
    svg_key: str


class MuscleLinkOut(Model):
    muscle_slug: str
    role: str


class ExerciseOut(Model):
    slug: str
    name: str
    modality: str
    load_type: str
    load_factor: float
    is_unilateral: bool
    equipment: str | None = None
    default_rule_slug: str | None = None
    next_variant_slug: str | None = None
    default_rest_seconds: int
    muscles: list[MuscleLinkOut] = []


class RuleOut(Model):
    slug: str
    name: str
    strategy: str
    params: dict = {}


# --------------------------------------------------------------------------
# Series
# --------------------------------------------------------------------------


class PlannedSetIn(Model):
    set_no: int = Field(ge=1)
    target_reps: int | None = Field(default=None, gt=0)
    target_reps_max: int | None = Field(default=None, gt=0)
    target_weight_kg: float | None = Field(default=None, ge=0)
    target_time_s: int | None = Field(default=None, gt=0)
    target_rir: int | None = Field(default=None, ge=0, le=10)
    is_warmup: bool = False


class PlannedSetOut(PlannedSetIn):
    pass


class SetSpec(Model):
    """Prescripción compacta: la UI dice "3x15" y el backend genera las filas."""

    count: int = Field(ge=1, le=20)
    reps: int | None = Field(default=None, gt=0)
    reps_max: int | None = Field(default=None, gt=0)
    weight_kg: float | None = Field(default=None, ge=0)
    time_s: int | None = Field(default=None, gt=0)
    rir: int | None = Field(default=None, ge=0, le=10)
    warmup: int = Field(default=0, ge=0, le=5)


class PlannedExerciseIn(Model):
    exercise_slug: str
    rest_seconds: int | None = Field(default=None, ge=0)
    rule_slug: str | None = None
    notes: str | None = None
    #: Series explícitas, o una prescripción compacta que las genera.
    sets: list[PlannedSetIn] | None = None
    spec: SetSpec | None = None


class PlannedExerciseOut(Model):
    exercise_slug: str
    position: int
    rest_seconds: int | None = None
    rule_slug: str | None = None
    notes: str | None = None
    sets: list[PlannedSetOut]


# --------------------------------------------------------------------------
# Rutinas
# --------------------------------------------------------------------------


class RoutineIn(Model):
    name: str = Field(min_length=1, max_length=120)
    exercises: list[PlannedExerciseIn]
    note: str | None = None


class RoutineUpdate(Model):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    exercises: list[PlannedExerciseIn]
    note: str | None = None


class RoutineSummaryOut(Model):
    id: int
    name: str
    status: str
    version_no: int
    exercise_count: int
    created_at: datetime


class RoutineOut(Model):
    id: int
    name: str
    status: str
    version_id: int
    version_no: int
    created_at: datetime
    note: str | None = None
    exercises: list[PlannedExerciseOut]


# --------------------------------------------------------------------------
# Semana y excepciones
# --------------------------------------------------------------------------


class WeekIn(Model):
    #: weekday (0 = lunes) → id de rutina, o null para descanso.
    days: dict[int, int | None]
    effective_from: Date | None = None


class WeekOut(Model):
    effective_on: Date
    days: dict[int, int | None]
    names: dict[int, str]


class ExceptionIn(Model):
    reason: str
    routine_id: int | None = None
    note: str | None = None


# --------------------------------------------------------------------------
# Sesiones
# --------------------------------------------------------------------------


class PerformedSetIn(Model):
    set_no: int = Field(ge=1)
    reps: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    time_s: int | None = Field(default=None, ge=0)
    rir: int | None = Field(default=None, ge=0, le=10)
    completed: bool = True
    is_warmup: bool = False


class PerformedSetOut(PerformedSetIn):
    pass


class PerformedExerciseIn(Model):
    exercise_slug: str
    notes: str | None = None
    sets: list[PerformedSetIn]


class PerformedExerciseOut(Model):
    exercise_slug: str
    position: int
    notes: str | None = None
    sets: list[PerformedSetOut]


class LogAsPlannedIn(Model):
    """«Hice esta rutina»: el registro de un toque."""

    date: Date
    status: SessionStatus = SessionStatus.COMPLETED
    perceived_effort: int | None = Field(default=None, ge=1, le=10)
    duration_min: int | None = Field(default=None, gt=0)
    notes: str | None = None


class LogSessionIn(Model):
    date: Date
    exercises: list[PerformedExerciseIn]
    status: SessionStatus = SessionStatus.COMPLETED
    routine_id: int | None = None
    perceived_effort: int | None = Field(default=None, ge=1, le=10)
    duration_min: int | None = Field(default=None, gt=0)
    notes: str | None = None


class SkipDayIn(Model):
    date: Date
    notes: str | None = None


class SessionOut(Model):
    id: int
    date: Date
    status: SessionStatus
    origin: SessionOrigin
    routine_id: int | None = None
    routine_name: str | None = None
    routine_version_no: int | None = None
    perceived_effort: int | None = None
    duration_min: int | None = None
    notes: str | None = None
    logged_at: datetime | None = None
    is_retroactive: bool = False
    exercises: list[PerformedExerciseOut]


# --------------------------------------------------------------------------
# Día y calendario
# --------------------------------------------------------------------------


class DayOut(Model):
    date: Date
    state: DayState
    reason: str
    can_log: bool
    planned: RoutineOut | None = None
    session: SessionOut | None = None
    exception_reason: str | None = None


class DayStateOut(Model):
    date: Date
    state: DayState
    reason: str
    #: Lo que se entrenó ese día, o lo que estaba programado si no se entrenó.
    routine_name: str | None = None
    routine_id: int | None = None
    session_id: int | None = None


class CalendarOut(Model):
    start: Date
    end: Date
    days: list[DayStateOut]
    #: ``None`` cuando ningún día computa todavía. Un 0 % sería mentira.
    adherence: float | None = None


class PendingDayOut(Model):
    date: Date
    routine_id: int
    routine_name: str
    days_left: int


# --------------------------------------------------------------------------
# Ajustes y peso
# --------------------------------------------------------------------------


class BodyweightIn(Model):
    date: Date
    weight_kg: float = Field(gt=0, lt=500)


class BodyweightOut(Model):
    date: Date
    weight_kg: float


class SettingIn(Model):
    value: object


class ErrorOut(Model):
    detail: str


# --------------------------------------------------------------------------
# Progresión
# --------------------------------------------------------------------------


class ProgressionItemOut(Model):
    """Veredicto para un ejercicio.

    ``reason`` viaja siempre, también en ``undetermined``: un cliente que solo
    pintara los ``ready`` estaría ocultando justo lo que hay que decidir.
    """

    exercise_slug: str
    exercise_name: str
    outcome: ProgressionOutcome
    reason: str
    current: str
    applicable: bool
    rule_slug: str | None = None
    rule_inherited: bool = False
    proposed: str | None = None
    proposed_sets: list[PlannedSetOut] = []
    next_exercise_slug: str | None = None
    next_exercise_name: str | None = None
    last_progression: Date | None = None


class RoutineProgressionOut(Model):
    routine_id: int
    routine_name: str
    version_no: int
    ready: int
    deload: int
    items: list[ProgressionItemOut]


class RoutineReadinessOut(Model):
    routine_id: int
    routine_name: str
    ready: int
    deload: int


class ProgressionApplyIn(Model):
    #: Slugs de los ejercicios a progresar. El servidor recalcula *cuánto*.
    exercises: list[str] = Field(min_length=1)
    note: str | None = None


class ProgressionEventOut(Model):
    id: int
    exercise_slug: str
    exercise_name: str
    routine_id: int
    routine_name: str
    rule_slug: str
    rationale: str
    applied_at: datetime
    actor: str
    before_summary: str
    after_summary: str
    before_exercise_slug: str
    after_exercise_slug: str
    reverted: bool = False
    is_reversal: bool = False
    from_version_no: int | None = None
    to_version_no: int | None = None


class ProgressionAppliedOut(Model):
    routine: RoutineOut
    events: list[ProgressionEventOut]
