"""Atajos para construir escenarios en los tests de la capa de aplicación.

Vive en `tests/` (que está en `pythonpath`) y no en `tests/application/`, para
que sea importable desde cualquier módulo de test sin trucos de sys.path.
"""

from __future__ import annotations

from fitup.application.services import planning as planning_svc
from fitup.domain.models import PlannedExercise


def plan(
    slug: str,
    *,
    count: int = 3,
    reps: int | None = 15,
    rule_slug: str | None = None,
    **kw,
) -> PlannedExercise:
    """Un ejercicio planificado con series ya generadas."""
    return PlannedExercise(
        exercise_slug=slug,
        position=0,
        rule_slug=rule_slug,
        sets=planning_svc.build_sets(count=count, reps=reps, **kw),
    )
