"""Persistencia de lo planificado: rutinas versionadas y calendario semanal."""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import datetime

from ...domain.enums import Actor
from ...domain.models import PlannedExercise, PlannedSet, ScheduleException, ScheduleSlot
from ..errors import NotFound
from ..views import RoutineDetail, RoutineSummary, WeekPlan
from . import catalog


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --------------------------------------------------------------------------
# Rutinas
# --------------------------------------------------------------------------


def list_routines(
    conn: sqlite3.Connection, *, include_archived: bool = False
) -> list[RoutineSummary]:
    """Rutinas con su versión más reciente y cuántos ejercicios tiene."""
    condition = "" if include_archived else "AND r.status <> 'archived'"
    rows = conn.execute(
        f"""
        SELECT r.id, r.name, r.status, r.created_at, v.version_no,
               (SELECT COUNT(*) FROM routine_exercise re
                 WHERE re.routine_version_id = v.id) AS n
          FROM routine r
          JOIN routine_version v ON v.routine_id = r.id
         WHERE v.version_no = (SELECT MAX(version_no) FROM routine_version
                                WHERE routine_id = r.id)
           {condition}
         ORDER BY r.name
        """
    ).fetchall()
    return [
        RoutineSummary(
            id=r["id"],
            name=r["name"],
            status=r["status"],
            version_no=r["version_no"],
            exercise_count=r["n"],
            created_at=_parse_dt(r["created_at"]),
        )
        for r in rows
    ]


def create_routine(
    conn: sqlite3.Connection,
    *,
    name: str,
    exercises: list[PlannedExercise],
    note: str | None = None,
    actor: Actor = Actor.USUARIO,
) -> int:
    cur = conn.execute(
        "INSERT INTO routine (name, status, created_at) VALUES (?, 'active', ?)",
        (name, _now()),
    )
    routine_id = int(cur.lastrowid)
    _insert_version(conn, routine_id, 1, exercises, note, actor)
    return routine_id


def create_version(
    conn: sqlite3.Connection,
    routine_id: int,
    *,
    exercises: list[PlannedExercise],
    note: str | None = None,
    actor: Actor = Actor.USUARIO,
) -> int:
    """Nueva versión de una rutina. **Nunca** se modifica la anterior (regla R1)."""
    row = conn.execute(
        "SELECT MAX(version_no) AS v FROM routine_version WHERE routine_id = ?",
        (routine_id,),
    ).fetchone()
    if row is None or row["v"] is None:
        raise NotFound(f"No existe la rutina {routine_id}")
    version_no = int(row["v"]) + 1
    _insert_version(conn, routine_id, version_no, exercises, note, actor)
    return version_no


def _insert_version(
    conn: sqlite3.Connection,
    routine_id: int,
    version_no: int,
    exercises: list[PlannedExercise],
    note: str | None,
    actor: Actor,
) -> int:
    cur = conn.execute(
        "INSERT INTO routine_version (routine_id, version_no, created_at, note, actor) "
        "VALUES (?, ?, ?, ?, ?)",
        (routine_id, version_no, _now(), note, str(actor)),
    )
    version_id = int(cur.lastrowid)

    for position, planned in enumerate(exercises):
        ex_id = catalog.exercise_id(conn, planned.exercise_slug)
        if ex_id is None:
            raise NotFound(f"No existe el ejercicio '{planned.exercise_slug}'")
        cur = conn.execute(
            "INSERT INTO routine_exercise "
            "(routine_version_id, exercise_id, position, rest_seconds, rule_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                version_id,
                ex_id,
                position,
                planned.rest_seconds,
                catalog.rule_id(conn, planned.rule_slug),
                planned.notes,
            ),
        )
        re_id = int(cur.lastrowid)
        for s in planned.sets:
            conn.execute(
                "INSERT INTO planned_set (routine_exercise_id, set_no, target_reps, "
                "target_reps_max, target_weight_kg, target_time_s, target_rir, is_warmup, "
                "to_failure) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    re_id,
                    s.set_no,
                    s.target_reps,
                    s.target_reps_max,
                    s.target_weight_kg,
                    s.target_time_s,
                    s.target_rir,
                    int(s.is_warmup),
                    int(s.to_failure),
                ),
            )
    return version_id


def get_routine(
    conn: sqlite3.Connection, routine_id: int, *, version_no: int | None = None
) -> RoutineDetail:
    if version_no is None:
        row = conn.execute(
            "SELECT r.id, r.name, r.status, v.id AS vid, v.version_no, v.created_at, v.note "
            "FROM routine r JOIN routine_version v ON v.routine_id = r.id "
            "WHERE r.id = ? ORDER BY v.version_no DESC LIMIT 1",
            (routine_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT r.id, r.name, r.status, v.id AS vid, v.version_no, v.created_at, v.note "
            "FROM routine r JOIN routine_version v ON v.routine_id = r.id "
            "WHERE r.id = ? AND v.version_no = ?",
            (routine_id, version_no),
        ).fetchone()

    if row is None:
        raise NotFound(f"No existe la rutina {routine_id}")
    return _detail_from(conn, row)


def get_version(conn: sqlite3.Connection, version_id: int) -> RoutineDetail:
    row = conn.execute(
        "SELECT r.id, r.name, r.status, v.id AS vid, v.version_no, v.created_at, v.note "
        "FROM routine_version v JOIN routine r ON r.id = v.routine_id WHERE v.id = ?",
        (version_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"No existe la versión de rutina {version_id}")
    return _detail_from(conn, row)


def _detail_from(conn: sqlite3.Connection, row: sqlite3.Row) -> RoutineDetail:
    return RoutineDetail(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        version_id=row["vid"],
        version_no=row["version_no"],
        created_at=_parse_dt(row["created_at"]),
        note=row["note"],
        exercises=tuple(load_exercises(conn, row["vid"])),
    )


def load_exercises(conn: sqlite3.Connection, version_id: int) -> list[PlannedExercise]:
    rows = conn.execute(
        "SELECT re.id, re.position, re.rest_seconds, re.notes, e.slug AS ex_slug, "
        "       r.slug AS rule_slug, e.default_rest_seconds "
        "FROM routine_exercise re "
        "JOIN exercise e ON e.id = re.exercise_id "
        "LEFT JOIN progression_rule r ON r.id = re.rule_id "
        "WHERE re.routine_version_id = ? ORDER BY re.position",
        (version_id,),
    ).fetchall()

    result: list[PlannedExercise] = []
    for r in rows:
        sets = conn.execute(
            "SELECT set_no, target_reps, target_reps_max, target_weight_kg, "
            "       target_time_s, target_rir, is_warmup, to_failure "
            "FROM planned_set WHERE routine_exercise_id = ? ORDER BY set_no",
            (r["id"],),
        ).fetchall()
        result.append(
            PlannedExercise(
                exercise_slug=r["ex_slug"],
                position=r["position"],
                rest_seconds=(
                    r["rest_seconds"]
                    if r["rest_seconds"] is not None
                    else r["default_rest_seconds"]
                ),
                rule_slug=r["rule_slug"],
                notes=r["notes"],
                sets=tuple(
                    PlannedSet(
                        set_no=s["set_no"],
                        target_reps=s["target_reps"],
                        target_reps_max=s["target_reps_max"],
                        target_weight_kg=s["target_weight_kg"],
                        target_time_s=s["target_time_s"],
                        target_rir=s["target_rir"],
                        is_warmup=bool(s["is_warmup"]),
                        to_failure=bool(s["to_failure"]),
                    )
                    for s in sets
                ),
            )
        )
    return result


def version_at(conn: sqlite3.Connection, routine_id: int, day: Date) -> int:
    """Versión vigente de la rutina en ``day``.

    Registrar el martes desde el domingo debe usar el plan que estaba vigente
    **el martes**, no el de hoy: es lo que hace fiable el registro retroactivo.
    Si la rutina se creó después, se usa la primera versión — mejor eso que
    negarse a registrar un entrenamiento que sí ocurrió.
    """
    row = conn.execute(
        "SELECT id FROM routine_version WHERE routine_id = ? AND date(created_at) <= ? "
        "ORDER BY version_no DESC LIMIT 1",
        (routine_id, day.isoformat()),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    row = conn.execute(
        "SELECT id FROM routine_version WHERE routine_id = ? ORDER BY version_no LIMIT 1",
        (routine_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"La rutina {routine_id} no tiene ninguna versión")
    return int(row["id"])


def archive_routine(conn: sqlite3.Connection, routine_id: int) -> None:
    """Archivar, nunca borrar: el historial referencia sus versiones."""
    cur = conn.execute("UPDATE routine SET status = 'archived' WHERE id = ?", (routine_id,))
    if cur.rowcount == 0:
        raise NotFound(f"No existe la rutina {routine_id}")
    conn.execute(
        "UPDATE schedule_slot SET active_to = ? WHERE routine_id = ? AND active_to IS NULL",
        (Date.today().isoformat(), routine_id),
    )


# --------------------------------------------------------------------------
# Calendario semanal
# --------------------------------------------------------------------------


def set_week(
    conn: sqlite3.Connection,
    assignments: dict[int, list[int]],
    *,
    effective_from: Date,
) -> None:
    """Fija la semana a partir de ``effective_from``.

    No reescribe el pasado: cierra los tramos vigentes y abre otros nuevos, de
    modo que un día de hace un mes siga sabiendo qué tocaba entonces (regla R3).
    """
    day_before = Date.fromordinal(effective_from.toordinal() - 1).isoformat()
    start = effective_from.isoformat()

    for weekday, routine_ids in assignments.items():
        if not 0 <= weekday <= 6:
            raise ValueError(f"weekday fuera de rango: {weekday}")

        # Primero se descartan los tramos que arrancaban en el corte o despues:
        # quedan completamente sustituidos, no hay nada que cerrar. Cerrarlos
        # produciria active_to < active_from y el CHECK del esquema lo rechaza,
        # que es exactamente lo que debe hacer.
        conn.execute(
            "DELETE FROM schedule_slot WHERE weekday = ? AND active_from >= ?",
            (weekday, start),
        )
        # Y solo entonces se cierra el tramo que venia de antes.
        conn.execute(
            "UPDATE schedule_slot SET active_to = ? "
            "WHERE weekday = ? AND active_from < ? "
            "  AND (active_to IS NULL OR active_to >= ?)",
            (day_before, weekday, start, start),
        )
        # El orden de inserción es el que el usuario dio, y `scheduled_routines`
        # lee por `id`: primero la de la mañana, después la de la tarde.
        for routine_id in routine_ids:
            conn.execute(
                "INSERT INTO schedule_slot (weekday, routine_id, active_from) VALUES (?, ?, ?)",
                (weekday, routine_id, start),
            )


def get_week(conn: sqlite3.Connection, at: Date) -> WeekPlan:
    rows = conn.execute(
        "SELECT s.weekday, s.routine_id, r.name FROM schedule_slot s "
        "JOIN routine r ON r.id = s.routine_id "
        "WHERE s.active_from <= ? AND (s.active_to IS NULL OR s.active_to >= ?) "
        "ORDER BY s.weekday, s.id",
        (at.isoformat(), at.isoformat()),
    ).fetchall()
    days: dict[int, list[int]] = {d: [] for d in range(7)}
    names: dict[int, list[str]] = {d: [] for d in range(7)}
    for r in rows:
        days[r["weekday"]].append(r["routine_id"])
        names[r["weekday"]].append(r["name"])
    return WeekPlan(effective_on=at, days=days, names=names)


def scheduled_routines(conn: sqlite3.Connection, day: Date) -> list[tuple[int, str]]:
    """Rutinas programadas ese día, según la planificación vigente entonces.

    Devuelve una lista porque un día puede tener más de una: calistenia por la
    mañana y pesas por la tarde son dos rutinas distintas, y fundirlas perdería
    el dato de cuál se hizo.

    El orden es el de creación del tramo (`id`), que es el que el usuario dio
    al planificar la semana: primero la mañana, luego la tarde.
    """
    rows = conn.execute(
        "SELECT s.routine_id, r.name FROM schedule_slot s "
        "JOIN routine r ON r.id = s.routine_id "
        "WHERE s.weekday = ? AND s.active_from <= ? "
        "  AND (s.active_to IS NULL OR s.active_to >= ?) "
        "ORDER BY s.id",
        (day.weekday(), day.isoformat(), day.isoformat()),
    ).fetchall()
    return [(row["routine_id"], row["name"]) for row in rows]


def list_slots(conn: sqlite3.Connection) -> list[ScheduleSlot]:
    rows = conn.execute(
        "SELECT weekday, routine_id, active_from, active_to FROM schedule_slot "
        "ORDER BY weekday, active_from"
    ).fetchall()
    return [
        ScheduleSlot(
            weekday=r["weekday"],
            routine_id=r["routine_id"],
            active_from=Date.fromisoformat(r["active_from"]),
            active_to=Date.fromisoformat(r["active_to"]) if r["active_to"] else None,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------
# Excepciones
# --------------------------------------------------------------------------


def set_exception(conn: sqlite3.Connection, exception: ScheduleException) -> None:
    conn.execute(
        "INSERT INTO schedule_exception (date, routine_id, reason, note) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET routine_id = excluded.routine_id, "
        "  reason = excluded.reason, note = excluded.note",
        (
            exception.date.isoformat(),
            exception.routine_id,
            str(exception.reason),
            exception.note,
        ),
    )


def clear_exception(conn: sqlite3.Connection, day: Date) -> None:
    conn.execute("DELETE FROM schedule_exception WHERE date = ?", (day.isoformat(),))


def get_exception(conn: sqlite3.Connection, day: Date) -> ScheduleException | None:
    from ...domain.enums import ExceptionReason

    row = conn.execute(
        "SELECT date, routine_id, reason, note FROM schedule_exception WHERE date = ?",
        (day.isoformat(),),
    ).fetchone()
    if row is None:
        return None
    return ScheduleException(
        date=Date.fromisoformat(row["date"]),
        reason=ExceptionReason(row["reason"]),
        routine_id=row["routine_id"],
        note=row["note"],
    )


def exceptions_between(
    conn: sqlite3.Connection, start: Date, end: Date
) -> dict[Date, ScheduleException]:
    from ...domain.enums import ExceptionReason

    rows = conn.execute(
        "SELECT date, routine_id, reason, note FROM schedule_exception WHERE date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return {
        Date.fromisoformat(r["date"]): ScheduleException(
            date=Date.fromisoformat(r["date"]),
            reason=ExceptionReason(r["reason"]),
            routine_id=r["routine_id"],
            note=r["note"],
        )
        for r in rows
    }
