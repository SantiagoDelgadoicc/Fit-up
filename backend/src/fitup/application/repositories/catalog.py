"""Acceso al catálogo: músculos, ejercicios y reglas de progresión."""

from __future__ import annotations

import json
import sqlite3

from ...domain.enums import LoadType, Modality, MuscleRole, Strategy
from ...domain.models import (
    Exercise,
    Guards,
    MuscleGroup,
    MuscleLink,
    ProgressionRule,
)


def list_muscles(conn: sqlite3.Connection) -> list[MuscleGroup]:
    rows = conn.execute(
        "SELECT slug, name, region, body_view, svg_key, display_order "
        "FROM muscle_group ORDER BY display_order, name"
    ).fetchall()
    return [
        MuscleGroup(
            slug=r["slug"],
            name=r["name"],
            region=r["region"],
            body_view=r["body_view"],
            svg_key=r["svg_key"],
            display_order=r["display_order"],
        )
        for r in rows
    ]


_EXERCISE_COLUMNS = """
    e.id, e.slug, e.name, e.modality, e.load_type, e.load_factor,
    e.is_unilateral, e.equipment, e.default_rest_seconds,
    r.slug  AS rule_slug,
    v.slug  AS variant_slug
"""

_EXERCISE_FROM = """
    FROM exercise e
    LEFT JOIN progression_rule r ON r.id = e.default_rule_id
    LEFT JOIN exercise         v ON v.id = e.next_variant_id
"""


def _muscles_by_exercise(conn: sqlite3.Connection) -> dict[int, list[MuscleLink]]:
    """Todos los vínculos de una vez: evita una consulta por ejercicio."""
    rows = conn.execute(
        "SELECT em.exercise_id, m.slug, em.role "
        "FROM exercise_muscle em JOIN muscle_group m ON m.id = em.muscle_id"
    ).fetchall()
    grouped: dict[int, list[MuscleLink]] = {}
    for r in rows:
        grouped.setdefault(r["exercise_id"], []).append(
            MuscleLink(r["slug"], MuscleRole(r["role"]))
        )
    return grouped


def _to_exercise(row: sqlite3.Row, links: list[MuscleLink]) -> Exercise:
    return Exercise(
        slug=row["slug"],
        name=row["name"],
        modality=Modality(row["modality"]),
        load_type=LoadType(row["load_type"]),
        muscles=tuple(links),
        load_factor=row["load_factor"],
        is_unilateral=bool(row["is_unilateral"]),
        equipment=row["equipment"],
        default_rule_slug=row["rule_slug"],
        next_variant_slug=row["variant_slug"],
        default_rest_seconds=row["default_rest_seconds"],
    )


def list_exercises(conn: sqlite3.Connection, *, active_only: bool = True) -> list[Exercise]:
    where = "WHERE e.is_active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT {_EXERCISE_COLUMNS} {_EXERCISE_FROM} {where} ORDER BY e.name"
    ).fetchall()
    links = _muscles_by_exercise(conn)
    return [_to_exercise(r, links.get(r["id"], [])) for r in rows]


def get_exercise(conn: sqlite3.Connection, slug: str) -> Exercise | None:
    row = conn.execute(
        f"SELECT {_EXERCISE_COLUMNS} {_EXERCISE_FROM} WHERE e.slug = ?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    links = conn.execute(
        "SELECT m.slug, em.role FROM exercise_muscle em "
        "JOIN muscle_group m ON m.id = em.muscle_id WHERE em.exercise_id = ?",
        (row["id"],),
    ).fetchall()
    return _to_exercise(row, [MuscleLink(x["slug"], MuscleRole(x["role"])) for x in links])


def exercise_id(conn: sqlite3.Connection, slug: str) -> int | None:
    row = conn.execute("SELECT id FROM exercise WHERE slug = ?", (slug,)).fetchone()
    return row["id"] if row else None


def _to_rule(row: sqlite3.Row) -> ProgressionRule:
    raw_guards = json.loads(row["guards_json"] or "{}")
    # Solo se aceptan las guardas que el dominio conoce: una clave inventada en
    # el JSON no debe reventar la carga ni colarse sin significado.
    known = {f for f in Guards.__dataclass_fields__}
    guards = Guards(**{k: v for k, v in raw_guards.items() if k in known})
    return ProgressionRule(
        slug=row["slug"],
        name=row["name"],
        strategy=Strategy(row["strategy"]),
        params=json.loads(row["params_json"] or "{}"),
        guards=guards,
    )


def get_rule(conn: sqlite3.Connection, slug: str) -> ProgressionRule | None:
    row = conn.execute(
        "SELECT slug, name, strategy, params_json, guards_json "
        "FROM progression_rule WHERE slug = ?",
        (slug,),
    ).fetchone()
    return _to_rule(row) if row else None


def list_rules(conn: sqlite3.Connection) -> list[ProgressionRule]:
    rows = conn.execute(
        "SELECT slug, name, strategy, params_json, guards_json FROM progression_rule ORDER BY name"
    ).fetchall()
    return [_to_rule(r) for r in rows]


def rule_id(conn: sqlite3.Connection, slug: str | None) -> int | None:
    if slug is None:
        return None
    row = conn.execute("SELECT id FROM progression_rule WHERE slug = ?", (slug,)).fetchone()
    return row["id"] if row else None
