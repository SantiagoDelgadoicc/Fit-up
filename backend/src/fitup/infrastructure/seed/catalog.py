"""Carga del catálogo semilla: músculos, reglas de progresión y ejercicios.

El catálogo vive en JSON y no en código para que puedas editarlo sin tocar
Python, y para que el agente de IA pueda leerlo directamente.

La carga es **idempotente**: se puede ejecutar sobre una base ya poblada sin
duplicar nada ni pisar personalizaciones. Y valida referencias antes de
escribir: un slug de músculo mal escrito debe fallar al sembrar, no producir
un ranking silenciosamente incompleto meses después.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"

VALID_ROLES = {"primario", "secundario", "estabilizador"}


class SeedError(RuntimeError):
    """El catálogo semilla es inconsistente. Se aborta antes de escribir."""


@dataclass(frozen=True, slots=True)
class SeedReport:
    muscles: int = 0
    rules: int = 0
    exercises: int = 0
    links: int = 0
    settings: int = 0

    @property
    def total(self) -> int:
        return self.muscles + self.rules + self.exercises + self.links + self.settings


def _load(name: str, directory: Path | None = None) -> list[dict[str, Any]]:
    path = (directory or DATA_DIR) / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"Falta el fichero de catálogo '{path}'") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"'{path}' no es JSON válido: {exc}") from exc
    if not isinstance(data, list):
        raise SeedError(f"'{path}' debe contener una lista")
    return data


def validate(directory: Path | None = None) -> None:
    """Comprueba la coherencia del catálogo sin tocar la base de datos."""
    muscles = _load("muscles.json", directory)
    rules = _load("progression_rules.json", directory)
    exercises = _load("exercises.json", directory)

    muscle_slugs = {m["slug"] for m in muscles}
    rule_slugs = {r["slug"] for r in rules}
    exercise_slugs = {e["slug"] for e in exercises}

    if len(muscle_slugs) != len(muscles):
        raise SeedError("Hay slugs de músculo duplicados")
    if len(rule_slugs) != len(rules):
        raise SeedError("Hay slugs de regla duplicados")
    if len(exercise_slugs) != len(exercises):
        raise SeedError("Hay slugs de ejercicio duplicados")

    for ex in exercises:
        slug = ex["slug"]

        rule = ex.get("default_rule")
        if rule is not None and rule not in rule_slugs:
            raise SeedError(f"'{slug}' referencia la regla inexistente '{rule}'")

        variant = ex.get("next_variant")
        if variant is not None:
            if variant not in exercise_slugs:
                raise SeedError(f"'{slug}' referencia la variante inexistente '{variant}'")
            if variant == slug:
                raise SeedError(f"'{slug}' se referencia a sí mismo como variante")

        links = ex.get("muscles", [])
        if not links and ex.get("load_type") != "ninguna":
            raise SeedError(f"'{slug}' no declara ningún músculo")

        seen: set[str] = set()
        for muscle_slug, role in links:
            if muscle_slug not in muscle_slugs:
                raise SeedError(f"'{slug}' referencia el músculo inexistente '{muscle_slug}'")
            if role not in VALID_ROLES:
                raise SeedError(f"'{slug}' usa el rol inválido '{role}'")
            if muscle_slug in seen:
                raise SeedError(f"'{slug}' repite el músculo '{muscle_slug}'")
            seen.add(muscle_slug)

        if ex.get("load_type") == "corporal" and not ex.get("load_factor"):
            raise SeedError(
                f"'{slug}' es de peso corporal y no declara 'load_factor': "
                "sin él su volumen no puede calcularse"
            )

    _detect_variant_cycles(exercises)


def _detect_variant_cycles(exercises: list[dict[str, Any]]) -> None:
    """Una cadena de variantes circular colgaría la progresión indefinidamente."""
    nxt = {e["slug"]: e.get("next_variant") for e in exercises}
    for start in nxt:
        seen: set[str] = set()
        node = start
        while node is not None:
            if node in seen:
                raise SeedError(f"La cadena de variantes que empieza en '{start}' es circular")
            seen.add(node)
            node = nxt.get(node)


DEFAULT_SETTINGS: dict[str, Any] = {
    "unidades": "kg",
    "inicio_semana": "lunes",
    "dias_gracia": 3,
    "tema": "oscuro",
    "timer_presets_s": [60, 90, 120, 180],
    "ranking_formula_version": "v1",
    "peso_corporal_kg": None,
}


def seed(conn: sqlite3.Connection, directory: Path | None = None) -> SeedReport:
    """Inserta el catálogo. Idempotente: lo ya existente no se toca."""
    validate(directory)

    muscles = _load("muscles.json", directory)
    rules = _load("progression_rules.json", directory)
    exercises = _load("exercises.json", directory)

    n_muscles = n_rules = n_exercises = n_links = n_settings = 0

    for m in muscles:
        cur = conn.execute(
            "INSERT OR IGNORE INTO muscle_group "
            "(slug, name, region, body_view, svg_key, display_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                m["slug"],
                m["name"],
                m["region"],
                m["body_view"],
                m["svg_key"],
                m.get("display_order", 0),
            ),
        )
        n_muscles += cur.rowcount

    for r in rules:
        cur = conn.execute(
            "INSERT OR IGNORE INTO progression_rule "
            "(slug, name, strategy, params_json, guards_json, is_builtin) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (
                r["slug"],
                r["name"],
                r["strategy"],
                json.dumps(r.get("params", {}), ensure_ascii=False),
                json.dumps(r.get("guards", {}), ensure_ascii=False),
            ),
        )
        n_rules += cur.rowcount

    rule_ids = _slug_ids(conn, "progression_rule")
    muscle_ids = _slug_ids(conn, "muscle_group")

    # Primera pasada: los ejercicios, sin resolver aún next_variant_id, porque
    # una variante puede apuntar a un ejercicio que todavía no existe.
    for e in exercises:
        cur = conn.execute(
            "INSERT OR IGNORE INTO exercise "
            "(slug, name, modality, load_type, load_factor, is_unilateral, equipment, "
            " default_rule_id, default_rest_seconds, notes, is_custom, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)",
            (
                e["slug"],
                e["name"],
                e["modality"],
                e["load_type"],
                float(e.get("load_factor", 0.0)),
                int(bool(e.get("is_unilateral", False))),
                e.get("equipment"),
                rule_ids.get(e.get("default_rule")),
                int(e.get("default_rest_seconds", 90)),
                e.get("notes"),
            ),
        )
        n_exercises += cur.rowcount

    exercise_ids = _slug_ids(conn, "exercise")

    # Segunda pasada: cadenas de variantes y vínculos musculares.
    for e in exercises:
        variant = e.get("next_variant")
        if variant is not None:
            conn.execute(
                "UPDATE exercise SET next_variant_id = ? "
                "WHERE slug = ? AND next_variant_id IS NULL",
                (exercise_ids[variant], e["slug"]),
            )
        for muscle_slug, role in e.get("muscles", []):
            cur = conn.execute(
                "INSERT OR IGNORE INTO exercise_muscle (exercise_id, muscle_id, role) "
                "VALUES (?, ?, ?)",
                (exercise_ids[e["slug"]], muscle_ids[muscle_slug], role),
            )
            n_links += cur.rowcount

    now = datetime.now(UTC).isoformat(timespec="seconds")
    for key, value in DEFAULT_SETTINGS.items():
        cur = conn.execute(
            "INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), now),
        )
        n_settings += cur.rowcount

    conn.commit()
    return SeedReport(n_muscles, n_rules, n_exercises, n_links, n_settings)


def _slug_ids(conn: sqlite3.Connection, table: str) -> dict[str, int]:
    rows = conn.execute(f"SELECT id, slug FROM {table}").fetchall()
    return {row["slug"]: row["id"] for row in rows}
