"""Persistencia de los snapshots del ranking.

``muscle_score_snapshot`` es la única excepción a "lo derivable se calcula"
(regla R15), y lo es por un motivo concreto: sin ella no habría forma de
dibujar cómo ha evolucionado un rango, porque la fórmula solo sabe responder
"cuánto vales hoy". Es **caché**: lleva la ``formula_version`` con la que se
calculó y puede reconstruirse entera desde el historial.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from datetime import datetime

from ...domain.enums import Tier
from ...domain.ranking.v2 import MuscleScore
from ..views import ScorePoint


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save(
    conn: sqlite3.Connection,
    day: Date,
    scores: dict[str, MuscleScore],
    *,
    formula_version: str,
) -> int:
    """Guarda (o rehace) el snapshot de un día.

    ``ON CONFLICT`` en vez de fallar: recalcular un día ya guardado es una
    operación legítima —es caché— y debe sobrescribir sin ceremonia.
    """
    written = 0
    for slug, score in scores.items():
        row = conn.execute("SELECT id FROM muscle_group WHERE slug = ?", (slug,)).fetchone()
        if row is None:  # pragma: no cover - los slugs vienen del catálogo
            continue
        conn.execute(
            """
            INSERT INTO muscle_score_snapshot
                (date, muscle_id, formula_version, development_score, activity_score,
                 tier, inputs_json, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, muscle_id, formula_version) DO UPDATE SET
                development_score = excluded.development_score,
                activity_score    = excluded.activity_score,
                tier              = excluded.tier,
                inputs_json       = excluded.inputs_json,
                computed_at       = excluded.computed_at
            """,
            (
                day.isoformat(),
                row["id"],
                formula_version,
                score.development,
                score.activity,
                str(score.tier),
                json.dumps(
                    {"factors": score.factors, "notes": list(score.notes)}, ensure_ascii=False
                ),
                _now(),
            ),
        )
        written += 1
    return written


def last_snapshot_date(conn: sqlite3.Connection, *, formula_version: str) -> Date | None:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM muscle_score_snapshot WHERE formula_version = ?",
        (formula_version,),
    ).fetchone()
    return Date.fromisoformat(row["d"]) if row and row["d"] else None


def history(
    conn: sqlite3.Connection, muscle_slug: str, *, formula_version: str, limit: int = 52
) -> list[ScorePoint]:
    """Serie temporal del rango de un músculo, de la más antigua a la reciente."""
    rows = conn.execute(
        """
        SELECT s.date, s.development_score, s.activity_score, s.tier
          FROM muscle_score_snapshot s
          JOIN muscle_group m ON m.id = s.muscle_id
         WHERE m.slug = ? AND s.formula_version = ?
         ORDER BY s.date DESC LIMIT ?
        """,
        (muscle_slug, formula_version, limit),
    ).fetchall()
    points = [
        ScorePoint(
            date=Date.fromisoformat(r["date"]),
            development=r["development_score"],
            activity=r["activity_score"],
            tier=Tier(r["tier"]),
        )
        for r in rows
    ]
    points.reverse()
    return points
