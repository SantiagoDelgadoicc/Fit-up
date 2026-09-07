"""Sobrecarga progresiva: evaluar, aplicar y deshacer.

El contrato es deliberadamente asimétrico: el cliente pregunta *qué* puede
progresar y pide progresar *ejercicios*, pero nunca dice *cuánto*. El salto lo
calcula el motor en el servidor, con sus guardas, cada vez.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Depends, Query, status

from ...application.services import progression as svc
from .. import mappers, schemas
from ..deps import get_db
from ..deps import today as today_dep

router = APIRouter(tags=["progresión"])


@router.get("/rutinas/{routine_id}/progresion", response_model=schemas.RoutineProgressionOut)
def evaluate_routine(
    routine_id: int,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    """Veredicto para cada ejercicio, con su motivo aunque no se pueda progresar."""
    return mappers.routine_progression_out(svc.evaluate_routine(db, routine_id, today=today))


@router.post(
    "/rutinas/{routine_id}/progresion",
    response_model=schemas.ProgressionAppliedOut,
    status_code=status.HTTP_201_CREATED,
)
def apply_progression(
    routine_id: int,
    payload: schemas.ProgressionApplyIn,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    """Aplica las progresiones elegidas: una versión nueva y un evento por ejercicio.

    Se recalcula antes de escribir. Si algo dejó de ser seguro entre la
    pantalla y el botón, responde 409 con el motivo en vez de aplicarlo.
    """
    result = svc.apply(
        db, routine_id, exercise_slugs=payload.exercises, today=today, note=payload.note
    )
    return mappers.progression_applied_out(result)


@router.get("/progresion/listas", response_model=list[schemas.RoutineReadinessOut])
def readiness(db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    """Rutinas con algo que ofrecer. Lo que avisa en «Hoy»."""
    return svc.readiness(db, today=today)


@router.get("/progresiones", response_model=list[schemas.ProgressionEventOut])
def list_events(
    routine_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: sqlite3.Connection = Depends(get_db),
):
    return [
        mappers.progression_event_out(e)
        for e in svc.list_events(db, routine_id=routine_id, limit=limit)
    ]


@router.post(
    "/progresiones/{event_id}/deshacer",
    response_model=schemas.ProgressionAppliedOut,
    status_code=status.HTTP_201_CREATED,
)
def undo_progression(event_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Deshacer es avanzar: crea la versión que restaura el plan anterior."""
    return mappers.progression_applied_out(svc.undo(db, event_id))
