"""Modelos de lectura.

Lo que los casos de uso devuelven hacia fuera. Son distintos de las entidades
de ``domain.models`` a propósito: una vista compone datos de varias tablas y
lleva identificadores de persistencia, cosas que el dominio puro no conoce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime

from ..domain.compliance.day_state import DayVerdict
from ..domain.enums import DayState, ProgressionOutcome, SessionOrigin, SessionStatus, Tier
from ..domain.models import PerformedExercise, PlannedExercise, PlannedSet
from ..domain.ranking.balance import BalanceCheck
from ..domain.ranking.v1 import MuscleScore


@dataclass(frozen=True, slots=True)
class RoutineSummary:
    id: int
    name: str
    status: str
    version_no: int
    exercise_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RoutineDetail:
    id: int
    name: str
    status: str
    version_id: int
    version_no: int
    created_at: datetime
    exercises: tuple[PlannedExercise, ...] = ()
    note: str | None = None


@dataclass(frozen=True, slots=True)
class SessionDetail:
    id: int
    date: Date
    status: SessionStatus
    origin: SessionOrigin
    exercises: tuple[PerformedExercise, ...] = ()
    routine_id: int | None = None
    routine_name: str | None = None
    routine_version_id: int | None = None
    routine_version_no: int | None = None
    perceived_effort: int | None = None
    duration_min: int | None = None
    notes: str | None = None
    logged_at: datetime | None = None

    @property
    def is_retroactive(self) -> bool:
        return self.logged_at is not None and self.logged_at.date() != self.date


@dataclass(frozen=True, slots=True)
class DayView:
    """Todo lo que hace falta para pintar un día: lo previsto y lo ocurrido."""

    date: Date
    state: DayState
    reason: str
    planned: RoutineDetail | None = None
    session: SessionDetail | None = None
    exception_reason: str | None = None

    @property
    def can_log(self) -> bool:
        """Si tiene sentido ofrecer el botón de registrar en este día."""
        return self.session is None


@dataclass(frozen=True, slots=True)
class CalendarDay:
    """Un día del calendario mensual.

    Envuelve el veredicto del dominio en lugar de copiar sus campos, para que
    el cálculo de adherencia siga trabajando sobre `DayVerdict` sin duplicar la
    regla de qué estados computan.
    """

    verdict: DayVerdict
    routine_id: int | None = None
    routine_name: str | None = None
    session_id: int | None = None

    @property
    def date(self) -> Date:
        return self.verdict.date

    @property
    def state(self) -> DayState:
        return self.verdict.state

    @property
    def reason(self) -> str:
        return self.verdict.reason


@dataclass(frozen=True, slots=True)
class PendingDay:
    """Día programado y aún sin registrar, dentro de la ventana de gracia."""

    date: Date
    routine_id: int
    routine_name: str
    days_left: int


@dataclass(frozen=True, slots=True)
class WeekPlan:
    """Asignación de rutinas a los siete días, vigente en una fecha."""

    effective_on: Date
    #: weekday (0 = lunes) → id de rutina, o None si es día de descanso.
    days: dict[int, int | None] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Progresión
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProgressionItem:
    """Veredicto del motor para un ejercicio concreto de una rutina.

    Lleva el motivo siempre, no solo cuando se puede progresar: un
    ``UNDETERMINED`` sin explicación sería exactamente el silencio que el
    proyecto se prohíbe.
    """

    exercise_slug: str
    exercise_name: str
    outcome: ProgressionOutcome
    reason: str
    #: Regla aplicada, ya resuelta: la de la rutina o, si no la hay, la que el
    #: catálogo declara por defecto para ese ejercicio.
    rule_slug: str | None = None
    rule_inherited: bool = False
    current: str = ""
    proposed: str | None = None
    proposed_sets: tuple[PlannedSet, ...] = ()
    #: Solo en la estrategia 'variante': el ejercicio pasa a ser otro.
    next_exercise_slug: str | None = None
    next_exercise_name: str | None = None
    last_progression: Date | None = None

    @property
    def is_applicable(self) -> bool:
        """Si existe una propuesta que el usuario pueda aplicar."""
        return self.outcome in (
            ProgressionOutcome.READY,
            ProgressionOutcome.DELOAD_SUGGESTED,
        ) and bool(self.proposed_sets or self.next_exercise_slug)


@dataclass(frozen=True, slots=True)
class RoutineProgression:
    """Evaluación completa de una rutina, ejercicio a ejercicio."""

    routine_id: int
    routine_name: str
    version_id: int
    version_no: int
    items: tuple[ProgressionItem, ...] = ()

    @property
    def ready(self) -> int:
        return sum(1 for i in self.items if i.outcome is ProgressionOutcome.READY)

    @property
    def deload(self) -> int:
        return sum(1 for i in self.items if i.outcome is ProgressionOutcome.DELOAD_SUGGESTED)


@dataclass(frozen=True, slots=True)
class RoutineReadiness:
    """Resumen por rutina para la pantalla «Hoy»."""

    routine_id: int
    routine_name: str
    ready: int
    deload: int


@dataclass(frozen=True, slots=True)
class ProgressionEventView:
    """Una progresión aplicada. Es historia: no se borra, se revierte."""

    id: int
    exercise_slug: str
    exercise_name: str
    routine_id: int
    routine_name: str
    rule_slug: str
    rationale: str
    applied_at: datetime
    actor: str
    before: dict
    after: dict
    from_version_no: int | None = None
    to_version_no: int | None = None
    reverted: bool = False
    #: True si este evento es en sí mismo la reversión de otro.
    is_reversal: bool = False


@dataclass(frozen=True, slots=True)
class ProgressionApplied:
    """Resultado de aplicar una o varias progresiones a la vez.

    Un solo salto de versión para todo el lote, y un evento por ejercicio: así
    la rutina no acumula una versión por cada serie que sube.
    """

    routine: RoutineDetail
    events: tuple[ProgressionEventView, ...] = ()


# --------------------------------------------------------------------------
# Ranking muscular
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExerciseStimulus:
    """Lo que un ejercicio aportó en una sesión, ya en kg equivalentes."""

    date: Date
    exercise_slug: str
    volume_kg: float
    e1rm_kg: float | None
    sets: int


@dataclass(frozen=True, slots=True)
class StimulusData:
    """Historial ya traducido a estímulo, con lo que quedó fuera y por qué."""

    by_exercise: tuple[ExerciseStimulus, ...] = ()
    #: Series efectivas que no pudieron convertirse a kg equivalentes.
    skipped_sets: int = 0
    #: Motivos distintos, para poder decirle al usuario qué le falta registrar.
    skipped_reasons: tuple[str, ...] = ()
    bodyweight_missing: bool = False


@dataclass(frozen=True, slots=True)
class MuscleUsage:
    """Cuánto y cuándo se ha trabajado un músculo en una ventana."""

    volume_kg: float
    sessions: int
    sessions_per_week: float
    #: Ejercicios que lo estimularon, del que más volumen aporta al que menos.
    top_exercises: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class ExerciseProgress:
    """Evolución de un ejercicio: lo que hace falta para dibujar una línea."""

    exercise_slug: str
    points: tuple[ExerciseStimulus, ...] = ()
    best_e1rm_kg: float | None = None
    best_on: Date | None = None

    @property
    def has_data(self) -> bool:
        return bool(self.points)


@dataclass(frozen=True, slots=True)
class MuscleRankingEntry:
    """Un músculo del mapa corporal con su puntuación.

    Envuelve el ``MuscleScore`` del dominio en lugar de copiar sus campos: la
    fórmula puede añadir factores sin que haya que tocar esta capa.
    """

    muscle_slug: str
    name: str
    region: str
    body_view: str
    svg_key: str
    display_order: int
    score: MuscleScore

    @property
    def tier(self) -> Tier:
        return self.score.tier

    @property
    def development(self) -> float | None:
        return self.score.development if self.score.has_data else None


@dataclass(frozen=True, slots=True)
class RankingView:
    """El mapa corporal completo, con lo que hace falta para no mentir."""

    today: Date
    formula_version: str
    bodyweight_kg: float | None
    entries: tuple[MuscleRankingEntry, ...] = ()
    balance: tuple[BalanceCheck, ...] = ()
    #: Qué impide medir mejor: sin peso corporal, series sin datos, etc.
    notes: tuple[str, ...] = ()
    #: La calibración es provisional mientras D9 siga abierta, y la interfaz
    #: tiene que decirlo en vez de presentar el rango como un veredicto.
    provisional: bool = True

    @property
    def measured(self) -> int:
        return sum(1 for e in self.entries if e.score.has_data)


@dataclass(frozen=True, slots=True)
class ExerciseContribution:
    """Qué aporta un ejercicio concreto al músculo que se está mirando."""

    exercise_slug: str
    exercise_name: str
    role: str
    role_factor: float
    volume_kg: float
    best_e1rm_kg: float | None = None
    last_date: Date | None = None


@dataclass(frozen=True, slots=True)
class ScorePoint:
    """Un punto del histórico del rango, tomado de un snapshot."""

    date: Date
    development: float
    activity: float
    tier: Tier


@dataclass(frozen=True, slots=True)
class MuscleDetail:
    """Ficha de un músculo. Explicabilidad obligatoria (ADR-0003)."""

    entry: MuscleRankingEntry
    next_tier: Tier | None = None
    points_to_next_tier: float | None = None
    recent: MuscleUsage | None = None
    quarter: MuscleUsage | None = None
    exercises: tuple[ExerciseContribution, ...] = ()
    history: tuple[ScorePoint, ...] = ()
