"""Ranking muscular — fórmula v1.

**Provisional y versionada.** Los pesos y umbrales de este módulo son una
primera calibración razonada, no un resultado validado. Se ajustarán con
datos reales; por eso la versión viaja en cada snapshot y todo es
recalculable desde el registro crudo.

Dos métricas, deliberadamente distintas (ADR-0003):

``development``
    Capacidad demostrada. Lenta, con trinquete, basada en las mejores marcas
    normalizadas por peso corporal. **Es la que determina el rango.**

``activity``
    Cuánto se está entrenando el músculo ahora. Volátil, ventana de 28 días.
    Alimenta el halo del mapa corporal, nunca el rango.

Confundirlas produciría un ranking que se desploma cada vez que descansas una
semana, y que premia acumular volumen por encima de hacerse fuerte.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import timedelta

from ..enums import Tier
from .tiers import points_to_next_tier, tier_for

FORMULA_VERSION = "v1"

#: Ventana de la métrica de desarrollo: las mejores marcas envejecen despacio.
#:
#: Fuera de esta ventana el músculo vuelve a ``SIN_DATOS``, no a un rango bajo.
#: Es deliberado y complementa —no contradice— el suelo de decaimiento: dentro
#: de la ventana el rango decae poco (descansar no castiga); pasados seis meses
#: sin ninguna marca, el sistema deja de afirmar una capacidad que ya no puede
#: sostener con evidencia. Prefiere "no lo sé" antes que un rango obsoleto.
DEVELOPMENT_WINDOW_DAYS = 180
#: Ventana de la métrica de actividad: refleja el presente, no el histórico.
ACTIVITY_WINDOW_DAYS = 28
#: Vida media de la ponderación exponencial de actividad.
ACTIVITY_HALF_LIFE_DAYS = 10.0

#: Días sin estímulo antes de que el desarrollo empiece a decaer.
DECAY_GRACE_DAYS = 21
#: Decaimiento diario una vez superada la gracia.
DECAY_PER_DAY = 0.004
#: Suelo del decaimiento. Con 0.85 no se pierde más de un escalón por
#: descansar: el descanso no debe castigarse (ADR-0003).
DECAY_FLOOR = 0.85

#: Bonus máximo por progresar, no solo por acumular. Es lo que hace que
#: aplicar sobrecarga progresiva suba el rango.
MAX_PROGRESSION_BONUS = 0.10
#: Bonus máximo por variedad de ejercicios que estimulan el músculo.
MAX_VARIETY_BONUS = 0.30
VARIETY_BONUS_PER_EXERCISE = 0.15


@dataclass(frozen=True, slots=True)
class StimulusEvent:
    """Una serie efectiva ya atribuida a un músculo.

    La capa de aplicación aplana el historial a estos eventos combinando
    catálogo e historial. El dominio del ranking no conoce ejercicios ni
    sesiones: solo estímulos.
    """

    date: Date
    exercise_slug: str
    #: Contribución del rol al músculo (primario 1.0 / secundario 0.5 / …).
    role_factor: float
    volume_kg: float
    e1rm_kg: float | None = None


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Parámetros de calibración, editables sin tocar la fórmula."""

    #: 1RM equivalente, en múltiplos del peso corporal, considerado tope de
    #: escala para cada músculo. Calibración provisional.
    reference_ratio: dict[str, float] = field(default_factory=dict)
    #: Valor por defecto cuando un músculo no tiene referencia propia.
    default_reference_ratio: float = 1.0
    #: Volumen semanal (kg equivalentes) considerado actividad plena.
    target_weekly_volume_kg: float = 6000.0


@dataclass(frozen=True, slots=True)
class MuscleScore:
    muscle_slug: str
    tier: Tier
    development: float
    activity: float
    days_since_stimulus: int | None
    points_to_next_tier: float | None
    #: Desglose de los factores que produjeron el resultado. Sin esto el
    #: ranking sería un número mágico, y el agente de IA no podría razonar
    #: sobre él.
    factors: dict[str, float]
    notes: tuple[str, ...] = ()

    @property
    def has_data(self) -> bool:
        return self.tier is not Tier.SIN_DATOS


def compute_muscle_score(
    muscle_slug: str,
    events: Sequence[StimulusEvent],
    *,
    today: Date,
    bodyweight_kg: float | None,
    config: RankingConfig | None = None,
) -> MuscleScore:
    """Calcula desarrollo, actividad y rango de un músculo.

    Devuelve ``SIN_DATOS`` —no ``IRON``— cuando no hay estímulos: "no medido"
    y "débil" son cosas distintas, y confundirlas haría que cuello y
    antebrazos mintieran siempre.
    """
    cfg = config or RankingConfig()

    if not events:
        return MuscleScore(
            muscle_slug=muscle_slug,
            tier=Tier.SIN_DATOS,
            development=0.0,
            activity=0.0,
            days_since_stimulus=None,
            points_to_next_tier=None,
            factors={},
            notes=("Ningún ejercicio registrado estimula este músculo",),
        )

    notes: list[str] = []
    last_date = max(e.date for e in events)
    days_since = (today - last_date).days

    activity = _activity_score(events, today=today, cfg=cfg)
    development, dev_factors, dev_notes = _development_score(
        events,
        today=today,
        days_since=days_since,
        bodyweight_kg=bodyweight_kg,
        cfg=cfg,
        muscle_slug=muscle_slug,
    )
    notes.extend(dev_notes)

    if development is None:
        # Hay estímulo pero no es medible en fuerza (p. ej. sin peso corporal
        # registrado en ejercicios de calistenia). Se dice, no se inventa.
        return MuscleScore(
            muscle_slug=muscle_slug,
            tier=Tier.SIN_DATOS,
            development=0.0,
            activity=activity,
            days_since_stimulus=days_since,
            points_to_next_tier=None,
            factors={"actividad": activity},
            notes=tuple(notes),
        )

    tier = tier_for(development)
    return MuscleScore(
        muscle_slug=muscle_slug,
        tier=tier,
        development=round(development, 2),
        activity=round(activity, 2),
        days_since_stimulus=days_since,
        points_to_next_tier=points_to_next_tier(development),
        factors=dev_factors | {"actividad": round(activity, 2)},
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------
# Actividad
# --------------------------------------------------------------------------


def _activity_score(events: Sequence[StimulusEvent], *, today: Date, cfg: RankingConfig) -> float:
    """Volumen semanal reciente, con ponderación exponencial, en escala 0–100."""
    cutoff = today - timedelta(days=ACTIVITY_WINDOW_DAYS)
    weighted = 0.0
    for e in events:
        if e.date < cutoff or e.date > today:
            continue
        age = (today - e.date).days
        weight = 0.5 ** (age / ACTIVITY_HALF_LIFE_DAYS)
        weighted += e.volume_kg * e.role_factor * weight

    # La suma ponderada aproxima el volumen de una semana típica reciente.
    weekly_equivalent = weighted / (ACTIVITY_HALF_LIFE_DAYS / 7.0 * 2.0)
    if cfg.target_weekly_volume_kg <= 0:
        return 0.0
    return min(100.0, 100.0 * weekly_equivalent / cfg.target_weekly_volume_kg)


# --------------------------------------------------------------------------
# Desarrollo
# --------------------------------------------------------------------------


def _development_score(
    events: Sequence[StimulusEvent],
    *,
    today: Date,
    days_since: int,
    bodyweight_kg: float | None,
    cfg: RankingConfig,
    muscle_slug: str,
) -> tuple[float | None, dict[str, float], list[str]]:
    notes: list[str] = []

    if bodyweight_kg is None or bodyweight_kg <= 0:
        notes.append(
            "Sin peso corporal registrado no puede normalizarse la fuerza: "
            "registra tu peso para obtener un rango"
        )
        return None, {}, notes

    cutoff = today - timedelta(days=DEVELOPMENT_WINDOW_DAYS)
    in_window = [e for e in events if cutoff <= e.date <= today]
    window = [e for e in in_window if e.e1rm_kg is not None]
    if not window:
        # Los dos motivos son distintos y el usuario merece saber cuál es el
        # suyo: uno se arregla registrando mejor, el otro entrenando.
        if in_window:
            notes.append(
                "Hay entrenamiento registrado, pero ninguna serie permite estimar "
                "fuerza (faltan repeticiones, tiempo o carga)"
            )
        else:
            notes.append(
                f"Sin marcas en los últimos {DEVELOPMENT_WINDOW_DAYS} días: "
                "el rango vuelve a estar sin determinar hasta que vuelvas a entrenarlo"
            )
        return None, {}, notes

    # Mejor marca ponderada por rol.
    best_by_exercise: dict[str, float] = {}
    for e in window:
        value = (e.e1rm_kg or 0.0) * e.role_factor
        if value > best_by_exercise.get(e.exercise_slug, 0.0):
            best_by_exercise[e.exercise_slug] = value

    peak = max(best_by_exercise.values())
    if peak <= 0:
        return None, {}, notes

    # Variedad: estimular el músculo desde varios ángulos aporta, pero con
    # rendimientos decrecientes y tope. No debe poder sustituir a la fuerza.
    others = len(best_by_exercise) - 1
    variety_bonus = min(MAX_VARIETY_BONUS, VARIETY_BONUS_PER_EXERCISE * others)

    progression_bonus = _progression_bonus(window, today=today)
    decay = _decay_factor(days_since)
    if decay < 1.0:
        notes.append(
            f"{days_since} días sin estímulo: el desarrollo decae suavemente "
            f"(x{decay:.2f}, con suelo en {DECAY_FLOOR:.2f})"
        )

    ratio = peak / bodyweight_kg
    reference = cfg.reference_ratio.get(muscle_slug, cfg.default_reference_ratio)
    if reference <= 0:
        reference = cfg.default_reference_ratio

    raw = 100.0 * (ratio / reference)
    score = min(100.0, raw * (1.0 + variety_bonus) * (1.0 + progression_bonus) * decay)

    factors = {
        "mejor_1rm_equivalente_kg": round(peak, 2),
        "ratio_sobre_peso_corporal": round(ratio, 3),
        "referencia": round(reference, 3),
        "bonus_variedad": round(variety_bonus, 3),
        "bonus_progresion": round(progression_bonus, 3),
        "decaimiento": round(decay, 3),
        "ejercicios_contribuyentes": float(len(best_by_exercise)),
    }
    return score, factors, notes


def _progression_bonus(window: Sequence[StimulusEvent], *, today: Date) -> float:
    """Premia mejorar respecto al periodo anterior, no solo acumular.

    Compara la mejor marca de los últimos 60 días con la del tramo previo. Es
    el término que hace que aplicar sobrecarga progresiva suba el rango.
    """
    split = today - timedelta(days=60)
    recent = [e.e1rm_kg * e.role_factor for e in window if e.date >= split and e.e1rm_kg]
    older = [e.e1rm_kg * e.role_factor for e in window if e.date < split and e.e1rm_kg]
    if not recent or not older:
        return 0.0

    best_recent, best_older = max(recent), max(older)
    if best_older <= 0 or best_recent <= best_older:
        return 0.0

    improvement = (best_recent - best_older) / best_older
    # Saturante: una mejora del 20 % ya otorga prácticamente el bonus máximo,
    # de modo que un salto puntual no dispare el rango.
    return MAX_PROGRESSION_BONUS * (1.0 - math.exp(-improvement / 0.08))


def _decay_factor(days_since: int) -> float:
    if days_since <= DECAY_GRACE_DAYS:
        return 1.0
    decayed = 1.0 - DECAY_PER_DAY * (days_since - DECAY_GRACE_DAYS)
    return max(DECAY_FLOOR, decayed)
