"""Entidades del dominio.

Todas inmutables (``frozen=True``): el dominio transforma, no muta. Son
estructuras puras sin dependencia de la base de datos ni del framework web;
la capa de infraestructura las construye a partir de filas y viceversa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime

from .enums import (
    Actor,
    ExceptionReason,
    LoadType,
    Modality,
    MuscleRole,
    SessionOrigin,
    SessionStatus,
    Strategy,
)

# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MuscleGroup:
    slug: str
    name: str
    region: str
    body_view: str
    #: Identificador del trazo en el SVG del mapa corporal.
    svg_key: str
    display_order: int = 0


@dataclass(frozen=True, slots=True)
class MuscleLink:
    """Participación de un músculo en un ejercicio."""

    muscle_slug: str
    role: MuscleRole


@dataclass(frozen=True, slots=True)
class Exercise:
    slug: str
    name: str
    modality: Modality
    load_type: LoadType
    muscles: tuple[MuscleLink, ...] = ()
    #: Fracción del peso corporal movilizada. Aproximación editable, no física.
    load_factor: float = 0.0
    is_unilateral: bool = False
    equipment: str | None = None
    default_rule_slug: str | None = None
    next_variant_slug: str | None = None
    default_rest_seconds: int = 90

    @property
    def uses_bodyweight(self) -> bool:
        return self.load_type in (LoadType.CORPORAL, LoadType.ASISTIDA)


# --------------------------------------------------------------------------
# Planificado
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlannedSet:
    """Una serie planificada. 3x15 son tres instancias de esta clase."""

    set_no: int
    target_reps: int | None = None
    target_reps_max: int | None = None
    target_weight_kg: float | None = None
    target_time_s: int | None = None
    target_rir: int | None = None
    is_warmup: bool = False
    #: Sin objetivo numérico: se repite hasta el fallo. Poner una estimación
    #: en `target_reps` sería inventarse el plan (invariante 5).
    to_failure: bool = False


@dataclass(frozen=True, slots=True)
class PlannedExercise:
    exercise_slug: str
    position: int
    sets: tuple[PlannedSet, ...]
    rest_seconds: int | None = None
    rule_slug: str | None = None
    notes: str | None = None

    @property
    def work_sets(self) -> tuple[PlannedSet, ...]:
        """Series efectivas: el calentamiento no cuenta para progresión ni volumen."""
        return tuple(s for s in self.sets if not s.is_warmup)


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    weekday: int  # 0 = lunes … 6 = domingo
    routine_id: int
    active_from: Date
    active_to: Date | None = None

    def covers(self, day: Date) -> bool:
        if day < self.active_from:
            return False
        return self.active_to is None or day <= self.active_to


@dataclass(frozen=True, slots=True)
class ScheduleException:
    date: Date
    reason: ExceptionReason
    routine_id: int | None = None
    note: str | None = None


# --------------------------------------------------------------------------
# Histórico
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PerformedSet:
    set_no: int
    reps: int | None = None
    weight_kg: float | None = None
    time_s: int | None = None
    rir: int | None = None
    completed: bool = True
    is_warmup: bool = False


@dataclass(frozen=True, slots=True)
class PerformedExercise:
    exercise_slug: str
    position: int
    sets: tuple[PerformedSet, ...]
    notes: str | None = None

    @property
    def work_sets(self) -> tuple[PerformedSet, ...]:
        return tuple(s for s in self.sets if not s.is_warmup)


@dataclass(frozen=True, slots=True)
class WorkoutSession:
    date: Date
    status: SessionStatus
    origin: SessionOrigin
    exercises: tuple[PerformedExercise, ...] = ()
    routine_version_id: int | None = None
    perceived_effort: int | None = None
    duration_min: int | None = None
    notes: str | None = None
    logged_at: datetime | None = None
    actor: Actor = Actor.USUARIO
    id: int | None = None

    @property
    def is_retroactive(self) -> bool:
        """True si se registró en un día distinto al del entrenamiento."""
        return self.logged_at is not None and self.logged_at.date() != self.date

    def find(self, exercise_slug: str) -> PerformedExercise | None:
        for ex in self.exercises:
            if ex.exercise_slug == exercise_slug:
                return ex
        return None


# --------------------------------------------------------------------------
# Progresión
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Guards:
    """Límites que ninguna propuesta de progresión puede sobrepasar.

    Existen para que el sistema no aumente la dificultad de forma
    irresponsable. Son duros: el motor no los interpreta, los obedece.
    """

    #: Días mínimos entre dos progresiones del mismo ejercicio.
    cooldown_days: int = 7
    #: Incremento máximo de carga por progresión, como fracción (0.10 = 10 %).
    max_load_increase_pct: float = 0.10
    #: Sesiones registradas mínimas antes de proponer nada.
    min_sessions: int = 2
    #: Sesiones consecutivas que deben cumplir el objetivo para disparar.
    required_successful_sessions: int = 2
    #: Regresiones consecutivas tras las que se sugiere descarga.
    deload_after_regressions: int = 2
    #: Techos absolutos. None = sin techo.
    max_reps: int | None = None
    max_sets: int | None = None
    max_time_s: int | None = None
    max_weight_kg: float | None = None


@dataclass(frozen=True, slots=True)
class ProgressionRule:
    slug: str
    name: str
    strategy: Strategy
    params: dict[str, float | int] = field(default_factory=dict)
    guards: Guards = field(default_factory=Guards)
