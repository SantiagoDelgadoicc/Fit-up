"""Persistencia de lo realizado: sesiones, peso corporal y ajustes."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime

from ...domain.enums import Actor, SessionOrigin, SessionStatus
from ...domain.models import PerformedExercise, PerformedSet, WorkoutSession
from ..errors import Conflict, NotFound
from ..views import SessionDetail
from . import catalog


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Sesiones
# --------------------------------------------------------------------------


def create_session(
    conn: sqlite3.Connection,
    session: WorkoutSession,
    *,
    idempotency_key: str | None = None,
) -> int:
    logged_at = (session.logged_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    try:
        cur = conn.execute(
            "INSERT INTO workout_session (date, routine_version_id, origin, status, "
            "perceived_effort, duration_min, notes, logged_at, actor, idempotency_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session.date.isoformat(),
                session.routine_version_id,
                str(session.origin),
                str(session.status),
                session.perceived_effort,
                session.duration_min,
                session.notes,
                logged_at,
                str(session.actor),
                idempotency_key,
            ),
        )
    except sqlite3.IntegrityError as exc:
        # La clave de idempotencia es la única restricción UNIQUE que puede
        # chocar aquí: un agente reintentando no debe duplicar la sesión.
        if idempotency_key is not None and "idempotency_key" in str(exc):
            raise Conflict(f"Ya existe una sesión con la clave '{idempotency_key}'") from exc
        raise

    session_id = int(cur.lastrowid)
    for position, performed in enumerate(session.exercises):
        ex_id = catalog.exercise_id(conn, performed.exercise_slug)
        if ex_id is None:
            raise NotFound(f"No existe el ejercicio '{performed.exercise_slug}'")
        cur = conn.execute(
            "INSERT INTO session_exercise (session_id, exercise_id, position, notes) "
            "VALUES (?, ?, ?, ?)",
            (session_id, ex_id, position, performed.notes),
        )
        se_id = int(cur.lastrowid)
        for s in performed.sets:
            conn.execute(
                "INSERT INTO session_set (session_exercise_id, set_no, reps, weight_kg, "
                "time_s, rir, completed, is_warmup) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    se_id,
                    s.set_no,
                    s.reps,
                    s.weight_kg,
                    s.time_s,
                    s.rir,
                    int(s.completed),
                    int(s.is_warmup),
                ),
            )
    return session_id


def session_by_key(conn: sqlite3.Connection, key: str) -> SessionDetail | None:
    row = conn.execute(
        "SELECT id FROM workout_session WHERE idempotency_key = ?", (key,)
    ).fetchone()
    return get_session(conn, row["id"]) if row else None


_SESSION_SELECT = """
    SELECT s.id, s.date, s.origin, s.status, s.perceived_effort, s.duration_min,
           s.notes, s.logged_at, s.routine_version_id,
           v.version_no, v.routine_id, r.name AS routine_name
      FROM workout_session s
      LEFT JOIN routine_version v ON v.id = s.routine_version_id
      LEFT JOIN routine         r ON r.id = v.routine_id
"""


def _to_detail(conn: sqlite3.Connection, row: sqlite3.Row) -> SessionDetail:
    return SessionDetail(
        id=row["id"],
        date=Date.fromisoformat(row["date"]),
        status=SessionStatus(row["status"]),
        origin=SessionOrigin(row["origin"]),
        exercises=tuple(load_exercises(conn, row["id"])),
        routine_id=row["routine_id"],
        routine_name=row["routine_name"],
        routine_version_id=row["routine_version_id"],
        routine_version_no=row["version_no"],
        perceived_effort=row["perceived_effort"],
        duration_min=row["duration_min"],
        notes=row["notes"],
        logged_at=datetime.fromisoformat(row["logged_at"]),
    )


def get_session(conn: sqlite3.Connection, session_id: int) -> SessionDetail:
    row = conn.execute(f"{_SESSION_SELECT} WHERE s.id = ?", (session_id,)).fetchone()
    if row is None:
        raise NotFound(f"No existe la sesión {session_id}")
    return _to_detail(conn, row)


def session_on(conn: sqlite3.Connection, day: Date) -> SessionDetail | None:
    row = conn.execute(
        f"{_SESSION_SELECT} WHERE s.date = ? ORDER BY s.id DESC LIMIT 1",
        (day.isoformat(),),
    ).fetchone()
    return _to_detail(conn, row) if row else None


def sessions_between(conn: sqlite3.Connection, start: Date, end: Date) -> list[SessionDetail]:
    rows = conn.execute(
        f"{_SESSION_SELECT} WHERE s.date BETWEEN ? AND ? ORDER BY s.date DESC, s.id DESC",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [_to_detail(conn, r) for r in rows]


def list_sessions(
    conn: sqlite3.Connection, *, limit: int = 50, offset: int = 0
) -> list[SessionDetail]:
    rows = conn.execute(
        f"{_SESSION_SELECT} ORDER BY s.date DESC, s.id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_to_detail(conn, r) for r in rows]


def load_exercises(conn: sqlite3.Connection, session_id: int) -> list[PerformedExercise]:
    rows = conn.execute(
        "SELECT se.id, se.position, se.notes, e.slug FROM session_exercise se "
        "JOIN exercise e ON e.id = se.exercise_id "
        "WHERE se.session_id = ? ORDER BY se.position",
        (session_id,),
    ).fetchall()

    result: list[PerformedExercise] = []
    for r in rows:
        sets = conn.execute(
            "SELECT set_no, reps, weight_kg, time_s, rir, completed, is_warmup "
            "FROM session_set WHERE session_exercise_id = ? ORDER BY set_no",
            (r["id"],),
        ).fetchall()
        result.append(
            PerformedExercise(
                exercise_slug=r["slug"],
                position=r["position"],
                notes=r["notes"],
                sets=tuple(
                    PerformedSet(
                        set_no=s["set_no"],
                        reps=s["reps"],
                        weight_kg=s["weight_kg"],
                        time_s=s["time_s"],
                        rir=s["rir"],
                        completed=bool(s["completed"]),
                        is_warmup=bool(s["is_warmup"]),
                    )
                    for s in sets
                ),
            )
        )
    return result


def delete_session(conn: sqlite3.Connection, session_id: int) -> None:
    cur = conn.execute("DELETE FROM workout_session WHERE id = ?", (session_id,))
    if cur.rowcount == 0:
        raise NotFound(f"No existe la sesión {session_id}")


def exercise_history(
    conn: sqlite3.Connection, exercise_slug: str, *, limit: int = 20
) -> list[tuple[Date, PerformedExercise]]:
    """Ejecuciones pasadas de un ejercicio, de la más antigua a la más reciente.

    Es exactamente lo que consume el motor de progresión en F3.
    """
    rows = conn.execute(
        "SELECT s.date, se.id, se.position, se.notes FROM session_exercise se "
        "JOIN workout_session s ON s.id = se.session_id "
        "JOIN exercise e ON e.id = se.exercise_id "
        "WHERE e.slug = ? AND s.status <> 'skipped' "
        "ORDER BY s.date DESC, s.id DESC LIMIT ?",
        (exercise_slug, limit),
    ).fetchall()

    result: list[tuple[Date, PerformedExercise]] = []
    for r in rows:
        sets = conn.execute(
            "SELECT set_no, reps, weight_kg, time_s, rir, completed, is_warmup "
            "FROM session_set WHERE session_exercise_id = ? ORDER BY set_no",
            (r["id"],),
        ).fetchall()
        result.append(
            (
                Date.fromisoformat(r["date"]),
                PerformedExercise(
                    exercise_slug=exercise_slug,
                    position=r["position"],
                    notes=r["notes"],
                    sets=tuple(
                        PerformedSet(
                            set_no=s["set_no"],
                            reps=s["reps"],
                            weight_kg=s["weight_kg"],
                            time_s=s["time_s"],
                            rir=s["rir"],
                            completed=bool(s["completed"]),
                            is_warmup=bool(s["is_warmup"]),
                        )
                        for s in sets
                    ),
                ),
            )
        )
    result.reverse()
    return result


# --------------------------------------------------------------------------
# Peso corporal
# --------------------------------------------------------------------------


def set_bodyweight(conn: sqlite3.Connection, day: Date, weight_kg: float) -> None:
    conn.execute(
        "INSERT INTO bodyweight_log (date, weight_kg) VALUES (?, ?) "
        "ON CONFLICT(date) DO UPDATE SET weight_kg = excluded.weight_kg",
        (day.isoformat(), weight_kg),
    )


def bodyweight_at(conn: sqlite3.Connection, day: Date) -> float | None:
    """Peso vigente en una fecha: el último registrado en o antes de ese día.

    Devuelve ``None`` si no hay ninguno. Las métricas que dependen del peso
    corporal deben declarar que no pueden calcularse, no suponer un valor.
    """
    row = conn.execute(
        "SELECT weight_kg FROM bodyweight_log WHERE date <= ? ORDER BY date DESC LIMIT 1",
        (day.isoformat(),),
    ).fetchone()
    if row is not None:
        return float(row["weight_kg"])

    # Sin registro anterior, el primero posterior es mejor estimación que nada,
    # y se usa solo para fechas previas al inicio del seguimiento.
    row = conn.execute("SELECT weight_kg FROM bodyweight_log ORDER BY date LIMIT 1").fetchone()
    return float(row["weight_kg"]) if row else None


def bodyweight_history(conn: sqlite3.Connection) -> list[tuple[Date, float]]:
    rows = conn.execute("SELECT date, weight_kg FROM bodyweight_log ORDER BY date").fetchall()
    return [(Date.fromisoformat(r["date"]), float(r["weight_kg"])) for r in rows]


# --------------------------------------------------------------------------
# Ajustes
# --------------------------------------------------------------------------


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value_json FROM settings").fetchall()
    return {r["key"]: json.loads(r["value_json"]) for r in rows}


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else default


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, "
        "  updated_at = excluded.updated_at",
        (key, json.dumps(value, ensure_ascii=False), _now()),
    )


# --------------------------------------------------------------------------
# Auditoría
# --------------------------------------------------------------------------


def audit(
    conn: sqlite3.Connection,
    *,
    actor: Actor,
    action: str,
    payload: dict | None = None,
    result: str = "ok",
    error: str | None = None,
) -> None:
    """Registra una operación.

    En F1 solo lo usan las escrituras del usuario, pero la tabla existe desde
    el principio: cuando llegue el agente (F6), la traza tiene que estar ya,
    no empezar entonces.
    """
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, payload_json, result, error) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            _now(),
            str(actor),
            action,
            json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            result,
            error,
        ),
    )


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Una línea del registro, tal cual quedó escrita."""

    id: int
    ts: str
    actor: str
    action: str
    payload: dict | None
    result: str
    error: str | None


def list_audit(
    conn: sqlite3.Connection,
    *,
    actor: Actor | None = None,
    result: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[AuditEntry]:
    """Últimas operaciones registradas, de la más reciente hacia atrás.

    Existe para poder responder «¿qué tocó el agente ayer?». Sin lectura, la
    tabla de auditoría es un cajón cerrado: se escribe y no sirve de nada
    (ADR-0004 §2).
    """
    clauses: list[str] = []
    params: list[object] = []
    if actor is not None:
        clauses.append("actor = ?")
        params.append(str(actor))
    if result is not None:
        clauses.append("result = ?")
        params.append(result)
    if since is not None:
        clauses.append("ts >= ?")
        params.append(since)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT id, ts, actor, action, payload_json, result, error FROM audit_log "
        f"{where} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()
    return [
        AuditEntry(
            id=r["id"],
            ts=r["ts"],
            actor=r["actor"],
            action=r["action"],
            payload=json.loads(r["payload_json"]) if r["payload_json"] else None,
            result=r["result"],
            error=r["error"],
        )
        for r in rows
    ]
