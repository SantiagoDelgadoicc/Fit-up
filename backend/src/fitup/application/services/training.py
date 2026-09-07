"""Casos de uso de entrenamiento: qué toca hoy, registrar, historial.

El caso central de Fit-Up no es registrar en vivo: es abrir la app el domingo y
anotar lo de la semana. Todo este módulo está diseñado alrededor de eso —
:func:`log_as_planned` existe para que registrar sea **un toque**, y
:func:`pending_days` para que ese toque sea fácil de encontrar.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta

from ...domain.compliance.day_state import DEFAULT_GRACE_DAYS, DayVerdict, resolve_day_state
from ...domain.enums import Actor, SessionOrigin, SessionStatus
from ...domain.models import PerformedExercise, PerformedSet, WorkoutSession
from ..errors import Conflict, Invalid
from ..repositories import history, planning
from ..views import CalendarDay, DayView, PendingDay, SessionDetail

MAX_RETROACTIVE_DAYS = 365


def grace_days(conn: sqlite3.Connection) -> int:
    value = history.get_setting(conn, "dias_gracia", DEFAULT_GRACE_DAYS)
    return int(value) if value is not None else DEFAULT_GRACE_DAYS


# --------------------------------------------------------------------------
# Consulta de un día
# --------------------------------------------------------------------------


def get_day(conn: sqlite3.Connection, day: Date, *, today: Date | None = None) -> DayView:
    today = today or Date.today()
    if day > today:
        raise Invalid("No se consulta el estado de un día futuro")

    scheduled = planning.scheduled_routine(conn, day)
    session = history.session_on(conn, day)
    exception = planning.get_exception(conn, day)

    verdict = _verdict(conn, day, today, scheduled, session, exception)

    planned = None
    if scheduled is not None:
        # La versión vigente **ese día**, no la de hoy: si la rutina se editó
        # el jueves, el martes tenía otro plan.
        planned = planning.get_version(conn, planning.version_at(conn, scheduled[0], day))

    return DayView(
        date=day,
        state=verdict.state,
        reason=verdict.reason,
        planned=planned,
        session=session,
        exception_reason=str(exception.reason) if exception else None,
    )


def _verdict(
    conn: sqlite3.Connection,
    day: Date,
    today: Date,
    scheduled: tuple[int, str] | None,
    session: SessionDetail | None,
    exception,
) -> DayVerdict:
    domain_session = None
    if session is not None:
        domain_session = WorkoutSession(
            date=session.date, status=session.status, origin=session.origin
        )
    return resolve_day_state(
        day,
        today=today,
        was_scheduled=scheduled is not None,
        session=domain_session,
        exception=exception,
        grace_days=grace_days(conn),
    )


def pending_days(conn: sqlite3.Connection, *, today: Date | None = None) -> list[PendingDay]:
    """Días programados, aún sin registrar y dentro de la ventana de gracia.

    Es la lista que la pantalla "Hoy" ofrece resolver de un toque.
    """
    today = today or Date.today()
    window = grace_days(conn)
    result: list[PendingDay] = []

    for offset in range(window + 1):
        day = today - timedelta(days=offset)
        scheduled = planning.scheduled_routine(conn, day)
        if scheduled is None:
            continue
        if history.session_on(conn, day) is not None:
            continue
        if planning.get_exception(conn, day) is not None:
            continue
        result.append(
            PendingDay(
                date=day,
                routine_id=scheduled[0],
                routine_name=scheduled[1],
                days_left=window - offset,
            )
        )
    return result


def calendar(
    conn: sqlite3.Connection, start: Date, end: Date, *, today: Date | None = None
) -> list[CalendarDay]:
    """Estados de un rango de días, con qué tocaba y qué se hizo.

    Carga sesiones y excepciones del rango de una vez: pintar un mes con una
    consulta por día serían decenas de viajes a la base de datos.
    """
    today = today or Date.today()
    if end > today:
        end = today
    if start > end:
        return []

    sessions = {s.date: s for s in history.sessions_between(conn, start, end)}
    exceptions = planning.exceptions_between(conn, start, end)
    window = grace_days(conn)

    days: list[CalendarDay] = []
    day = start
    while day <= end:
        scheduled = planning.scheduled_routine(conn, day)
        session = sessions.get(day)
        domain_session = None
        if session is not None:
            domain_session = WorkoutSession(
                date=session.date, status=session.status, origin=session.origin
            )
        verdict = resolve_day_state(
            day,
            today=today,
            was_scheduled=scheduled is not None,
            session=domain_session,
            exception=exceptions.get(day),
            grace_days=window,
        )
        days.append(
            CalendarDay(
                verdict=verdict,
                routine_id=scheduled[0] if scheduled else None,
                # El nombre de la sesion manda sobre el programado: si ese dia
                # se entreno otra cosa, el calendario debe decir lo que pasó.
                routine_name=(session.routine_name if session else None)
                or (scheduled[1] if scheduled else None),
                session_id=session.id if session else None,
            )
        )
        day += timedelta(days=1)
    return days


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------


def _check_date(day: Date, today: Date) -> None:
    if day > today:
        raise Invalid("No se pueden registrar entrenamientos en el futuro")
    if (today - day).days > MAX_RETROACTIVE_DAYS:
        raise Invalid(
            f"La fecha está a más de {MAX_RETROACTIVE_DAYS} días: "
            "probablemente sea un error de tecleo"
        )


def log_as_planned(
    conn: sqlite3.Connection,
    day: Date,
    *,
    today: Date | None = None,
    status: SessionStatus = SessionStatus.COMPLETED,
    perceived_effort: int | None = None,
    duration_min: int | None = None,
    notes: str | None = None,
    actor: Actor = Actor.USUARIO,
    idempotency_key: str | None = None,
) -> SessionDetail:
    """«Hice esta rutina»: registra el día tal y como estaba planificado.

    Es el camino de un solo toque. Las desviaciones se corrigen después
    editando la sesión, no rellenando un formulario antes de guardarla.
    """
    today = today or Date.today()
    _check_date(day, today)

    if idempotency_key:
        existing = history.session_by_key(conn, idempotency_key)
        if existing is not None:
            return existing

    scheduled = planning.scheduled_routine(conn, day)
    if scheduled is None:
        raise Invalid(
            f"El {day.isoformat()} no tenía ninguna rutina programada; "
            "usa el registro libre para anotar un entrenamiento extra"
        )
    if history.session_on(conn, day) is not None:
        raise Conflict(f"El {day.isoformat()} ya tiene un entrenamiento registrado")

    version_id = planning.version_at(conn, scheduled[0], day)
    plan = planning.load_exercises(conn, version_id)

    performed = tuple(
        PerformedExercise(
            exercise_slug=p.exercise_slug,
            position=p.position,
            sets=tuple(
                PerformedSet(
                    set_no=s.set_no,
                    reps=s.target_reps,
                    weight_kg=s.target_weight_kg,
                    time_s=s.target_time_s,
                    completed=True,
                    is_warmup=s.is_warmup,
                )
                for s in p.sets
            ),
        )
        for p in plan
    )

    session = WorkoutSession(
        date=day,
        status=status,
        origin=SessionOrigin.PLANIFICADA,
        exercises=performed,
        routine_version_id=version_id,
        perceived_effort=perceived_effort,
        duration_min=duration_min,
        notes=notes,
        logged_at=datetime.now().astimezone(),
        actor=actor,
    )
    session_id = history.create_session(conn, session, idempotency_key=idempotency_key)
    history.audit(
        conn,
        actor=actor,
        action="log_as_planned",
        payload={"date": day.isoformat(), "routine_id": scheduled[0], "session_id": session_id},
    )
    conn.commit()
    return history.get_session(conn, session_id)


def log_session(
    conn: sqlite3.Connection,
    *,
    day: Date,
    exercises: list[PerformedExercise],
    today: Date | None = None,
    status: SessionStatus = SessionStatus.COMPLETED,
    routine_id: int | None = None,
    perceived_effort: int | None = None,
    duration_min: int | None = None,
    notes: str | None = None,
    actor: Actor = Actor.USUARIO,
    idempotency_key: str | None = None,
) -> SessionDetail:
    """Registro libre: entrenamiento ad-hoc o con desviaciones respecto al plan."""
    today = today or Date.today()
    _check_date(day, today)

    if idempotency_key:
        existing = history.session_by_key(conn, idempotency_key)
        if existing is not None:
            return existing

    if status is not SessionStatus.SKIPPED and not exercises:
        raise Invalid("Un entrenamiento registrado necesita al menos un ejercicio")
    if history.session_on(conn, day) is not None:
        raise Conflict(f"El {day.isoformat()} ya tiene un entrenamiento registrado")

    scheduled = planning.scheduled_routine(conn, day)
    target_routine = routine_id or (scheduled[0] if scheduled else None)

    version_id = None
    origin = SessionOrigin.ADHOC
    if target_routine is not None:
        version_id = planning.version_at(conn, target_routine, day)
        origin = SessionOrigin.PLANIFICADA

    session = WorkoutSession(
        date=day,
        status=status,
        origin=origin,
        exercises=tuple(exercises),
        routine_version_id=version_id,
        perceived_effort=perceived_effort,
        duration_min=duration_min,
        notes=notes,
        logged_at=datetime.now().astimezone(),
        actor=actor,
    )
    session_id = history.create_session(conn, session, idempotency_key=idempotency_key)
    history.audit(
        conn,
        actor=actor,
        action="log_session",
        payload={"date": day.isoformat(), "session_id": session_id, "status": str(status)},
    )
    conn.commit()
    return history.get_session(conn, session_id)


def skip_day(
    conn: sqlite3.Connection,
    day: Date,
    *,
    today: Date | None = None,
    notes: str | None = None,
    actor: Actor = Actor.USUARIO,
) -> SessionDetail:
    """Declarar explícitamente que un día no se entrenó.

    Distinto de dejarlo sin registrar: esto es información, no ausencia de
    información, y pasa el día a MISSED sin esperar la ventana de gracia.
    """
    return log_session(
        conn,
        day=day,
        exercises=[],
        today=today,
        status=SessionStatus.SKIPPED,
        notes=notes,
        actor=actor,
    )


def delete_session(
    conn: sqlite3.Connection, session_id: int, *, actor: Actor = Actor.USUARIO
) -> None:
    history.get_session(conn, session_id)  # existencia
    history.delete_session(conn, session_id)
    history.audit(conn, actor=actor, action="delete_session", payload={"session_id": session_id})
    conn.commit()


def get_session(conn: sqlite3.Connection, session_id: int) -> SessionDetail:
    return history.get_session(conn, session_id)


def list_sessions(
    conn: sqlite3.Connection, *, limit: int = 50, offset: int = 0
) -> list[SessionDetail]:
    return history.list_sessions(conn, limit=limit, offset=offset)
