"""Traducción entre el contrato HTTP y el dominio.

Un único sitio donde ocurre la conversión: si los routers construyeran
entidades a mano, cada uno lo haría un poco distinto.
"""

from __future__ import annotations

from ..application.errors import Invalid
from ..application.services.planning import build_sets
from ..application.views import (
    DayView,
    ExerciseProgress,
    MuscleDetail,
    MuscleRankingEntry,
    MuscleUsage,
    ProgressionApplied,
    ProgressionEventView,
    ProgressionItem,
    RankingView,
    RoutineDetail,
    RoutineProgression,
    SessionDetail,
)
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
                    to_failure=s.to_failure,
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
                to_failure=item.spec.to_failure,
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
        scheduled=[
            schemas.ScheduledRoutineOut(
                routine_id=s.routine_id,
                name=s.name,
                detail=routine_out(s.detail),
                session=session_out(s.session) if s.session else None,
                can_log=s.can_log,
            )
            for s in view.scheduled
        ],
        extra_sessions=[session_out(s) for s in view.extra_sessions],
        exception_reason=view.exception_reason,
    )


def progression_item_out(item: ProgressionItem) -> schemas.ProgressionItemOut:
    return schemas.ProgressionItemOut(
        exercise_slug=item.exercise_slug,
        exercise_name=item.exercise_name,
        outcome=item.outcome,
        reason=item.reason,
        current=item.current,
        applicable=item.is_applicable,
        rule_slug=item.rule_slug,
        rule_inherited=item.rule_inherited,
        proposed=item.proposed,
        proposed_sets=[schemas.PlannedSetOut.model_validate(s) for s in item.proposed_sets],
        next_exercise_slug=item.next_exercise_slug,
        next_exercise_name=item.next_exercise_name,
        last_progression=item.last_progression,
    )


def routine_progression_out(view: RoutineProgression) -> schemas.RoutineProgressionOut:
    return schemas.RoutineProgressionOut(
        routine_id=view.routine_id,
        routine_name=view.routine_name,
        version_no=view.version_no,
        ready=view.ready,
        deload=view.deload,
        items=[progression_item_out(i) for i in view.items],
    )


def progression_event_out(event: ProgressionEventView) -> schemas.ProgressionEventOut:
    return schemas.ProgressionEventOut(
        id=event.id,
        exercise_slug=event.exercise_slug,
        exercise_name=event.exercise_name,
        routine_id=event.routine_id,
        routine_name=event.routine_name,
        rule_slug=event.rule_slug,
        rationale=event.rationale,
        applied_at=event.applied_at,
        actor=event.actor,
        # Del snapshot solo sale hacia fuera el resumen legible: las filas
        # completas viven en el evento por si hay que auditarlo, pero la UI no
        # las necesita para decidir nada.
        before_summary=event.before["summary"],
        after_summary=event.after["summary"],
        before_exercise_slug=event.before["exercise_slug"],
        after_exercise_slug=event.after["exercise_slug"],
        reverted=event.reverted,
        is_reversal=event.is_reversal,
        from_version_no=event.from_version_no,
        to_version_no=event.to_version_no,
    )


def progression_applied_out(result: ProgressionApplied) -> schemas.ProgressionAppliedOut:
    return schemas.ProgressionAppliedOut(
        routine=routine_out(result.routine),
        events=[progression_event_out(e) for e in result.events],
    )


def muscle_ranking_out(entry: MuscleRankingEntry) -> schemas.MuscleRankingOut:
    score = entry.score
    return schemas.MuscleRankingOut(
        muscle_slug=entry.muscle_slug,
        name=entry.name,
        region=entry.region,
        body_view=entry.body_view,
        svg_key=entry.svg_key,
        display_order=entry.display_order,
        tier=score.tier,
        has_data=score.has_data,
        activity=score.activity,
        # `None` y no 0.0: el cliente pinta "sin datos", no un mínimo.
        development=entry.development,
        days_since_stimulus=score.days_since_stimulus,
        points_to_next_tier=score.points_to_next_tier,
        leading_exercise=score.leading_exercise,
        leading_mark=score.leading_mark,
        next_mark=score.next_mark,
        notes=list(score.notes),
    )


def ranking_out(view: RankingView) -> schemas.RankingOut:
    return schemas.RankingOut(
        today=view.today,
        formula_version=view.formula_version,
        provisional=view.provisional,
        measured=view.measured,
        bodyweight_kg=view.bodyweight_kg,
        entries=[muscle_ranking_out(e) for e in view.entries],
        balance=[
            schemas.BalanceCheckOut(
                key=c.key,
                name=c.name,
                verdict=str(c.verdict),
                message=c.message,
                left_name=c.left_name,
                right_name=c.right_name,
                left_score=c.left_score,
                right_score=c.right_score,
                ratio=c.ratio,
                missing=list(c.missing),
            )
            for c in view.balance
        ],
        notes=list(view.notes),
    )


def _usage_out(usage: MuscleUsage | None) -> schemas.MuscleUsageOut | None:
    if usage is None:
        return None
    return schemas.MuscleUsageOut(
        volume_kg=usage.volume_kg,
        sessions=usage.sessions,
        sessions_per_week=usage.sessions_per_week,
    )


def muscle_detail_out(detail: MuscleDetail) -> schemas.MuscleDetailOut:
    return schemas.MuscleDetailOut(
        muscle=muscle_ranking_out(detail.entry),
        factors=dict(detail.entry.score.factors),
        next_tier=detail.next_tier,
        points_to_next_tier=detail.points_to_next_tier,
        recent=_usage_out(detail.recent),
        quarter=_usage_out(detail.quarter),
        exercises=[
            schemas.ExerciseContributionOut(
                exercise_slug=c.exercise_slug,
                exercise_name=c.exercise_name,
                role=c.role,
                role_factor=c.role_factor,
                volume_kg=c.volume_kg,
                best_mark=c.best_mark,
                last_date=c.last_date,
            )
            for c in detail.exercises
        ],
        history=[
            schemas.ScorePointOut(
                date=p.date, development=p.development, activity=p.activity, tier=p.tier
            )
            for p in detail.history
        ],
    )


def exercise_progress_out(progress: ExerciseProgress) -> schemas.ExerciseProgressOut:
    return schemas.ExerciseProgressOut(
        exercise_slug=progress.exercise_slug,
        best_e1rm_kg=progress.best_e1rm_kg,
        best_on=progress.best_on,
        points=[
            schemas.ExercisePointOut(
                date=p.date,
                volume_kg=round(p.volume_kg, 1),
                sets=p.sets,
                e1rm_kg=round(p.e1rm_kg, 1) if p.e1rm_kg is not None else None,
                mark=round(p.mark, 1) if p.mark is not None else None,
            )
            for p in progress.points
        ],
    )
