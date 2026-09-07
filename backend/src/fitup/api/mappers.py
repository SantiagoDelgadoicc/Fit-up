"""Traducción entre el contrato HTTP y el dominio.

Un único sitio donde ocurre la conversión: si los routers construyeran
entidades a mano, cada uno lo haría un poco distinto.
"""

from __future__ import annotations

from ..application.errors import Invalid
from ..application.services.planning import build_sets
from ..application.views import DayView, RoutineDetail, SessionDetail
from ..domain.models import PerformedExercise, PerformedSet, PlannedExercise, PlannedSet
from . import schemas


def to_planned_exercises(items: list[schemas.PlannedExerciseIn]) -> list[PlannedExercise]:
    result: list[PlannedExercise] = []
    for position, item in enumerate(items):
        if item.sets:
            sets = tuple(
                PlannedSet(
                    set_no=s.set_no,
                    target_reps=s.target_reps,
                    target_reps_max=s.target_reps_max,
                    target_weight_kg=s.target_weight_kg,
                    target_time_s=s.target_time_s,
                    target_rir=s.target_rir,
                    is_warmup=s.is_warmup,
                )
                for s in item.sets
            )
        elif item.spec:
            sets = build_sets(
                count=item.spec.count,
                reps=item.spec.reps,
                reps_max=item.spec.reps_max,
                weight_kg=item.spec.weight_kg,
                time_s=item.spec.time_s,
                rir=item.spec.rir,
                warmup=item.spec.warmup,
            )
        else:
            raise Invalid(f"'{item.exercise_slug}' no define series: usa 'sets' o 'spec'")

        result.append(
            PlannedExercise(
                exercise_slug=item.exercise_slug,
                position=position,
                sets=sets,
                rest_seconds=item.rest_seconds,
                rule_slug=item.rule_slug,
                notes=item.notes,
            )
        )
    return result


def to_performed_exercises(items: list[schemas.PerformedExerciseIn]) -> list[PerformedExercise]:
    return [
        PerformedExercise(
            exercise_slug=item.exercise_slug,
            position=position,
            notes=item.notes,
            sets=tuple(
                PerformedSet(
                    set_no=s.set_no,
                    reps=s.reps,
                    weight_kg=s.weight_kg,
                    time_s=s.time_s,
                    rir=s.rir,
                    completed=s.completed,
                    is_warmup=s.is_warmup,
                )
                for s in item.sets
            ),
        )
        for position, item in enumerate(items)
    ]


def routine_out(detail: RoutineDetail) -> schemas.RoutineOut:
    return schemas.RoutineOut(
        id=detail.id,
        name=detail.name,
        status=detail.status,
        version_id=detail.version_id,
        version_no=detail.version_no,
        created_at=detail.created_at,
        note=detail.note,
        exercises=[
            schemas.PlannedExerciseOut(
                exercise_slug=e.exercise_slug,
                position=e.position,
                rest_seconds=e.rest_seconds,
                rule_slug=e.rule_slug,
                notes=e.notes,
                sets=[schemas.PlannedSetOut.model_validate(s) for s in e.sets],
            )
            for e in detail.exercises
        ],
    )


def session_out(detail: SessionDetail) -> schemas.SessionOut:
    return schemas.SessionOut(
        id=detail.id,
        date=detail.date,
        status=detail.status,
        origin=detail.origin,
        routine_id=detail.routine_id,
        routine_name=detail.routine_name,
        routine_version_no=detail.routine_version_no,
        perceived_effort=detail.perceived_effort,
        duration_min=detail.duration_min,
        notes=detail.notes,
        logged_at=detail.logged_at,
        is_retroactive=detail.is_retroactive,
        exercises=[
            schemas.PerformedExerciseOut(
                exercise_slug=e.exercise_slug,
                position=e.position,
                notes=e.notes,
                sets=[schemas.PerformedSetOut.model_validate(s) for s in e.sets],
            )
            for e in detail.exercises
        ],
    )


def day_out(view: DayView) -> schemas.DayOut:
    return schemas.DayOut(
        date=view.date,
        state=view.state,
        reason=view.reason,
        can_log=view.can_log,
        planned=routine_out(view.planned) if view.planned else None,
        session=session_out(view.session) if view.session else None,
        exception_reason=view.exception_reason,
    )
