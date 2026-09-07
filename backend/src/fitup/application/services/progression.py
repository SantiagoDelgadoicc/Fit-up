"""Casos de uso de sobrecarga progresiva.

El cálculo vive entero en ``domain.progression.engine``, que es puro. Este
módulo solo hace lo que el dominio no puede: leer el historial, resolver qué
regla aplica, escribir la versión nueva y dejar el rastro auditable.

Tres cosas que no se negocian aquí:

1. **Aplicar re-evalúa.** El cliente dice qué ejercicios quiere progresar, no
   cuánto: la propuesta se recalcula en el servidor. Un cliente no puede pedir
   un salto que las guardas no permitirían.
2. **Un lote, una versión.** Progresar tres ejercicios crea *una* versión con
   los tres cambios y *tres* eventos, no tres versiones.
3. **Deshacer no borra.** Genera otra versión que restaura el plan anterior y
   marca el evento original como revertido (regla R14).
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, replace
from datetime import date as Date

from ...domain.enums import Actor
from ...domain.models import PlannedExercise, PlannedSet
from ...domain.progression.engine import ExerciseHistoryEntry, describe_sets, evaluate
from ..errors import Conflict, Invalid, NotFound
from ..repositories import catalog, history, planning
from ..repositories import progression as events
from ..views import (
    ProgressionApplied,
    ProgressionEventView,
    ProgressionItem,
    RoutineProgression,
    RoutineReadiness,
)

#: Sesiones que se le pasan al motor. Con las guardas actuales bastarían dos,
#: pero la detección de regresiones necesita ver una racha, no un par.
HISTORY_WINDOW = 12


# --------------------------------------------------------------------------
# Evaluación
# --------------------------------------------------------------------------


def evaluate_routine(
    conn: sqlite3.Connection, routine_id: int, *, today: Date | None = None
) -> RoutineProgression:
    """Veredicto del motor para cada ejercicio de la versión vigente."""
    today = today or Date.today()
    detail = planning.get_routine(conn, routine_id)
    items = tuple(_evaluate(conn, planned, today=today) for planned in detail.exercises)
    return RoutineProgression(
        routine_id=detail.id,
        routine_name=detail.name,
        version_id=detail.version_id,
        version_no=detail.version_no,
        items=items,
    )


def _evaluate(
    conn: sqlite3.Connection, planned: PlannedExercise, *, today: Date
) -> ProgressionItem:
    exercise = catalog.get_exercise(conn, planned.exercise_slug)
    if exercise is None:  # pragma: no cover - el catálogo es semilla, no entrada
        raise NotFound(f"No existe el ejercicio '{planned.exercise_slug}'")

    # La rutina manda; si no dice nada, vale la regla que el catálogo declara
    # para ese ejercicio. No es suponer: está escrita, solo que en otro sitio.
    rule_slug = planned.rule_slug or exercise.default_rule_slug
    inherited = planned.rule_slug is None and rule_slug is not None
    rule = catalog.get_rule(conn, rule_slug) if rule_slug else None

    entries = [
        ExerciseHistoryEntry(date=day, performed=performed)
        for day, performed in history.exercise_history(
            conn, planned.exercise_slug, limit=HISTORY_WINDOW
        )
    ]
    last = events.last_applied_on(conn, planned.exercise_slug)

    assessment = evaluate(
        exercise=exercise,
        planned=planned,
        rule=rule,
        history=entries,
        today=today,
        last_progression_date=last,
    )

    proposal = assessment.proposal
    next_slug = proposal.next_exercise_slug if proposal else None
    next_name = None
    if next_slug is not None:
        variant = catalog.get_exercise(conn, next_slug)
        next_name = variant.name if variant else next_slug

    return ProgressionItem(
        exercise_slug=planned.exercise_slug,
        exercise_name=exercise.name,
        outcome=assessment.outcome,
        reason=assessment.reason,
        rule_slug=rule_slug,
        rule_inherited=inherited,
        current=describe_sets(planned.sets),
        proposed=describe_sets(proposal.sets) if proposal else None,
        proposed_sets=proposal.sets if proposal else (),
        next_exercise_slug=next_slug,
        next_exercise_name=next_name,
        last_progression=last,
    )


def readiness(conn: sqlite3.Connection, *, today: Date | None = None) -> list[RoutineReadiness]:
    """Cuántos ejercicios pueden progresar en cada rutina activa.

    Es lo que la pantalla «Hoy» necesita para avisar sin obligar a entrar en
    cada rutina a comprobarlo.
    """
    today = today or Date.today()
    result: list[RoutineReadiness] = []
    for summary in planning.list_routines(conn):
        evaluation = evaluate_routine(conn, summary.id, today=today)
        if evaluation.ready or evaluation.deload:
            result.append(
                RoutineReadiness(
                    routine_id=summary.id,
                    routine_name=summary.name,
                    ready=evaluation.ready,
                    deload=evaluation.deload,
                )
            )
    return result


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------


def _snapshot(*, exercise_slug: str, rule_slug: str | None, sets: tuple[PlannedSet, ...]) -> dict:
    """Foto del plan de un ejercicio, tal y como se guarda en el evento.

    Es lo que permite deshacer sin adivinar: el `before` es literalmente el
    plan que había, no una reconstrucción.
    """
    return {
        "exercise_slug": exercise_slug,
        "rule_slug": rule_slug,
        "summary": describe_sets(sets),
        "sets": [asdict(s) for s in sets],
    }


def _reject_duplicates(exercises: list[PlannedExercise]) -> None:
    seen: set[str] = set()
    for planned in exercises:
        if planned.exercise_slug in seen:
            raise Invalid(
                f"'{planned.exercise_slug}' quedaría dos veces en la rutina. "
                "Quita la repetición desde el editor antes de aplicar este cambio"
            )
        seen.add(planned.exercise_slug)


def apply(
    conn: sqlite3.Connection,
    routine_id: int,
    *,
    exercise_slugs: list[str],
    today: Date | None = None,
    actor: Actor = Actor.USUARIO,
    note: str | None = None,
) -> ProgressionApplied:
    """Aplica las progresiones elegidas creando una versión nueva de la rutina.

    Se re-evalúa aquí a propósito: el cliente elige *qué* ejercicios, nunca
    *cuánto* se sube. Si entre pintar la pantalla y pulsar el botón dejó de ser
    seguro progresar, la operación se rechaza con el motivo.
    """
    today = today or Date.today()
    if not exercise_slugs:
        raise Invalid("No se ha seleccionado ningún ejercicio para progresar")

    evaluation = evaluate_routine(conn, routine_id, today=today)
    by_slug = {item.exercise_slug: item for item in evaluation.items}

    chosen: dict[str, ProgressionItem] = {}
    for slug in exercise_slugs:
        item = by_slug.get(slug)
        if item is None:
            raise NotFound(f"'{slug}' no está en la rutina {routine_id}")
        if not item.is_applicable:
            raise Conflict(f"'{item.exercise_name}' no puede progresar ahora: {item.reason}")
        chosen[slug] = item

    before = planning.get_routine(conn, routine_id)
    new_exercises: list[PlannedExercise] = []
    for planned in before.exercises:
        item = chosen.get(planned.exercise_slug)
        if item is None:
            new_exercises.append(planned)
            continue
        new_exercises.append(
            replace(
                planned,
                exercise_slug=item.next_exercise_slug or planned.exercise_slug,
                sets=item.proposed_sets or planned.sets,
            )
        )
    _reject_duplicates(new_exercises)

    summary = ", ".join(f"{i.exercise_name}: {i.current} → {i.proposed}" for i in chosen.values())
    planning.create_version(
        conn,
        routine_id,
        exercises=new_exercises,
        note=note or f"Progresión aplicada: {summary}",
        actor=actor,
    )
    after = planning.get_routine(conn, routine_id)

    created: list[int] = []
    for planned in before.exercises:
        item = chosen.get(planned.exercise_slug)
        if item is None:
            continue
        created.append(
            events.record(
                conn,
                # El evento se atribuye al ejercicio de partida: es el que
                # progresó, aunque la propuesta lo sustituya por su variante.
                exercise_slug=planned.exercise_slug,
                routine_id=routine_id,
                from_version_id=before.version_id,
                to_version_id=after.version_id,
                rule_slug=item.rule_slug or "",
                before=_snapshot(
                    exercise_slug=planned.exercise_slug,
                    rule_slug=planned.rule_slug,
                    sets=planned.sets,
                ),
                after=_snapshot(
                    exercise_slug=item.next_exercise_slug or planned.exercise_slug,
                    rule_slug=planned.rule_slug,
                    sets=item.proposed_sets or planned.sets,
                ),
                rationale=f"{item.reason}. {item.current} → {item.proposed}",
                actor=actor,
            )
        )

    history.audit(
        conn,
        actor=actor,
        action="apply_progression",
        payload={
            "routine_id": routine_id,
            "exercises": list(chosen),
            "from_version": before.version_no,
            "to_version": after.version_no,
        },
    )
    conn.commit()
    return ProgressionApplied(
        routine=after,
        events=tuple(events.get_event(conn, event_id) for event_id in created),
    )


# --------------------------------------------------------------------------
# Deshacer
# --------------------------------------------------------------------------


def undo(
    conn: sqlite3.Connection, event_id: int, *, actor: Actor = Actor.USUARIO
) -> ProgressionApplied:
    """Revierte una progresión creando la versión que restaura el plan previo.

    Se niega si el plan cambió después: deshacer descartaría en silencio esa
    edición, y el sistema prefiere decir que no puede antes que decidir por su
    cuenta cuál de los dos cambios importa más.
    """
    event = events.get_event(conn, event_id)
    if event.reverted:
        raise Conflict("Esa progresión ya se deshizo")
    if event.is_reversal:
        raise Conflict(
            "Eso ya es una reversión. Para volver a subir, aplica la progresión de nuevo"
        )

    before = planning.get_routine(conn, event.routine_id)
    target_slug = event.after["exercise_slug"]
    current = next((e for e in before.exercises if e.exercise_slug == target_slug), None)
    if current is None:
        raise Conflict(
            f"'{event.exercise_name}' ya no está en la versión actual de "
            f"'{event.routine_name}': deshacer pisaría un cambio posterior"
        )
    if [asdict(s) for s in current.sets] != event.after["sets"]:
        raise Conflict(
            f"El plan de '{event.exercise_name}' cambió después de esa progresión. "
            "Deshacer descartaría ese cambio, así que hay que ajustarlo desde el editor"
        )

    restored = tuple(PlannedSet(**s) for s in event.before["sets"])
    new_exercises = [
        replace(e, exercise_slug=event.before["exercise_slug"], sets=restored)
        if e.exercise_slug == target_slug
        else e
        for e in before.exercises
    ]
    _reject_duplicates(new_exercises)

    planning.create_version(
        conn,
        event.routine_id,
        exercises=new_exercises,
        note=f"Progresión deshecha: {event.exercise_name} vuelve a {event.before['summary']}",
        actor=actor,
    )
    after = planning.get_routine(conn, event.routine_id)

    reversal_id = events.record(
        conn,
        exercise_slug=event.exercise_slug,
        routine_id=event.routine_id,
        from_version_id=before.version_id,
        to_version_id=after.version_id,
        rule_slug=event.rule_slug,
        before=event.after,
        after=event.before,
        rationale=(
            f"Reversión de la progresión del {event.applied_at.date().isoformat()}: "
            f"{event.after['summary']} → {event.before['summary']}"
        ),
        actor=actor,
    )
    events.mark_reverted(conn, event.id, by_event_id=reversal_id)

    history.audit(
        conn,
        actor=actor,
        action="undo_progression",
        payload={"event_id": event.id, "routine_id": event.routine_id},
    )
    conn.commit()
    return ProgressionApplied(routine=after, events=(events.get_event(conn, reversal_id),))


# --------------------------------------------------------------------------
# Historial
# --------------------------------------------------------------------------


def list_events(
    conn: sqlite3.Connection, *, routine_id: int | None = None, limit: int = 50
) -> list[ProgressionEventView]:
    return events.list_events(conn, routine_id=routine_id, limit=limit)
