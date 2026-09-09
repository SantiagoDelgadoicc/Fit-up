"""Métricas derivadas del historial: volumen, frecuencia y 1RM equivalente.

Aquí ocurre la traducción que el dominio del ranking no puede hacer por sí
solo: pasar de "una sesión con estos ejercicios y estas series" a "estos
músculos recibieron este estímulo". Combina tres cosas que solo la aplicación
conoce a la vez —historial, catálogo y peso corporal— y devuelve los
``StimulusEvent`` puros que consume ``domain.ranking``.

Nada de esto se almacena: todo se recalcula desde el registro crudo (regla
R15). La única excepción es ``muscle_score_snapshot``, que es caché.
"""

from __future__ import annotations

import sqlite3
from bisect import bisect_right
from collections import defaultdict
from datetime import date as Date
from datetime import timedelta

from ...domain.enums import ROLE_CONTRIBUTION, LoadType, Modality, SessionStatus
from ...domain.metrics.load import LoadUndeterminable, set_e1rm_kg, set_mark, set_volume_kg
from ...domain.models import Exercise
from ...domain.ranking.standards import standard_for
from ...domain.ranking.v2 import StimulusEvent
from ..repositories import catalog, history
from ..views import ExerciseProgress, ExerciseStimulus, MuscleUsage, StimulusData


class _Bodyweight:
    """Peso corporal vigente en una fecha, resuelto en memoria.

    El repositorio sabe hacerlo, pero con una consulta por día: aquí se
    recorren cientos de sesiones y esa cuenta se nota.
    """

    def __init__(self, entries: list[tuple[Date, float]]) -> None:
        self._dates = [d for d, _ in entries]
        self._weights = [w for _, w in entries]

    def at(self, day: Date) -> float | None:
        if not self._dates:
            return None
        index = bisect_right(self._dates, day)
        if index:
            return self._weights[index - 1]
        # Antes del primer registro se usa el primero: es mejor estimación que
        # ninguna para fechas previas al inicio del seguimiento, y es lo que
        # ya hace `history.bodyweight_at`.
        return self._weights[0]

    @property
    def empty(self) -> bool:
        return not self._dates


def load_stimuli(
    conn: sqlite3.Connection, *, since: Date, until: Date, exercise_slug: str | None = None
) -> StimulusData:
    """Recorre el historial del rango y lo convierte en estímulo por ejercicio.

    Las series de calentamiento y las no completadas no aportan; las que no se
    pueden convertir se cuentan y se explican en vez de valer cero en silencio.
    """
    bodyweight = _Bodyweight(history.bodyweight_history(conn))
    exercises: dict[str, Exercise | None] = {}

    grouped: dict[tuple[Date, str], list[float]] = defaultdict(list)
    marks: dict[tuple[Date, str], list[float]] = defaultdict(list)
    volumes: dict[tuple[Date, str], float] = defaultdict(float)
    counts: dict[tuple[Date, str], int] = defaultdict(int)
    skipped = 0
    reasons: dict[str, None] = {}
    references: dict[str, float] = {}

    # De la sesión más antigua a la más reciente: el peso de referencia de un
    # ejercicio sin calibrar es el primero que se registró, y para deducirlo
    # hay que recorrer el historial en orden.
    for session in sorted(history.sessions_between(conn, since, until), key=lambda s: s.date):
        if session.status is SessionStatus.SKIPPED:
            continue
        weight = bodyweight.at(session.date)

        for performed in session.exercises:
            if exercise_slug is not None and performed.exercise_slug != exercise_slug:
                continue
            if performed.exercise_slug not in exercises:
                exercises[performed.exercise_slug] = catalog.get_exercise(
                    conn, performed.exercise_slug
                )
            exercise = exercises[performed.exercise_slug]
            if exercise is None:  # pragma: no cover - el catálogo es semilla
                continue

            key = (session.date, performed.exercise_slug)
            reference = _reference_weight(exercise, performed, references)
            for s in performed.sets:
                if s.is_warmup or not s.completed:
                    continue

                # La marca va primero y fuera del `try`: son repeticiones o
                # segundos, no kilos, así que existe aunque el volumen no se
                # pueda calcular. Es lo que permite que el rango funcione sin
                # peso corporal registrado, cosa que en v1 lo bloqueaba todo.
                mark = set_mark(exercise, s, bodyweight_kg=weight, reference_weight_kg=reference)
                if mark is not None:
                    marks[key].append(mark)

                try:
                    volumes[key] += set_volume_kg(exercise, s, bodyweight_kg=weight)
                    counts[key] += 1
                except LoadUndeterminable as exc:
                    skipped += 1
                    reasons[str(exc)] = None
                    continue
                e1rm = set_e1rm_kg(exercise, s, bodyweight_kg=weight)
                if e1rm is not None:
                    grouped[key].append(e1rm)

    stimuli = tuple(
        ExerciseStimulus(
            date=day,
            exercise_slug=slug,
            volume_kg=volumes[(day, slug)],
            # La mejor serie del día representa la capacidad de ese día; las
            # demás ya cuentan en el volumen.
            e1rm_kg=max(grouped[(day, slug)]) if grouped.get((day, slug)) else None,
            mark=max(marks[(day, slug)]) if marks.get((day, slug)) else None,
            sets=counts[(day, slug)],
        )
        # Unión, no solo `counts`: una serie cuyo volumen no se puede calcular
        # sigue teniendo marca, y dejarla fuera perdería el rango de un
        # ejercicio corporal por no tener el peso anotado.
        for (day, slug) in sorted(set(counts) | set(marks))
    )
    return StimulusData(
        by_exercise=stimuli,
        skipped_sets=skipped,
        skipped_reasons=tuple(reasons)[:5],
        bodyweight_missing=bodyweight.empty,
    )


def _reference_weight(exercise: Exercise, performed, references: dict[str, float]) -> float | None:
    """Peso con el que se compara la marca de un ejercicio de carga externa.

    El de la escalera si está calibrada; si no, **el primero que registró el
    usuario**. Así cualquier ejercicio del catálogo tiene una referencia sin
    que haya que inventarle una: la suya es la propia.
    """
    if exercise.load_type is not LoadType.EXTERNA:
        return None

    calibrated = standard_for(exercise.slug).reference_weight_kg
    if calibrated:
        return calibrated

    if exercise.slug not in references:
        weights = [s.weight_kg for s in performed.sets if s.weight_kg and not s.is_warmup]
        if weights:
            references[exercise.slug] = max(weights)
    return references.get(exercise.slug)


def events_by_muscle(
    conn: sqlite3.Connection, data: StimulusData
) -> dict[str, list[StimulusEvent]]:
    """Reparte cada estímulo entre los músculos del ejercicio, según su rol.

    Un press banca aporta al pectoral entero, al tríceps la mitad y al
    deltoide anterior la mitad: los factores viven en ``ROLE_CONTRIBUTION``,
    que es configuración de la fórmula y no un dato del catálogo (regla R15).

    Aquí se resuelve también la escalera de cada ejercicio: el dominio del
    ranking no conoce el catálogo, así que la recibe ya adjunta al estímulo.
    """
    exercises = {e.slug: e for e in catalog.list_exercises(conn, active_only=False)}
    result: dict[str, list[StimulusEvent]] = defaultdict(list)

    for stimulus in data.by_exercise:
        exercise = exercises.get(stimulus.exercise_slug)
        if exercise is None:  # pragma: no cover - el catálogo es semilla
            continue
        standard = standard_for(exercise.slug, is_time_based=exercise.modality is Modality.TIEMPO)
        for link in exercise.muscles:
            result[link.muscle_slug].append(
                StimulusEvent(
                    date=stimulus.date,
                    exercise_slug=stimulus.exercise_slug,
                    role_factor=ROLE_CONTRIBUTION[link.role],
                    volume_kg=stimulus.volume_kg,
                    mark=stimulus.mark,
                    standard=standard,
                )
            )
    return result


# --------------------------------------------------------------------------
# Métricas legibles
# --------------------------------------------------------------------------


def muscle_usage(events: list[StimulusEvent], *, since: Date, until: Date) -> MuscleUsage:
    """Volumen y frecuencia de un músculo en la ventana indicada."""
    window = [e for e in events if since <= e.date <= until]
    if not window:
        return MuscleUsage(volume_kg=0.0, sessions=0, sessions_per_week=0.0)

    by_exercise: dict[str, float] = defaultdict(float)
    for e in window:
        by_exercise[e.exercise_slug] += e.volume_kg * e.role_factor

    days = {e.date for e in window}
    weeks = max(1.0, ((until - since).days + 1) / 7.0)
    ranked = sorted(by_exercise.items(), key=lambda kv: kv[1], reverse=True)

    return MuscleUsage(
        volume_kg=round(sum(by_exercise.values()), 1),
        sessions=len(days),
        sessions_per_week=round(len(days) / weeks, 2),
        top_exercises=tuple((slug, round(volume, 1)) for slug, volume in ranked),
    )


def exercise_progress(
    conn: sqlite3.Connection, exercise_slug: str, *, since: Date, until: Date
) -> ExerciseProgress:
    data = load_stimuli(conn, since=since, until=until, exercise_slug=exercise_slug)
    points = data.by_exercise
    measurable = [p for p in points if p.e1rm_kg is not None]
    best = max(measurable, key=lambda p: p.e1rm_kg or 0.0) if measurable else None
    return ExerciseProgress(
        exercise_slug=exercise_slug,
        points=points,
        best_e1rm_kg=round(best.e1rm_kg, 1) if best and best.e1rm_kg else None,
        best_on=best.date if best else None,
    )


def default_window(today: Date, days: int) -> tuple[Date, Date]:
    return today - timedelta(days=days), today
