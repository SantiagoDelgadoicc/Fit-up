"""Casos de uso de planificación: crear y editar rutinas, organizar la semana."""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from ...domain.enums import Actor
from ...domain.models import PlannedExercise, PlannedSet, ScheduleException
from ..errors import Invalid, NotFound
from ..repositories import catalog, history, planning
from ..views import RoutineDetail, RoutineSummary, WeekPlan


def build_sets(
    *,
    count: int,
    reps: int | None = None,
    reps_max: int | None = None,
    weight_kg: float | None = None,
    time_s: int | None = None,
    rir: int | None = None,
    warmup: int = 0,
    to_failure: bool = False,
) -> tuple[PlannedSet, ...]:
    """Genera las filas de series a partir de una prescripción compacta.

    La UI dice "3x15" y aquí se convierten en tres filas explícitas. El modelo
    guarda series individuales (decisión d7), pero nadie debería escribirlas a
    mano.
    """
    if count < 1:
        raise Invalid("Una serie planificada como mínimo")
    if reps is None and time_s is None and not to_failure:
        raise Invalid("Cada serie necesita repeticiones, tiempo objetivo, o ir al fallo")
    if to_failure and reps is not None:
        raise Invalid(
            "Una serie al fallo no lleva repeticiones objetivo: o se llega al "
            "fallo, o se llega al número"
        )
    if reps_max is not None and reps is not None and reps_max < reps:
        raise Invalid("El máximo de repeticiones no puede ser menor que el objetivo")

    sets: list[PlannedSet] = []
    for i in range(warmup):
        sets.append(
            PlannedSet(
                set_no=i + 1,
                # El calentamiento nunca va al fallo, aunque la serie efectiva
                # sí: calentar hasta no poder más deja sin nada el trabajo.
                target_reps=reps,
                target_time_s=time_s,
                # Se propone a la mitad de la carga; es un punto de partida
                # editable, no una prescripción.
                target_weight_kg=round(weight_kg / 2, 2) if weight_kg else None,
                is_warmup=True,
            )
        )
    for i in range(count):
        sets.append(
            PlannedSet(
                set_no=warmup + i + 1,
                target_reps=reps,
                target_reps_max=reps_max,
                target_weight_kg=weight_kg,
                target_time_s=time_s,
                target_rir=rir,
                to_failure=to_failure,
            )
        )
    return tuple(sets)


def _validate(conn: sqlite3.Connection, exercises: list[PlannedExercise]) -> None:
    if not exercises:
        raise Invalid("Una rutina necesita al menos un ejercicio")

    seen: set[str] = set()
    for planned in exercises:
        exercise = catalog.get_exercise(conn, planned.exercise_slug)
        if exercise is None:
            raise NotFound(f"No existe el ejercicio '{planned.exercise_slug}'")
        if planned.exercise_slug in seen:
            raise Invalid(f"El ejercicio '{planned.exercise_slug}' está repetido en la rutina")
        seen.add(planned.exercise_slug)

        if not planned.sets:
            raise Invalid(f"'{exercise.name}' no tiene ninguna serie")
        numbers = [s.set_no for s in planned.sets]
        if len(set(numbers)) != len(numbers):
            raise Invalid(f"'{exercise.name}' tiene números de serie repetidos")

        if planned.rule_slug and catalog.get_rule(conn, planned.rule_slug) is None:
            raise NotFound(f"No existe la regla de progresión '{planned.rule_slug}'")


def create_routine(
    conn: sqlite3.Connection,
    *,
    name: str,
    exercises: list[PlannedExercise],
    note: str | None = None,
    actor: Actor = Actor.USUARIO,
) -> RoutineDetail:
    if not name.strip():
        raise Invalid("La rutina necesita un nombre")
    _validate(conn, exercises)

    routine_id = planning.create_routine(
        conn, name=name.strip(), exercises=exercises, note=note, actor=actor
    )
    history.audit(
        conn,
        actor=actor,
        action="create_routine",
        payload={"routine_id": routine_id, "name": name.strip()},
    )
    conn.commit()
    return planning.get_routine(conn, routine_id)


def update_routine(
    conn: sqlite3.Connection,
    routine_id: int,
    *,
    exercises: list[PlannedExercise],
    name: str | None = None,
    note: str | None = None,
    actor: Actor = Actor.USUARIO,
) -> RoutineDetail:
    """Editar una rutina crea una versión nueva; la anterior queda intacta.

    Es lo que permite que una sesión de hace tres meses siga describiendo lo
    que realmente estaba planificado entonces (regla R2).
    """
    planning.get_routine(conn, routine_id)  # existencia
    _validate(conn, exercises)

    if name is not None:
        if not name.strip():
            raise Invalid("La rutina necesita un nombre")
        conn.execute("UPDATE routine SET name = ? WHERE id = ?", (name.strip(), routine_id))

    planning.create_version(conn, routine_id, exercises=exercises, note=note, actor=actor)
    history.audit(
        conn, actor=actor, action="update_routine", payload={"routine_id": routine_id, "name": name}
    )
    conn.commit()
    return planning.get_routine(conn, routine_id)


def get_routine(
    conn: sqlite3.Connection, routine_id: int, *, version_no: int | None = None
) -> RoutineDetail:
    return planning.get_routine(conn, routine_id, version_no=version_no)


def list_routines(
    conn: sqlite3.Connection, *, include_archived: bool = False
) -> list[RoutineSummary]:
    return planning.list_routines(conn, include_archived=include_archived)


def archive_routine(
    conn: sqlite3.Connection, routine_id: int, *, actor: Actor = Actor.USUARIO
) -> None:
    planning.archive_routine(conn, routine_id)
    history.audit(conn, actor=actor, action="archive_routine", payload={"routine_id": routine_id})
    conn.commit()


# --------------------------------------------------------------------------
# Semana
# --------------------------------------------------------------------------


def set_week(
    conn: sqlite3.Connection,
    assignments: dict[int, list[int]],
    *,
    effective_from: Date,
    actor: Actor = Actor.USUARIO,
) -> WeekPlan:
    for weekday, routine_ids in assignments.items():
        if not 0 <= weekday <= 6:
            raise Invalid(f"Día de la semana inválido: {weekday}")
        if len(set(routine_ids)) != len(routine_ids):
            raise Invalid(
                f"El día {weekday} repite alguna rutina. Para hacerla dos veces "
                "el mismo día, duplícala con otro nombre."
            )
        for routine_id in routine_ids:
            planning.get_routine(conn, routine_id)  # existencia

    planning.set_week(conn, assignments, effective_from=effective_from)
    history.audit(
        conn,
        actor=actor,
        action="set_week",
        payload={"days": assignments, "effective_from": effective_from},
    )
    conn.commit()
    return planning.get_week(conn, effective_from)


def get_week(conn: sqlite3.Connection, at: Date) -> WeekPlan:
    return planning.get_week(conn, at)


def set_exception(
    conn: sqlite3.Connection, exception: ScheduleException, *, actor: Actor = Actor.USUARIO
) -> None:
    planning.set_exception(conn, exception)
    history.audit(
        conn,
        actor=actor,
        action="set_exception",
        payload={"date": exception.date, "reason": str(exception.reason)},
    )
    conn.commit()


def clear_exception(conn: sqlite3.Connection, day: Date, *, actor: Actor = Actor.USUARIO) -> None:
    planning.clear_exception(conn, day)
    history.audit(conn, actor=actor, action="clear_exception", payload={"date": day})
    conn.commit()
