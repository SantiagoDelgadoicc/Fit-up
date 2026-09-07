"""Rutinas y planificación semanal."""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Body, Depends, Response, status

from ...application.services import planning as svc
from ...domain.enums import ExceptionReason
from ...domain.models import ScheduleException
from .. import agent, mappers, schemas
from ..agent import Caller
from ..deps import get_db
from ..deps import today as today_dep

router = APIRouter(tags=["rutinas"])


@router.get("/rutinas", response_model=list[schemas.RoutineSummaryOut])
def list_routines(include_archived: bool = False, db: sqlite3.Connection = Depends(get_db)):
    return svc.list_routines(db, include_archived=include_archived)


@router.post("/rutinas", response_model=schemas.RoutineOut, status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: schemas.RoutineIn,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_routines),
):
    detail = svc.create_routine(
        db,
        name=payload.name,
        exercises=mappers.to_planned_exercises(payload.exercises),
        note=payload.note,
        actor=caller.actor,
    )
    return mappers.routine_out(detail)


@router.get("/rutinas/{routine_id}", response_model=schemas.RoutineOut)
def get_routine(
    routine_id: int, version: int | None = None, db: sqlite3.Connection = Depends(get_db)
):
    return mappers.routine_out(svc.get_routine(db, routine_id, version_no=version))


@router.put("/rutinas/{routine_id}", response_model=schemas.RoutineOut)
def update_routine(
    routine_id: int,
    payload: schemas.RoutineUpdate,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_routines),
):
    """Editar **crea una versión nueva**; la anterior queda intacta (regla R1)."""
    detail = svc.update_routine(
        db,
        routine_id,
        name=payload.name,
        exercises=mappers.to_planned_exercises(payload.exercises),
        note=payload.note,
        actor=caller.actor,
    )
    return mappers.routine_out(detail)


@router.delete("/rutinas/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_routine(
    routine_id: int,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_routines),
):
    """Archiva, no borra: el historial referencia sus versiones."""
    svc.archive_routine(db, routine_id, actor=caller.actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Semana
# --------------------------------------------------------------------------


@router.get("/semana", response_model=schemas.WeekOut, tags=["planificación"])
def get_week(
    at: Date | None = None,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    return svc.get_week(db, at or today)


@router.put("/semana", response_model=schemas.WeekOut, tags=["planificación"])
def set_week(
    payload: schemas.WeekIn,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
    caller: Caller = Depends(agent.write_routines),
):
    """Fija la semana desde una fecha. No reescribe el pasado (regla R3)."""
    return svc.set_week(
        db,
        payload.days,
        effective_from=payload.effective_from or today,
        actor=caller.actor,
    )


# --------------------------------------------------------------------------
# Excepciones
# --------------------------------------------------------------------------


@router.put("/excepciones/{day}", status_code=status.HTTP_204_NO_CONTENT, tags=["planificación"])
def set_exception(
    day: Date,
    payload: schemas.ExceptionIn = Body(...),
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_routines),
):
    """Un día excusado no es un incumplimiento (regla R4)."""
    svc.set_exception(
        db,
        ScheduleException(
            date=day,
            reason=ExceptionReason(payload.reason),
            routine_id=payload.routine_id,
            note=payload.note,
        ),
        actor=caller.actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/excepciones/{day}", status_code=status.HTTP_204_NO_CONTENT, tags=["planificación"])
def clear_exception(
    day: Date,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_routines),
):
    svc.clear_exception(db, day, actor=caller.actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
