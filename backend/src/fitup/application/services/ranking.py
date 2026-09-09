"""Casos de uso del ranking muscular.

Orquesta tres piezas puras que ya existían —``metrics/load``,
``ranking/v2`` y ``ranking/balance``— y añade lo único que no puede vivir en
el dominio: leer historial, resolver la calibración y guardar los snapshots.

El principio que gobierna el módulo es el de ADR-0003: el rango mide
**desarrollo**, la actividad es un halo secundario, y un músculo sin datos
dice "sin datos", nunca Iron.
"""

from __future__ import annotations

import sqlite3
from datetime import date as Date
from datetime import timedelta

from ...domain.enums import Tier
from ...domain.ranking.balance import check_balance
from ...domain.ranking.tiers import next_tier
from ...domain.ranking.v2 import (
    ACTIVITY_WINDOW_DAYS,
    DEVELOPMENT_WINDOW_DAYS,
    FORMULA_VERSION,
    MuscleScore,
    RankingConfig,
    StimulusEvent,
    compute_muscle_score,
)
from ..errors import NotFound
from ..repositories import catalog, history
from ..repositories import ranking as snapshots
from ..views import (
    ExerciseContribution,
    MuscleDetail,
    MuscleRankingEntry,
    RankingView,
)
from . import metrics

#: Clave de ajustes con la que sobrescribir la calibración sin tocar código
#: (ADR-0003: umbrales editables en configuración). Las escaleras por ejercicio
#: viven en ``domain.ranking.standards``; aquí solo queda el objetivo de
#: volumen, que es lo único que la fórmula v2 sigue tomando de configuración.
TARGET_VOLUME_SETTING = "ranking_volumen_semanal_objetivo"

#: Cada cuánto se guarda un punto del histórico. Semanal: el desarrollo se
#: mueve despacio y un punto diario solo engordaría la tabla.
SNAPSHOT_EVERY_DAYS = 7

#: Ventana corta para "qué has entrenado últimamente", la misma que usa el
#: halo de actividad.
RECENT_WINDOW_DAYS = ACTIVITY_WINDOW_DAYS
QUARTER_WINDOW_DAYS = 90


def load_config(conn: sqlite3.Connection) -> RankingConfig:
    """Calibración vigente: la de la fórmula, con lo que ajuste el usuario."""
    target = history.get_setting(conn, TARGET_VOLUME_SETTING)
    if isinstance(target, int | float) and target > 0:
        return RankingConfig(target_weekly_volume_kg=float(target))
    return RankingConfig()


def _events(
    conn: sqlite3.Connection, *, today: Date
) -> tuple[dict[str, list[StimulusEvent]], object]:
    since = today - timedelta(days=DEVELOPMENT_WINDOW_DAYS)
    data = metrics.load_stimuli(conn, since=since, until=today)
    return metrics.events_by_muscle(conn, data), data


def compute_scores(
    conn: sqlite3.Connection, *, today: Date
) -> tuple[dict[str, MuscleScore], object, float | None]:
    """Puntuación de los 18 músculos del catálogo, medibles o no."""
    config = load_config(conn)
    by_muscle, data = _events(conn, today=today)
    bodyweight = history.bodyweight_at(conn, today)

    scores = {
        muscle.slug: compute_muscle_score(
            muscle.slug,
            by_muscle.get(muscle.slug, []),
            today=today,
            config=config,
        )
        for muscle in catalog.list_muscles(conn)
    }
    return scores, data, bodyweight


def ranking(conn: sqlite3.Connection, *, today: Date | None = None) -> RankingView:
    """El mapa corporal completo, con sus avisos y sus límites declarados."""
    today = today or Date.today()
    scores, data, bodyweight = compute_scores(conn, today=today)

    entries = tuple(
        MuscleRankingEntry(
            muscle_slug=m.slug,
            name=m.name,
            region=m.region,
            body_view=m.body_view,
            svg_key=m.svg_key,
            display_order=m.display_order,
            score=scores[m.slug],
        )
        for m in catalog.list_muscles(conn)
    )

    development = {e.muscle_slug: e.development for e in entries}
    measured = sum(1 for e in entries if e.development is not None)
    return RankingView(
        today=today,
        formula_version=FORMULA_VERSION,
        bodyweight_kg=bodyweight,
        entries=entries,
        balance=tuple(check_balance(development)),
        notes=_notes(data, bodyweight=bodyweight, measured=measured),
    )


def _notes(data, *, bodyweight: float | None, measured: int) -> tuple[str, ...]:
    """Qué impide medir mejor. Se dice; no se disimula con un cero."""
    notes: list[str] = []
    if bodyweight is None:
        # Ya no bloquea el rango —las escaleras están en repeticiones—, pero sí
        # el volumen de los ejercicios corporales, que es la mitad del halo.
        notes.append(
            "Sin peso corporal registrado no puede calcularse el volumen de los "
            "ejercicios de peso corporal: el rango funciona, la actividad no"
        )
    if measured == 0:
        notes.append(
            "Todavía no hay series registradas que permitan estimar fuerza: "
            "el rango aparece cuando entrenes con repeticiones y carga anotadas"
        )
    if getattr(data, "skipped_sets", 0):
        notes.append(
            f"{data.skipped_sets} serie(s) quedaron fuera del cálculo por faltarles "
            "datos (peso, repeticiones o tiempo)"
        )
    return tuple(notes)


def muscle_detail(
    conn: sqlite3.Connection, muscle_slug: str, *, today: Date | None = None
) -> MuscleDetail:
    """Ficha explicable de un músculo (ADR-0003, explicabilidad obligatoria)."""
    today = today or Date.today()
    muscle = next((m for m in catalog.list_muscles(conn) if m.slug == muscle_slug), None)
    if muscle is None:
        raise NotFound(f"No existe el músculo '{muscle_slug}'")

    config = load_config(conn)
    by_muscle, _ = _events(conn, today=today)
    events = by_muscle.get(muscle_slug, [])

    score = compute_muscle_score(muscle_slug, events, today=today, config=config)
    entry = MuscleRankingEntry(
        muscle_slug=muscle.slug,
        name=muscle.name,
        region=muscle.region,
        body_view=muscle.body_view,
        svg_key=muscle.svg_key,
        display_order=muscle.display_order,
        score=score,
    )

    return MuscleDetail(
        entry=entry,
        next_tier=next_tier(score.tier) if score.has_data else None,
        points_to_next_tier=score.points_to_next_tier,
        recent=metrics.muscle_usage(
            events, since=today - timedelta(days=RECENT_WINDOW_DAYS), until=today
        ),
        quarter=metrics.muscle_usage(
            events, since=today - timedelta(days=QUARTER_WINDOW_DAYS), until=today
        ),
        exercises=_contributions(conn, events),
        history=tuple(snapshots.history(conn, muscle_slug, formula_version=FORMULA_VERSION)),
    )


def _contributions(
    conn: sqlite3.Connection, events: list[StimulusEvent]
) -> tuple[ExerciseContribution, ...]:
    """Ejercicios que estimulan el músculo, ordenados por lo que aportan."""
    if not events:
        return ()

    names = {e.slug: e.name for e in catalog.list_exercises(conn, active_only=False)}
    roles = {v: k for k, v in _ROLE_BY_FACTOR.items()}

    volume: dict[str, float] = {}
    best: dict[str, float] = {}
    last: dict[str, Date] = {}
    factor: dict[str, float] = {}

    for e in events:
        volume[e.exercise_slug] = volume.get(e.exercise_slug, 0.0) + e.volume_kg * e.role_factor
        factor[e.exercise_slug] = e.role_factor
        if e.mark is not None:
            best[e.exercise_slug] = max(best.get(e.exercise_slug, 0.0), e.mark)
        if e.date > last.get(e.exercise_slug, Date.min):
            last[e.exercise_slug] = e.date

    return tuple(
        ExerciseContribution(
            exercise_slug=slug,
            exercise_name=names.get(slug, slug),
            role=roles.get(factor[slug], "desconocido"),
            role_factor=factor[slug],
            volume_kg=round(total, 1),
            best_mark=round(best[slug], 1) if slug in best else None,
            last_date=last.get(slug),
        )
        for slug, total in sorted(volume.items(), key=lambda kv: kv[1], reverse=True)
    )


#: Inverso de ROLE_CONTRIBUTION, para poder decir "primario" en vez de "1.0".
_ROLE_BY_FACTOR = {"primario": 1.0, "secundario": 0.5, "estabilizador": 0.2}


# --------------------------------------------------------------------------
# Snapshots
# --------------------------------------------------------------------------


def take_snapshot(conn: sqlite3.Connection, *, today: Date | None = None) -> int:
    """Guarda el rango de hoy. Reconstruible: recalcularlo lo sobrescribe."""
    today = today or Date.today()
    scores, _, _ = compute_scores(conn, today=today)
    written = snapshots.save(conn, today, scores, formula_version=FORMULA_VERSION)
    conn.commit()
    return written


def snapshot_if_stale(conn: sqlite3.Connection, *, today: Date | None = None) -> int:
    """Toma un snapshot si ha pasado una semana desde el último.

    Mismo criterio que la copia de seguridad: sin planificador ni proceso
    residente, se aprovecha el arranque del servidor. Para una app que se abre
    varias veces por semana es suficiente, y si se salta una semana el
    histórico pierde un punto, no la verdad — que sigue en el historial crudo.
    """
    today = today or Date.today()
    last = snapshots.last_snapshot_date(conn, formula_version=FORMULA_VERSION)
    if last is not None and (today - last).days < SNAPSHOT_EVERY_DAYS:
        return 0

    scores, _, _ = compute_scores(conn, today=today)
    if not any(score.has_data for score in scores.values()):
        # Un punto donde ningún músculo tiene rango no es información: sería
        # una fila de ceros que luego aparece como un valle en la gráfica de
        # alguien que simplemente aún no había registrado nada. Forzarlo sigue
        # siendo posible desde `take_snapshot`.
        return 0

    written = snapshots.save(conn, today, scores, formula_version=FORMULA_VERSION)
    conn.commit()
    return written


def tier_of(scores: dict[str, MuscleScore], muscle_slug: str) -> Tier:
    return scores[muscle_slug].tier
