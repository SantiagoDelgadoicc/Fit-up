"""Ajustes, peso corporal, export y copias de seguridad."""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Depends, Query, status

from ...application.repositories import history
from ...application.services import maintenance
from ...domain.enums import Actor
from .. import agent, schemas
from ..agent import Caller, actor_header, get_scopes
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
def set_setting(
    key: str,
    payload: schemas.SettingIn,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_settings),
):
    history.set_setting(db, key, payload.value)
    history.audit(
        db, actor=caller.actor, action="set_setting", payload={"key": key, "value": payload.value}
    )
    db.commit()
    return {key: payload.value}


@router.get("/agente/permisos")
def agent_scopes(db: sqlite3.Connection = Depends(get_db)):
    """Permisos vigentes del agente.

    Los publica para que el propio agente pueda consultarlos y saber qué no
    va a poder hacer, en vez de descubrirlo con un 403 a mitad de un plan.
    """
    return get_scopes(db)


@router.get("/auditoria", response_model=list[schemas.AuditEntryOut])
def audit_log(
    actor: Actor | None = None,
    result: str | None = Query(default=None, pattern="^(ok|error|rechazado)$"),
    since: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: sqlite3.Connection = Depends(get_db),
):
    """Qué se ha hecho, quién y con qué resultado.

    Es la contrapartida de que los scopes no sean una frontera real: si no se
    puede impedir, al menos tiene que poder revisarse (ADR-0004 §2).
    """
    return history.list_audit(db, actor=actor, result=result, since=since, limit=limit)


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
def set_bodyweight(
    payload: schemas.BodyweightIn,
    db: sqlite3.Connection = Depends(get_db),
    caller: Caller = Depends(agent.write_settings),
):
    history.set_bodyweight(db, payload.date, payload.weight_kg)
    history.audit(
        db,
        actor=caller.actor,
        action="set_bodyweight",
        payload={"date": payload.date, "weight_kg": payload.weight_kg},
    )
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
    actor: Actor = Depends(actor_header),
):
    """Copia bajo demanda. Sin scope: guardar una copia nunca empeora nada."""
    path = maintenance.backup(db, settings.db_path, today=today)
    history.audit(db, actor=actor, action="backup", payload={"path": str(path)})
    db.commit()
    return {"path": str(path)}
