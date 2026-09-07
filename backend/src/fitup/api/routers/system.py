"""Ajustes, peso corporal, export y copias de seguridad."""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Depends, status

from ...application.repositories import history
from ...application.services import maintenance
from .. import schemas
from ..deps import Settings, get_db, get_settings
from ..deps import today as today_dep

router = APIRouter(tags=["sistema"])


@router.get("/salud")
def health(db: sqlite3.Connection = Depends(get_db)):
    from ...infrastructure.db import connection, migrator

    return {
        "ok": connection.integrity_ok(db),
        "schema_version": migrator.current_version(db),
    }


# --------------------------------------------------------------------------
# Ajustes
# --------------------------------------------------------------------------


@router.get("/ajustes")
def get_settings_all(db: sqlite3.Connection = Depends(get_db)):
    return history.get_settings(db)


@router.put("/ajustes/{key}")
def set_setting(key: str, payload: schemas.SettingIn, db: sqlite3.Connection = Depends(get_db)):
    history.set_setting(db, key, payload.value)
    db.commit()
    return {key: payload.value}


# --------------------------------------------------------------------------
# Peso corporal
# --------------------------------------------------------------------------


@router.get("/peso", response_model=list[schemas.BodyweightOut])
def bodyweight_history(db: sqlite3.Connection = Depends(get_db)):
    return [schemas.BodyweightOut(date=d, weight_kg=w) for d, w in history.bodyweight_history(db)]


@router.get("/peso/actual", response_model=schemas.BodyweightOut | None)
def current_bodyweight(db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    """``null`` si no hay ningún registro.

    Las métricas que dependen del peso corporal deben poder decir que no son
    calculables, en lugar de suponer un valor.
    """
    weight = history.bodyweight_at(db, today)
    return schemas.BodyweightOut(date=today, weight_kg=weight) if weight else None


@router.put("/peso", response_model=schemas.BodyweightOut)
def set_bodyweight(payload: schemas.BodyweightIn, db: sqlite3.Connection = Depends(get_db)):
    history.set_bodyweight(db, payload.date, payload.weight_kg)
    db.commit()
    return payload


# --------------------------------------------------------------------------
# Export y copias
# --------------------------------------------------------------------------


@router.get("/export")
def export(db: sqlite3.Connection = Depends(get_db)):
    """Volcado completo y autocontenido.

    Segundo destinatario: el agente de IA (ADR-0004), que puede analizarlo sin
    depender del proceso vivo. El texto libre que contiene es dato, no orden.
    """
    return maintenance.export_data(db)


@router.post("/backup", status_code=status.HTTP_201_CREATED)
def backup(
    db: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    today: Date = Depends(today_dep),
):
    path = maintenance.backup(db, settings.db_path, today=today)
    return {"path": str(path)}
