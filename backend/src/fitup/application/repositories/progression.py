"""Persistencia de las progresiones aplicadas.

Un ``progression_event`` es historia auditable: nunca se borra ni se edita.
Deshacer produce **otro** evento que revierte al anterior y lo marca como
revertido, de modo que el rastro completo sigue ahí (regla R14, ADR-0004).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from datetime import datetime

from ...domain.enums import Actor
from ..errors import NotFound
from ..views import ProgressionEventView
from . import catalog


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


#: Eventos que son la reversión de otro. Se excluyen del cooldown: si una
#: progresión se deshizo, lo que queda vigente es el plan anterior, y esperar
#: una semana por un cambio que ya no está sería castigar por nada.
_REVERSALS = (
    "SELECT reverted_by_event_id FROM progression_event WHERE reverted_by_event_id IS NOT NULL"
)


def record(
    conn: sqlite3.Connection,
    *,
    exercise_slug: str,
    routine_id: int,
    from_version_id: int | None,
    to_version_id: int,
    rule_slug: str,
    before: dict,
    after: dict,
    rationale: str,
    actor: Actor = Actor.USUARIO,
) -> int:
    exercise_id = catalog.exercise_id(conn, exercise_slug)
    if exercise_id is None:
        raise NotFound(f"No existe el ejercicio '{exercise_slug}'")
    cur = conn.execute(
        "INSERT INTO progression_event (exercise_id, routine_id, from_version_id, "
        "to_version_id, rule_slug, before_json, after_json, rationale, applied_at, actor) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            exercise_id,
            routine_id,
            from_version_id,
            to_version_id,
            rule_slug,
            json.dumps(before, ensure_ascii=False),
            json.dumps(after, ensure_ascii=False),
            rationale,
            _now(),
            str(actor),
        ),
    )
    return int(cur.lastrowid)


def mark_reverted(conn: sqlite3.Connection, event_id: int, *, by_event_id: int) -> None:
    conn.execute(
        "UPDATE progression_event SET reverted_by_event_id = ? WHERE id = ?",
        (by_event_id, event_id),
    )


def last_applied_on(conn: sqlite3.Connection, exercise_slug: str) -> Date | None:
    """Fecha de la última progresión **vigente** de un ejercicio, o ``None``.

    Alimenta el cooldown de las guardas. Cuenta el ejercicio en todas las
    rutinas: subir la carga cansa al músculo venga de donde venga el estímulo.
    """
    row = conn.execute(
        f"""
        SELECT p.applied_at FROM progression_event p
          JOIN exercise e ON e.id = p.exercise_id
         WHERE e.slug = ?
           AND p.reverted_by_event_id IS NULL
           AND p.id NOT IN ({_REVERSALS})
         ORDER BY p.applied_at DESC LIMIT 1
        """,
        (exercise_slug,),
    ).fetchone()
    return datetime.fromisoformat(row["applied_at"]).date() if row else None


_EVENT_SELECT = f"""
    SELECT p.id, p.routine_id, p.from_version_id, p.to_version_id, p.rule_slug,
           p.before_json, p.after_json, p.rationale, p.applied_at, p.actor,
           p.reverted_by_event_id,
           e.slug AS exercise_slug, e.name AS exercise_name,
           r.name AS routine_name,
           fv.version_no AS from_version_no, tv.version_no AS to_version_no,
           (p.id IN ({_REVERSALS})) AS is_reversal
      FROM progression_event p
      JOIN exercise e ON e.id = p.exercise_id
      JOIN routine  r ON r.id = p.routine_id
      LEFT JOIN routine_version fv ON fv.id = p.from_version_id
      LEFT JOIN routine_version tv ON tv.id = p.to_version_id
"""


def _to_view(row: sqlite3.Row) -> ProgressionEventView:
    return ProgressionEventView(
        id=row["id"],
        exercise_slug=row["exercise_slug"],
        exercise_name=row["exercise_name"],
        routine_id=row["routine_id"],
        routine_name=row["routine_name"],
        rule_slug=row["rule_slug"],
        rationale=row["rationale"],
        applied_at=datetime.fromisoformat(row["applied_at"]),
        actor=row["actor"],
        before=json.loads(row["before_json"]),
        after=json.loads(row["after_json"]),
        from_version_no=row["from_version_no"],
        to_version_no=row["to_version_no"],
        reverted=row["reverted_by_event_id"] is not None,
        is_reversal=bool(row["is_reversal"]),
    )


def get_event(conn: sqlite3.Connection, event_id: int) -> ProgressionEventView:
    row = conn.execute(f"{_EVENT_SELECT} WHERE p.id = ?", (event_id,)).fetchone()
    if row is None:
        raise NotFound(f"No existe la progresión {event_id}")
    return _to_view(row)


def list_events(
    conn: sqlite3.Connection, *, routine_id: int | None = None, limit: int = 50
) -> list[ProgressionEventView]:
    where = "WHERE p.routine_id = ?" if routine_id is not None else ""
    params: tuple = (routine_id, limit) if routine_id is not None else (limit,)
    rows = conn.execute(
        f"{_EVENT_SELECT} {where} ORDER BY p.applied_at DESC, p.id DESC LIMIT ?", params
    ).fetchall()
    return [_to_view(r) for r in rows]
