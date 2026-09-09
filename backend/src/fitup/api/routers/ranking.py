"""Ranking muscular: mapa corporal, ficha por músculo y evolución.

Solo lectura salvo el snapshot, que es caché reconstruible. El rango que
devuelve esta API es una **estimación calibrada de forma provisional** y el
campo ``provisional`` lo declara: cualquier cliente —la PWA o el agente de
IA— debe presentarlo como tal y no como una medición.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...application.repositories import catalog, history
from ...application.services import metrics
from ...application.services import ranking as svc
from ...domain.enums import Actor
from ...domain.ranking.v2 import DEVELOPMENT_WINDOW_DAYS
from .. import mappers, schemas
from ..agent import actor_header
from ..deps import get_db
from ..deps import today as today_dep

router = APIRouter(tags=["ranking"])


@router.get("/ranking", response_model=schemas.RankingOut)
def muscle_ranking(db: sqlite3.Connection = Depends(get_db), today: Date = Depends(today_dep)):
    """Los 18 músculos con su rango, su halo de actividad y sus avisos."""
    return mappers.ranking_out(svc.ranking(db, today=today))


@router.get("/ranking/{muscle_slug}", response_model=schemas.MuscleDetailOut)
def muscle_detail(
    muscle_slug: str,
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    """Ficha explicable: factores, ejercicios que aportan, histórico y qué falta."""
    return mappers.muscle_detail_out(svc.muscle_detail(db, muscle_slug, today=today))


@router.post("/ranking/snapshot", status_code=status.HTTP_201_CREATED)
def take_snapshot(
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
    actor: Actor = Depends(actor_header),
):
    """Fuerza un punto del histórico. Recalcularlo sobrescribe: es caché.

    Sin scope: el snapshot es caché reconstruible desde el registro crudo, así
    que rehacerlo no destruye nada. Se audita igual, para que la traza del
    agente no tenga huecos.
    """
    muscles = svc.take_snapshot(db, today=today)
    history.audit(
        db, actor=actor, action="take_snapshot", payload={"date": today, "muscles": muscles}
    )
    db.commit()
    return {"date": today, "muscles": muscles}


@router.get(
    "/metricas/ejercicios/{exercise_slug}",
    response_model=schemas.ExerciseProgressOut,
    tags=["métricas"],
)
def exercise_progress(
    exercise_slug: str,
    days: int = Query(default=DEVELOPMENT_WINDOW_DAYS, ge=7, le=1825),
    db: sqlite3.Connection = Depends(get_db),
    today: Date = Depends(today_dep),
):
    """Evolución de un ejercicio: volumen y 1RM equivalente sesión a sesión."""
    if catalog.get_exercise(db, exercise_slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el ejercicio '{exercise_slug}'")
    since, until = metrics.default_window(today, days)
    return mappers.exercise_progress_out(
        metrics.exercise_progress(db, exercise_slug, since=since, until=until)
    )
