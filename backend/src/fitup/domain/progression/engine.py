"""Motor de sobrecarga progresiva.

Función pura: ``(historial, plan actual, regla, hoy) → veredicto``. Sin acceso
a base de datos y sin consultar el reloj, de modo que cada caso es
reproducible en un test.

Dos principios gobiernan este módulo:

1. **Propone, no aplica.** Devuelve un veredicto; escribir el nuevo plan es
   responsabilidad de la capa de aplicación, tras confirmación humana.
2. **No inventa.** Si no puede determinar con seguridad cómo progresar,
   devuelve ``UNDETERMINED`` con el motivo. Nunca rellena un hueco con una
   suposición.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date as Date
from enum import Enum, auto

from ..enums import ProgressionOutcome, Strategy
from ..models import Exercise, PerformedExercise, PlannedExercise, PlannedSet, ProgressionRule

EPSILON = 1e-6


@dataclass(frozen=True, slots=True)
class ExerciseHistoryEntry:
    """Una ejecución pasada del ejercicio. El historial se ordena de antigua a reciente."""

    date: Date
    performed: PerformedExercise


@dataclass(frozen=True, slots=True)
class ProgressionProposal:
    """Plan propuesto. Sustituye a las series actuales si el usuario acepta."""

    sets: tuple[PlannedSet, ...]
    summary: str
    #: Solo en la estrategia 'variante': el ejercicio pasa a ser otro.
    next_exercise_slug: str | None = None


@dataclass(frozen=True, slots=True)
class ProgressionAssessment:
    outcome: ProgressionOutcome
    reason: str
    proposal: ProgressionProposal | None = None

    @property
    def is_ready(self) -> bool:
        return self.outcome is ProgressionOutcome.READY


class _Check(Enum):
    MET = auto()
    NOT_MET = auto()
    INDETERMINATE = auto()


# --------------------------------------------------------------------------
# Descripción legible
# --------------------------------------------------------------------------


def describe_sets(sets: Sequence[PlannedSet]) -> str:
    """Resumen humano de un plan de series: ``3x15``, ``3x8 @ 40kg``, ``3x45s``."""
    work = [s for s in sets if not s.is_warmup]
    if not work:
        return "sin series"

    def signature(s: PlannedSet) -> tuple:
        return (s.target_reps, s.target_time_s, s.target_weight_kg)

    first = work[0]
    uniform = all(signature(s) == signature(first) for s in work)

    def one(s: PlannedSet) -> str:
        base = f"{s.target_time_s}s" if s.target_time_s is not None else str(s.target_reps)
        if s.target_weight_kg:
            base += f" @ {_fmt(s.target_weight_kg)}kg"
        return base

    if uniform:
        return f"{len(work)}x{one(first)}"
    return " / ".join(one(s) for s in work)


def _fmt(value: float) -> str:
    return f"{value:g}"


# --------------------------------------------------------------------------
# Evaluación de una sesión frente al objetivo
# --------------------------------------------------------------------------


def _session_meets_target(planned: PlannedExercise, performed: PerformedExercise) -> _Check:
    """¿Cumplió esta sesión el objetivo planificado?

    Exige completar todas las series efectivas alcanzando reps/tiempo/peso.
    Si además hay RIR registrado, un RIR de 0 (fallo muscular) bloquea la
    progresión: subir desde el fallo es exactamente la subida irresponsable
    que el sistema debe evitar.
    """
    targets = planned.work_sets
    if not targets:
        return _Check.INDETERMINATE

    done = {s.set_no: s for s in performed.work_sets}

    for target in targets:
        actual = done.get(target.set_no)
        if actual is None or not actual.completed:
            return _Check.NOT_MET

        if target.target_reps is not None:
            if actual.reps is None:
                return _Check.INDETERMINATE
            if actual.reps < target.target_reps:
                return _Check.NOT_MET

        if target.target_time_s is not None:
            if actual.time_s is None:
                return _Check.INDETERMINATE
            if actual.time_s < target.target_time_s:
                return _Check.NOT_MET

        if target.target_weight_kg is not None:
            if actual.weight_kg is None:
                return _Check.INDETERMINATE
            if actual.weight_kg + EPSILON < target.target_weight_kg:
                return _Check.NOT_MET

        if actual.rir is not None and actual.rir < 1:
            return _Check.NOT_MET

    return _Check.MET


def _performance_score(performed: PerformedExercise) -> float | None:
    """Puntuación ordinal para comparar dos sesiones del mismo ejercicio.

    No es una magnitud física: solo necesita ser monótona en repeticiones,
    tiempo y peso para responder "¿fue mejor o peor que la vez anterior?".
    El ``1 +`` hace que los ejercicios sin peso externo sigan siendo
    comparables en lugar de puntuar cero.
    """
    total = 0.0
    counted = False
    for s in performed.work_sets:
        if not s.completed:
            continue
        effort = s.reps if s.reps is not None else s.time_s
        if effort is None:
            continue
        total += effort * (1.0 + (s.weight_kg or 0.0))
        counted = True
    return total if counted else None


def _count_trailing_regressions(history: Sequence[ExerciseHistoryEntry]) -> int:
    """Sesiones consecutivas, de la más reciente hacia atrás, peores que la previa."""
    scores = [s for s in (_performance_score(h.performed) for h in history) if s is not None]
    regressions = 0
    for i in range(len(scores) - 1, 0, -1):
        if scores[i] < scores[i - 1] - EPSILON:
            regressions += 1
        else:
            break
    return regressions


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------


def evaluate(
    *,
    exercise: Exercise,
    planned: PlannedExercise,
    rule: ProgressionRule | None,
    history: Sequence[ExerciseHistoryEntry],
    today: Date,
    last_progression_date: Date | None = None,
) -> ProgressionAssessment:
    """Evalúa si corresponde progresar, y cómo.

    ``history`` debe llegar ordenado de la sesión más antigua a la más
    reciente y contener solo ejecuciones de ``exercise``.
    """
    if rule is None:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            f"'{exercise.name}' no tiene regla de progresión asignada",
        )

    if rule.strategy is Strategy.MANUAL:
        return ProgressionAssessment(
            ProgressionOutcome.NOT_YET,
            "Este ejercicio está configurado para progresar manualmente",
        )

    guards = rule.guards

    # --- Datos suficientes -------------------------------------------------
    if len(history) < guards.min_sessions:
        faltan = guards.min_sessions - len(history)
        return ProgressionAssessment(
            ProgressionOutcome.NOT_YET,
            f"Faltan {faltan} sesión(es) registrada(s) para poder evaluar la progresión",
        )

    # --- Cooldown ----------------------------------------------------------
    if last_progression_date is not None:
        elapsed = (today - last_progression_date).days
        if elapsed < guards.cooldown_days:
            return ProgressionAssessment(
                ProgressionOutcome.NOT_YET,
                f"Progresado hace {elapsed} día(s); el margen mínimo es de {guards.cooldown_days}",
            )

    # --- Regresión: antes de premiar, comprobar que no se está cayendo -----
    regressions = _count_trailing_regressions(history)
    if regressions >= guards.deload_after_regressions:
        return ProgressionAssessment(
            ProgressionOutcome.DELOAD_SUGGESTED,
            f"{regressions} sesiones consecutivas por debajo de la anterior: "
            "conviene una descarga antes que una subida",
            _deload_proposal(planned),
        )

    # --- Cumplimiento sostenido del objetivo -------------------------------
    needed = guards.required_successful_sessions
    recent = list(history)[-needed:]
    if len(recent) < needed:
        return ProgressionAssessment(
            ProgressionOutcome.NOT_YET,
            f"Se necesitan {needed} sesiones cumpliendo el objetivo",
        )

    for entry in recent:
        check = _session_meets_target(planned, entry.performed)
        if check is _Check.INDETERMINATE:
            return ProgressionAssessment(
                ProgressionOutcome.UNDETERMINED,
                f"La sesión del {entry.date.isoformat()} tiene series sin datos "
                "suficientes (repeticiones, tiempo o peso sin registrar)",
            )
        if check is _Check.NOT_MET:
            return ProgressionAssessment(
                ProgressionOutcome.NOT_YET,
                f"La sesión del {entry.date.isoformat()} no alcanzó el objetivo "
                f"({describe_sets(planned.sets)})",
            )

    # --- Todo en orden: construir la propuesta -----------------------------
    return _propose(exercise=exercise, planned=planned, rule=rule)


# --------------------------------------------------------------------------
# Construcción de propuestas por estrategia
# --------------------------------------------------------------------------


def _propose(
    *, exercise: Exercise, planned: PlannedExercise, rule: ProgressionRule
) -> ProgressionAssessment:
    strategy = rule.strategy
    if strategy is Strategy.REPS_LINEAL:
        return _propose_reps(planned, rule)
    if strategy is Strategy.DOBLE_PROGRESION:
        return _propose_double(planned, rule)
    if strategy is Strategy.PESO_LINEAL:
        return _propose_weight(planned, rule)
    if strategy is Strategy.SERIES:
        return _propose_sets(planned, rule)
    if strategy is Strategy.TIEMPO:
        return _propose_time(planned, rule)
    if strategy is Strategy.VARIANTE:
        return _propose_variant(exercise, planned)

    return ProgressionAssessment(  # pragma: no cover - defensivo
        ProgressionOutcome.UNDETERMINED,
        f"Estrategia '{strategy}' no implementada",
    )


def _rep_ceiling(rule: ProgressionRule) -> int | None:
    """Techo de repeticiones: el de la regla o el de las guardas, el más bajo."""
    param = rule.params.get("rep_max")
    guard = rule.guards.max_reps
    values = [int(v) for v in (param, guard) if v is not None]
    return min(values) if values else None


def _propose_reps(planned: PlannedExercise, rule: ProgressionRule) -> ProgressionAssessment:
    step = int(rule.params.get("incremento", 1))
    ceiling = _rep_ceiling(rule)
    work = planned.work_sets

    if any(s.target_reps is None for s in work):
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "El plan tiene series sin repeticiones objetivo",
        )

    if ceiling is not None and all(s.target_reps >= ceiling for s in work):
        # Techo alcanzado y la regla no dice qué hacer después. Declararlo es
        # correcto; inventar un salto de peso no lo sería.
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            f"Alcanzado el techo de {ceiling} repeticiones y la regla "
            "'reps_lineal' no define cómo continuar. Considera cambiar a "
            "'doble_progresion' o a una variante más difícil",
        )

    new_sets = tuple(
        s if s.is_warmup else replace(s, target_reps=_cap(s.target_reps + step, ceiling))
        for s in planned.sets
    )
    return _ready(planned, new_sets, "repeticiones")


def _propose_double(planned: PlannedExercise, rule: ProgressionRule) -> ProgressionAssessment:
    rep_min = int(rule.params.get("rep_min", 8))
    ceiling = _rep_ceiling(rule)
    step = int(rule.params.get("incremento", 1))
    weight_step = float(rule.params.get("incremento_peso", 2.5))
    work = planned.work_sets

    if any(s.target_reps is None for s in work):
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "El plan tiene series sin repeticiones objetivo",
        )
    if ceiling is None:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "La doble progresión necesita un techo de repeticiones "
            "('rep_max') y la regla no lo define",
        )

    at_ceiling = all(s.target_reps >= ceiling for s in work)
    if not at_ceiling:
        new_sets = tuple(
            s if s.is_warmup else replace(s, target_reps=_cap(s.target_reps + step, ceiling))
            for s in planned.sets
        )
        return _ready(planned, new_sets, "repeticiones")

    # Techo de reps alcanzado: sube la carga y reinicia el rango.
    current = max((s.target_weight_kg or 0.0) for s in work)
    if current <= 0.0:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "Se alcanzó el techo de repeticiones, pero el plan no registra peso "
            "y no puede deducirse cuánto añadir. Indica el peso o pasa a una "
            "variante más difícil",
        )

    allowed, clamped = _clamp_increase(current, weight_step, rule)
    if allowed <= EPSILON:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "El incremento de peso permitido por las guardas es despreciable; "
            "revisa la regla de este ejercicio",
        )

    new_weight = current + allowed
    new_sets = tuple(
        s if s.is_warmup else replace(s, target_reps=rep_min, target_weight_kg=new_weight)
        for s in planned.sets
    )
    note = "peso (+reinicio de repeticiones)"
    if clamped:
        note += "; incremento recortado por la guarda de carga máxima"
    return _ready(planned, new_sets, note)


def _propose_weight(planned: PlannedExercise, rule: ProgressionRule) -> ProgressionAssessment:
    step = float(rule.params.get("incremento", 2.5))
    work = planned.work_sets
    current = max((s.target_weight_kg or 0.0) for s in work) if work else 0.0

    if current <= 0.0:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "El plan no registra peso objetivo: no puede deducirse el incremento",
        )

    allowed, clamped = _clamp_increase(current, step, rule)
    if allowed <= EPSILON:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "Las guardas no permiten ningún incremento de carga apreciable",
        )

    new_sets = tuple(
        s if s.is_warmup else replace(s, target_weight_kg=(s.target_weight_kg or current) + allowed)
        for s in planned.sets
    )
    note = "peso"
    if clamped:
        note += "; incremento recortado por la guarda de carga máxima"
    return _ready(planned, new_sets, note)


def _propose_sets(planned: PlannedExercise, rule: ProgressionRule) -> ProgressionAssessment:
    work = planned.work_sets
    if not work:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED, "El plan no tiene series efectivas"
        )

    ceiling = rule.params.get("set_max") or rule.guards.max_sets
    if ceiling is not None and len(work) >= int(ceiling):
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            f"Alcanzado el techo de {int(ceiling)} series y la regla 'series' "
            "no define cómo continuar",
        )

    last = work[-1]
    new_set = replace(last, set_no=max(s.set_no for s in planned.sets) + 1)
    return _ready(planned, (*planned.sets, new_set), "una serie más")


def _propose_time(planned: PlannedExercise, rule: ProgressionRule) -> ProgressionAssessment:
    step = int(rule.params.get("incremento_s", 5))
    param_max = rule.params.get("tiempo_max")
    guard_max = rule.guards.max_time_s
    limits = [int(v) for v in (param_max, guard_max) if v is not None]
    ceiling = min(limits) if limits else None
    work = planned.work_sets

    if any(s.target_time_s is None for s in work):
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            "El plan tiene series sin tiempo objetivo",
        )
    if ceiling is not None and all(s.target_time_s >= ceiling for s in work):
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            f"Alcanzado el techo de {ceiling}s y la regla 'tiempo' no define cómo continuar",
        )

    new_sets = tuple(
        s if s.is_warmup else replace(s, target_time_s=_cap(s.target_time_s + step, ceiling))
        for s in planned.sets
    )
    return _ready(planned, new_sets, "tiempo")


def _propose_variant(exercise: Exercise, planned: PlannedExercise) -> ProgressionAssessment:
    if exercise.next_variant_slug is None:
        return ProgressionAssessment(
            ProgressionOutcome.UNDETERMINED,
            f"'{exercise.name}' progresa por variante pero no tiene definida "
            "la siguiente de la cadena",
        )
    summary = f"{exercise.name} → {exercise.next_variant_slug} ({describe_sets(planned.sets)})"
    return ProgressionAssessment(
        ProgressionOutcome.READY,
        "Objetivo cumplido de forma sostenida: toca pasar a la variante siguiente",
        ProgressionProposal(planned.sets, summary, exercise.next_variant_slug),
    )


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _cap(value: int, ceiling: int | None) -> int:
    return value if ceiling is None else min(value, ceiling)


def _clamp_increase(current: float, requested: float, rule: ProgressionRule) -> tuple[float, bool]:
    """Recorta un incremento de carga a lo que permiten las guardas.

    Devuelve ``(incremento_permitido, fue_recortado)``.
    """
    guards = rule.guards
    allowed = requested
    clamped = False

    ceiling_pct = current * guards.max_load_increase_pct
    if allowed > ceiling_pct + EPSILON:
        allowed = ceiling_pct
        clamped = True

    if guards.max_weight_kg is not None:
        room = max(0.0, guards.max_weight_kg - current)
        if allowed > room + EPSILON:
            allowed = room
            clamped = True

    return allowed, clamped


def _deload_proposal(planned: PlannedExercise) -> ProgressionProposal:
    """Descarga del 10 % sobre el peso, o una serie menos si no hay peso."""
    work = planned.work_sets
    has_weight = any((s.target_weight_kg or 0.0) > 0 for s in work)

    if has_weight:
        new_sets = tuple(
            s
            if s.is_warmup or not s.target_weight_kg
            else replace(s, target_weight_kg=round(s.target_weight_kg * 0.9, 2))
            for s in planned.sets
        )
        summary = f"{describe_sets(planned.sets)} → {describe_sets(new_sets)} (descarga 10 %)"
        return ProgressionProposal(new_sets, summary)

    if len(work) > 1:
        drop = work[-1].set_no
        new_sets = tuple(s for s in planned.sets if s.set_no != drop)
        summary = f"{describe_sets(planned.sets)} → {describe_sets(new_sets)} (una serie menos)"
        return ProgressionProposal(new_sets, summary)

    return ProgressionProposal(planned.sets, "Mantener el plan actual y descansar")


def _ready(
    planned: PlannedExercise, new_sets: tuple[PlannedSet, ...], what: str
) -> ProgressionAssessment:
    summary = f"{describe_sets(planned.sets)} → {describe_sets(new_sets)}"
    return ProgressionAssessment(
        ProgressionOutcome.READY,
        f"Objetivo cumplido de forma sostenida: progresa en {what}",
        ProgressionProposal(new_sets, summary),
    )
