"""Base de datos sembrada en memoria y atajos para construir escenarios."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from fitup.application.services import planning as planning_svc
from fitup.infrastructure.db import migrator
from fitup.infrastructure.db.connection import connect_memory
from fitup.infrastructure.seed import catalog
from helpers_app import plan

TODAY = date(2026, 3, 15)  # domingo
MONDAY = date(2026, 3, 9)


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect_memory()
    migrator.migrate(conn)
    catalog.seed(conn)
    yield conn
    conn.close()


@pytest.fixture
def push_routine(db) -> int:
    """Rutina de empuje con tres ejercicios, creada el 1 de marzo."""
    detail = planning_svc.create_routine(
        db,
        name="Empuje",
        exercises=[
            plan("flexiones", count=3, reps=15),
            plan("press_banca", count=3, reps=8, weight_kg=40.0),
            plan("plancha", count=3, reps=None, time_s=45),
        ],
    )
    db.execute(
        "UPDATE routine SET created_at = '2026-03-01T10:00:00+01:00' WHERE id = ?",
        (detail.id,),
    )
    db.execute(
        "UPDATE routine_version SET created_at = '2026-03-01T10:00:00+01:00' WHERE routine_id = ?",
        (detail.id,),
    )
    db.commit()
    return detail.id


@pytest.fixture
def weekly(db, push_routine) -> int:
    """La rutina de empuje asignada a lunes, miércoles y viernes."""
    planning_svc.set_week(
        db,
        {0: push_routine, 2: push_routine, 4: push_routine},
        effective_from=date(2026, 3, 1),
    )
    return push_routine
