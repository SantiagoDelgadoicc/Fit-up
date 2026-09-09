"""Ranking muscular — fórmula v2.

Sustituye a v1. El cambio no es de parámetros, es de pregunta: v1 estimaba un
1RM con Epley y lo comparaba con múltiplos del peso corporal; v2 compara **la
marca real de cada ejercicio con la escalera de ese ejercicio**
(``standards.py``). Nada se convierte en nada.

Por qué se tiró v1: con series largas de calistenia, Epley extrapolaba fuera
de su rango válido —×2 a 30 repeticiones, ×4,3 a 100— y producía marcas
imposibles. Tres músculos llegaron a Radiant con dos días de registro. El
problema no eran los umbrales: era convertir resistencia en fuerza.

Dos métricas, deliberadamente distintas (ADR-0003):

``development``
    Capacidad demostrada, y **es la que determina el rango**. Sale de la mejor
    serie única confirmada de cada ejercicio.

``activity``
    Cuánto se está entrenando el músculo ahora. Volátil, ventana de 28 días.
    Alimenta el halo del mapa corporal, nunca el rango.

Tres reglas gobiernan el desarrollo:

1. **Cuenta la mejor serie, no la suma.** 30 repeticiones seguidas demuestran
   más que 3×10, y sumar volumen no debe poder sustituir a la capacidad.
2. **Trinquete de constancia.** Una marca cuenta cuando se ha repetido: la
   mejor de las que se han alcanzado en dos sesiones distintas. Un día bueno
   suelto no sube el rango; repetirlo, sí.
3. **Techo por ejercicio.** Ninguno puede dar más rango del que declara su
   escalera, por muchas repeticiones que se acumulen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta

from ..enums import Tier
from .standards import (
    ExerciseStandard,
    mark_for_score,
    score_for_mark,
    tier_cap_reached,
)
from .tiers import TIER_THRESHOLDS, next_tier, points_to_next_tier, tier_for

FORMULA_VERSION = "v2"

#: Ventana de la métrica de desarrollo: las mejores marcas envejecen despacio.
#:
#: Fuera de esta ventana el músculo vuelve a ``SIN_DATOS``, no a un rango bajo.
#: Pasados seis meses sin ninguna marca el sistema deja de afirmar una
#: capacidad que ya no puede sostener con evidencia.
DEVELOPMENT_WINDOW_DAYS = 180
#: Ventana de la métrica de actividad: refleja el presente, no el histórico.
ACTIVITY_WINDOW_DAYS = 28
#: Vida media de la ponderación exponencial de actividad.
ACTIVITY_HALF_LIFE_DAYS = 10.0

#: Sesiones en las que hay que alcanzar una marca para que cuente. Es el
#: trinquete: mismo criterio que ``required_successful_sessions`` del motor de
#: progresión, para que plan y rango no midan con varas distintas.
CONFIRMATIONS_REQUIRED = 2

#: Días sin estímulo antes de que el desarrollo empiece a decaer.
DECAY_GRACE_DAYS = 21
#: Decaimiento diario una vez superada la gracia.
DECAY_PER_DAY = 0.004
#: Suelo del decaimiento. Con 0.85 no se pierde más de un escalón por
#: descansar: el descanso no debe castigarse (ADR-0003).
DECAY_FLOOR = 0.85


@dataclass(frozen=True, slots=True)
class StimulusEvent:
    """Una sesión de un ejercicio ya atribuida a un músculo.

    La capa de aplicación aplana el historial a estos eventos combinando
    catálogo e historial. El dominio del ranking no conoce ejercicios ni
    sesiones: solo estímulos.
    """

    date: Date
    exercise_slug: str
    #: Contribución del rol al músculo (primario 1.0 / secundario 0.5 / …).
    role_factor: float
    volume_kg: float
    #: Mejor serie única del día, en las unidades de la escalera del ejercicio
    #: (repeticiones, o segundos en los isométricos). ``None`` si la serie no
    #: permite deducirla.
    mark: float | None = None
    #: Escalera del ejercicio, resuelta por la aplicación desde el catálogo.
    standard: ExerciseStandard | None = None


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """Parámetros de calibración, editables sin tocar la fórmula."""

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
    #: Ejercicio que fija el rango del músculo, y qué falta para el siguiente
    #: escalón. Es lo que convierte el ranking en un objetivo accionable.
    leading_exercise: str | None = None
    leading_mark: float | None = None
    next_tier: Tier | None = None
    next_mark: float | None = None

    @property
    def has_data(self) -> bool:
        return self.tier is not Tier.SIN_DATOS


def compute_muscle_score(
    muscle_slug: str,
    events: Sequence[StimulusEvent],
    *,
    today: Date,
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

    last_date = max(e.date for e in events)
    days_since = (today - last_date).days
    activity = _activity_score(events, today=today, cfg=cfg)

    best = _best_exercise(events, today=today)
    if best is None:
        return MuscleScore(
            muscle_slug=muscle_slug,
            tier=Tier.SIN_DATOS,
            development=0.0,
            activity=activity,
            days_since_stimulus=days_since,
            points_to_next_tier=None,
            factors={"actividad": round(activity, 2)},
            notes=(
                "Hay entrenamiento registrado, pero ninguna serie permite "
                "medir una marca (faltan repeticiones o tiempo)",
            ),
        )

    slug, mark, standard, role_factor, raw_score = best
    decay = _decay_factor(days_since)
    development = min(100.0, raw_score * role_factor * decay)

    notes: list[str] = []
    if role_factor < 1.0:
        notes.append(
            f"Este músculo solo trabaja como secundario en '{slug}': "
            "su rango está limitado hasta que haya un ejercicio que lo trabaje "
            "como principal"
        )
    if decay < 1.0:
        notes.append(
            f"{days_since} días sin estímulo: el desarrollo decae suavemente "
            f"(x{decay:.2f}, con suelo en {DECAY_FLOOR:.2f})"
        )
    if tier_cap_reached(mark, standard):
        notes.append(
            f"'{slug}' ha llegado a su techo ({standard.max_tier.value}): más "
            "repeticiones ya no suben el rango, hace falta un ejercicio más exigente"
        )
    if standard.provisional:
        notes.append(f"La escalera de '{slug}' aún no está calibrada; usa la genérica")

    tier = tier_for(development)
    upcoming, needed = _milestone(tier, standard, role_factor=role_factor, decay=decay)
    if upcoming is not None and needed is None:
        notes.append(
            f"Con '{slug}' no se puede llegar a {upcoming.value}: hace falta un "
            "ejercicio que trabaje este músculo de forma más exigente"
        )

    return MuscleScore(
        muscle_slug=muscle_slug,
        tier=tier,
        development=round(development, 2),
        activity=round(activity, 2),
        days_since_stimulus=days_since,
        points_to_next_tier=points_to_next_tier(development),
        factors={
            "marca_confirmada": round(mark, 2),
            "puntuación_del_ejercicio": round(raw_score, 2),
            "factor_de_rol": role_factor,
            "decaimiento": round(decay, 3),
            "actividad": round(activity, 2),
        },
        notes=tuple(notes),
        leading_exercise=slug,
        leading_mark=round(mark, 2),
        next_tier=upcoming,
        next_mark=round(needed, 1) if needed is not None else None,
    )


def _milestone(
    tier: Tier, standard: ExerciseStandard, *, role_factor: float, decay: float
) -> tuple[Tier | None, float | None]:
    """Siguiente rango del **músculo** y la marca que lo desbloquea.

    No es el siguiente escalón del ejercicio: si el músculo solo trabaja como
    secundario, su puntuación va multiplicada por el rol, y hacen falta más
    repeticiones de las que marcaría la escalera a secas. Dar la cifra del
    ejercicio sería prometer una subida que no llega.
    """
    upcoming = next_tier(tier)
    if upcoming is None:
        return None, None

    divisor = role_factor * decay
    if divisor <= 0:  # pragma: no cover - defensivo
        return upcoming, None
    return upcoming, mark_for_score(TIER_THRESHOLDS[upcoming] / divisor, standard)


# --------------------------------------------------------------------------
# Desarrollo
# --------------------------------------------------------------------------


def _best_exercise(
    events: Sequence[StimulusEvent], *, today: Date
) -> tuple[str, float, ExerciseStandard, float, float] | None:
    """Ejercicio que fija el rango del músculo.

    Gana el que más puntuación aporta ya ponderada por su rol: una dominada
    donde el músculo es principal manda sobre una donde solo acompaña, aunque
    la marca bruta de la segunda sea mayor.
    """
    cutoff = today - timedelta(days=DEVELOPMENT_WINDOW_DAYS)
    marks: dict[str, list[float]] = {}
    meta: dict[str, tuple[ExerciseStandard, float]] = {}

    for e in events:
        if e.mark is None or e.standard is None or not (cutoff <= e.date <= today):
            continue
        marks.setdefault(e.exercise_slug, []).append(e.mark)
        meta[e.exercise_slug] = (e.standard, e.role_factor)

    best: tuple[str, float, ExerciseStandard, float, float] | None = None
    for slug, values in marks.items():
        confirmed = _confirmed_mark(values)
        standard, role_factor = meta[slug]
        score = score_for_mark(confirmed, standard)
        if best is None or score * role_factor > best[4] * best[3]:
            best = (slug, confirmed, standard, role_factor, score)
    return best


def _confirmed_mark(marks: Sequence[float]) -> float:
    """La mejor marca alcanzada en ``CONFIRMATIONS_REQUIRED`` sesiones.

    Con una sola sesión cuenta esa: un dato es un dato. El trinquete solo
    gobierna las **mejoras**, que es donde importa no premiar un día suelto.
    """
    ordered = sorted(marks, reverse=True)
    if len(ordered) < CONFIRMATIONS_REQUIRED:
        return ordered[0]
    return ordered[CONFIRMATIONS_REQUIRED - 1]


def _decay_factor(days_since: int) -> float:
    if days_since <= DECAY_GRACE_DAYS:
        return 1.0
    decayed = 1.0 - DECAY_PER_DAY * (days_since - DECAY_GRACE_DAYS)
    return max(DECAY_FLOOR, decayed)


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
