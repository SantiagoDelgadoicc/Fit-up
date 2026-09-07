"""Entrenamiento: qué toca, registrar, calendario e historial."""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Query, Response, status

from ...application.services import training as svc
from ...domain.compliance.day_state import adherence
from .. import agent, mappers, schemas
from ..agent import Caller
from ..deps import get_db
from ..deps import today as today_dep

router = APIRouter(tags=["entrenamiento"])


@router.get("/hoy", response_model=schemas.DayOut)
def get_today(db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    return mappers.day_out(svc.get_day(db, today, today=today))


@router.get("/dias/{day}", response_model=schemas.DayOut)
def get_day(day: Date, db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    return mappers.day_out(svc.get_day(db, day, today=today))


@router.get("/pendientes", response_model=list[schemas.PendingDayOut])
def pending(db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    """Días programados y sin registrar, resolubles de un toque."""
    return svc.pending_days(db, today=today)


@router.get("/calendario", response_model=schemas.CalendarOut)
def calendar(
    start: Date,
    end: Date,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    days = svc.calendar(db, start, end, today=today)
    return schemas.CalendarOut(
        start=start,
        end=min(end, today),
        days=[
            schemas.DayStateOut(
                date=d.date,
                state=d.state,
                reason=d.reason,
                routine_name=d.routine_name,
                routine_id=d.routine_id,
                session_ids=d.session_ids,
            )
            for d in days
        ],
        # La adherencia se calcula sobre el veredicto del dominio: la regla de
        # qué estados computan vive ahí, no aquí.
        adherence=adherence([d.verdict for d in days]),
    )


@router.get("/calendario/{year}/{month}", response_model=schemas.CalendarOut)
def calendar_month(
    year: int,
    month: int,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    start = Date(year, month, 1)
    end = (Date(year + (month == 12), (month % 12) + 1, 1)) - timedelta(days=1)
    return calendar(start=start, end=end, db=db, today=today)


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------


@router.post(
    "/sesiones/como-planificado",
    response_model=schemas.SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def log_as_planned(
    payload: schemas.LogAsPlannedIn,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    caller: Caller = Depends(agent.write_sessions),
):
    """«Hice esta rutina»: copia el plan vigente **ese día** y lo da por hecho."""
    detail = svc.log_as_planned(
        db,
        payload.date,
        routine_id=payload.routine_id,
        today=today,
        actor=caller.actor,
        status=payload.status,
        perceived_effort=payload.perceived_effort,
        duration_min=payload.duration_min,
        notes=payload.notes,
        idempotency_key=idempotency_key,
    )
    return mappers.session_out(detail)


@router.post("/sesiones", response_model=schemas.SessionOut, status_code=status.HTTP_201_CREATED)
def log_session(
    payload: schemas.LogSessionIn,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    caller: Caller = Depends(agent.write_sessions),
):
    """Registro libre: entrenamiento extra o con desviaciones respecto al plan."""
    detail = svc.log_session(
        db,
        day=payload.date,
        exercises=mappers.to_performed_exercises(payload.exercises),
        today=today,
        actor=caller.actor,
        status=payload.status,
        routine_id=payload.routine_id,
        perceived_effort=payload.perceived_effort,
        duration_min=payload.duration_min,
        notes=payload.notes,
        idempotency_key=idempotency_key,
    )
    return mappers.session_out(detail)


@router.post(
    "/sesiones/no-realizado",
    response_model=schemas.SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def skip_day(
    payload: schemas.SkipDayIn,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
    caller: Caller = Depends(agent.write_sessions),
):
    """Declarar que un día no se entrenó: información, no ausencia de ella."""
    return mappers.session_out(
        svc.skip_day(db, payload.date, today=today, notes=payload.notes, actor=caller.actor)
    )


@router.get("/sesiones", response_model=list[schemas.SessionOut])
def list_sessions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    return [mappers.session_out(s) for s in svc.list_sessions(db, limit=limit, offset=offset)]


@router.get("/sesiones/{session_id}", response_model=schemas.SessionOut)
def get_session(session_id: int, db: sqlite3.Connection = Depends(get_db)):
    return mappers.session_out(svc.get_session(db, session_id))


@router.delete("/sesiones/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_sessions),
):
    svc.delete_session(db, session_id, actor=caller.actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
