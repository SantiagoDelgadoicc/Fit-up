"""Constructores compactos para los tests del dominio.

Los tests se leen mejor cuando el ruido de construir entidades desaparece:
lo relevante de un caso es qué se planificó y qué se hizo, no el boilerplate.
"""

from __future__ import annotations

from datetime import date

import pytest

from fitup.domain.enums import LoadType, Modality, MuscleRole, Strategy
from fitup.domain.models import (
    Exercise,
    Guards,
    MuscleLink,
    PerformedExercise,
    PerformedSet,
    PlannedExercise,
    PlannedSet,
    ProgressionRule,
)
from fitup.domain.progression.engine import ExerciseHistoryEntry


def make_exercise(
    slug: str = "flexiones",
    *,
    modality: Modality = Modality.REPS,
    load_type: LoadType = LoadType.CORPORAL,
    load_factor: float = 0.64,
    is_unilateral: bool = False,
    next_variant: str | None = None,
    muscles: tuple[tuple[str, MuscleRole], ...] = (("pectoral", MuscleRole.PRIMARIO),),
) -> Exercise:
    return Exercise(
        slug=slug,
        name=slug.replace("_", " ").capitalize(),
        modality=modality,
        load_type=load_type,
        load_factor=load_factor,
        is_unilateral=is_unilateral,
        next_variant_slug=next_variant,
        muscles=tuple(MuscleLink(m, r) for m, r in muscles),
    )


def planned(
    *,
    sets: int = 3,
    reps: int | None = 15,
    weight: float | None = None,
    time_s: int | None = None,
    slug: str = "flexiones",
    rule_slug: str | None = None,
) -> PlannedExercise:
    return PlannedExercise(
        exercise_slug=slug,
        position=0,
        rule_slug=rule_slug,
        sets=tuple(
            PlannedSet(
                set_no=i + 1,
                target_reps=reps,
                target_weight_kg=weight,
                target_time_s=time_s,
            )
            for i in range(sets)
        ),
    )


def performed(
    *,
    sets: int = 3,
    reps: int | None = 15,
    weight: float | None = None,
    time_s: int | None = None,
    rir: int | None = None,
    completed: bool = True,
    slug: str = "flexiones",
) -> PerformedExercise:
    return PerformedExercise(
        exercise_slug=slug,
        position=0,
        sets=tuple(
            PerformedSet(
                set_no=i + 1,
                reps=reps,
                weight_kg=weight,
                time_s=time_s,
                rir=rir,
                completed=completed,
            )
            for i in range(sets)
        ),
    )


def history(*entries: tuple[date, PerformedExercise]) -> list[ExerciseHistoryEntry]:
    """Historial ordenado de antiguo a reciente."""
    return [ExerciseHistoryEntry(d, p) for d, p in sorted(entries, key=lambda e: e[0])]


def rule(
    strategy: Strategy,
    *,
    params: dict | None = None,
    guards: Guards | None = None,
    slug: str = "regla",
) -> ProgressionRule:
    return ProgressionRule(
        slug=slug,
        name=slug,
        strategy=strategy,
        params=params or {},
        guards=guards or Guards(),
    )


@pytest.fixture
def today() -> date:
    return date(2026, 3, 15)
