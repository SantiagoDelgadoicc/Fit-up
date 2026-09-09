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
from ..views import CalendarDay, DayView, PendingDay, ScheduledRoutine, SessionDetail

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

    scheduled = planning.scheduled_routines(conn, day)
    sessions = history.sessions_on(conn, day)
    exception = planning.get_exception(conn, day)

    verdict = _verdict(conn, day, today, len(scheduled), sessions, exception)

    # Cada rutina se empareja con la sesión que la ejecutó. Lo que sobra son
    # entrenamientos extra: no había plan para ellos, pero cuentan igual.
    emparejadas: list[ScheduledRoutine] = []
    usadas: set[int] = set()
    for routine_id, name in scheduled:
        suya = next(
            (s for s in sessions if s.routine_id == routine_id and s.id not in usadas), None
        )
        if suya is not None:
            usadas.add(suya.id)
        # La versión vigente **ese día**, no la de hoy: si la rutina se editó
        # el jueves, el martes tenía otro plan.
        detail = planning.get_version(conn, planning.version_at(conn, routine_id, day))
        emparejadas.append(
            ScheduledRoutine(routine_id=routine_id, name=name, detail=detail, session=suya)
        )

    return DayView(
        date=day,
        state=verdict.state,
        reason=verdict.reason,
        scheduled=emparejadas,
        extra_sessions=[s for s in sessions if s.id not in usadas],
        exception_reason=str(exception.reason) if exception else None,
    )


def _verdict(
    conn: sqlite3.Connection,
    day: Date,
    today: Date,
    scheduled_count: int,
    sessions: list[SessionDetail],
    exception,
) -> DayVerdict:
    return resolve_day_state(
        day,
        today=today,
        scheduled_count=scheduled_count,
        sessions=[WorkoutSession(date=s.date, status=s.status, origin=s.origin) for s in sessions],
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
        scheduled = planning.scheduled_routines(conn, day)
        if not scheduled:
            continue
        if planning.get_exception(conn, day) is not None:
            continue

        # Una entrada por rutina pendiente, no por día: si la mañana está
        # registrada y la tarde no, lo que queda por hacer es la tarde.
        hechas = {s.routine_id for s in history.sessions_on(conn, day)}
        for routine_id, name in scheduled:
            if routine_id in hechas:
                continue
            result.append(
                PendingDay(
                    date=day,
                    routine_id=routine_id,
                    routine_name=name,
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

    # Un dia puede tener varias sesiones, asi que se agrupan por fecha.
    por_dia: dict[Date, list[SessionDetail]] = {}
    for sesion in history.sessions_between(conn, start, end):
        por_dia.setdefault(sesion.date, []).append(sesion)

    exceptions = planning.exceptions_between(conn, start, end)
    window = grace_days(conn)

    days: list[CalendarDay] = []
    day = start
    while day <= end:
        scheduled = planning.scheduled_routines(conn, day)
        del_dia = por_dia.get(day, [])
        verdict = resolve_day_state(
            day,
            today=today,
            scheduled_count=len(scheduled),
            sessions=[
                WorkoutSession(date=s.date, status=s.status, origin=s.origin) for s in del_dia
            ],
            exception=exceptions.get(day),
            grace_days=window,
        )
        # Lo entrenado manda sobre lo programado: si ese dia se hizo otra cosa,
        # el calendario debe decir lo que pasó, no lo que tocaba.
        hechas = [(s.routine_id, s.routine_name) for s in del_dia if s.routine_name]
        days.append(
            CalendarDay(
                verdict=verdict,
                routines=[(rid or 0, nombre) for rid, nombre in hechas] or scheduled,
                session_ids=[s.id for s in del_dia],
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


def _rutina_del_dia(conn: sqlite3.Connection, day: Date, routine_id: int | None) -> tuple[int, str]:
    """Elige qué rutina de las programadas ese día se está registrando.

    Con una sola no hay nada que elegir. Con varias hay que decir cuál: dar por
    hecho que es la primera registraría la mañana cuando el usuario acaba de
    hacer la tarde, y eso es peor que pedirle que lo diga.
    """
    programadas = planning.scheduled_routines(conn, day)
    if not programadas:
        raise Invalid(
            f"El {day.isoformat()} no tenía ninguna rutina programada; "
            "usa el registro libre para anotar un entrenamiento extra"
        )

    ya_hechas = {s.routine_id for s in history.sessions_on(conn, day)}

    if routine_id is not None:
        elegida = next((r for r in programadas if r[0] == routine_id), None)
        if elegida is None:
            nombres = ", ".join(f"{rid} ({nombre})" for rid, nombre in programadas)
            raise Invalid(
                f"La rutina {routine_id} no estaba programada el {day.isoformat()}. "
                f"Ese día tocaba: {nombres}"
            )
        if routine_id in ya_hechas:
            raise Conflict(f"La rutina '{elegida[1]}' ya está registrada el {day.isoformat()}")
        return elegida

    pendientes = [r for r in programadas if r[0] not in ya_hechas]
    if not pendientes:
        raise Conflict(f"El {day.isoformat()} ya tiene registradas todas sus rutinas")
    if len(pendientes) > 1:
        nombres = ", ".join(f"{rid} ({nombre})" for rid, nombre in pendientes)
        raise Invalid(
            f"El {day.isoformat()} tiene más de una rutina sin registrar. "
            f"Indica cuál con 'routine_id': {nombres}"
        )
    return pendientes[0]


def log_as_planned(
    conn: sqlite3.Connection,
    day: Date,
    *,
    routine_id: int | None = None,
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

    elegida = _rutina_del_dia(conn, day, routine_id)
    version_id = planning.version_at(conn, elegida[0], day)
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
        payload={"date": day.isoformat(), "routine_id": elegida[0], "session_id": session_id},
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

    # El registro libre no comprueba si el día ya tiene algo: entrenar dos
    # veces el mismo día es normal —calistenia por la mañana, pesas por la
    # tarde— y bloquearlo obligaría a mentir juntándolo todo en una sesión.
    scheduled = planning.scheduled_routines(conn, day)
    ya_hechas = {s.routine_id for s in history.sessions_on(conn, day)}
    pendientes = [r for r in scheduled if r[0] not in ya_hechas]
    # Sin rutina indicada se asocia a la primera del día que quede por hacer;
    # si no queda ninguna, es un entrenamiento extra y así se registra.
    target_routine = routine_id or (pendientes[0][0] if pendientes else None)

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
