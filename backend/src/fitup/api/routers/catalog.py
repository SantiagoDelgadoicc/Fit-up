"""Catálogo: músculos, ejercicios y reglas de progresión. Solo lectura."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ...application.repositories import catalog
from .. import schemas
from ..deps import get_db

router = APIRouter(prefix="/catalogo", tags=["catálogo"])


@router.get("/musculos", response_model=list[schemas.MuscleOut])
def list_muscles(db: sqlite3.Connection = Depends(get_db)):
    return catalog.list_muscles(db)


@router.get("/ejercicios", response_model=list[schemas.ExerciseOut])
def list_exercises(include_inactive: bool = False, db: sqlite3.Connection = Depends(get_db)):
    return [
        schemas.ExerciseOut(
            slug=e.slug,
            name=e.name,
            modality=str(e.modality),
            load_type=str(e.load_type),
            load_factor=e.load_factor,
            is_unilateral=e.is_unilateral,
            equipment=e.equipment,
            default_rule_slug=e.default_rule_slug,
            next_variant_slug=e.next_variant_slug,
            default_rest_seconds=e.default_rest_seconds,
            muscles=[
                schemas.MuscleLinkOut(muscle_slug=m.muscle_slug, role=str(m.role))
                for m in e.muscles
            ],
        )
        for e in catalog.list_exercises(db, active_only=not include_inactive)
    ]


@router.get("/ejercicios/{slug}", response_model=schemas.ExerciseOut)
def get_exercise(slug: str, db: sqlite3.Connection = Depends(get_db)):
    exercise = catalog.get_exercise(db, slug)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el ejercicio '{slug}'")
    return schemas.ExerciseOut(
        slug=exercise.slug,
        name=exercise.name,
        modality=str(exercise.modality),
        load_type=str(exercise.load_type),
        load_factor=exercise.load_factor,
        is_unilateral=exercise.is_unilateral,
        equipment=exercise.equipment,
        default_rule_slug=exercise.default_rule_slug,
        next_variant_slug=exercise.next_variant_slug,
        default_rest_seconds=exercise.default_rest_seconds,
        muscles=[
            schemas.MuscleLinkOut(muscle_slug=m.muscle_slug, role=str(m.role))
            for m in exercise.muscles
        ],
    )


@router.get("/reglas", response_model=list[schemas.RuleOut])
def list_rules(db: sqlite3.Connection = Depends(get_db)):
    return [
        schemas.RuleOut(slug=r.slug, name=r.name, strategy=str(r.strategy), params=dict(r.params))
        for r in catalog.list_rules(db)
    ]
