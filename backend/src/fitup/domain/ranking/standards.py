"""Escaleras de rango por ejercicio: qué marca corresponde a qué tier.

Sustituye a la calibración por múltiplos del peso corporal de la fórmula v1.
El cambio de fondo es cuál es la pregunta:

- **v1** preguntaba "¿cuánto levantarías a una repetición?" y lo estimaba con
  Epley. Fuera de su rango válido (~12 reps) esa extrapolación multiplicaba la
  carga por 2 a 30 repeticiones y por 4,3 a 100, así que una serie larga de
  calistenia producía marcas de levantador olímpico.
- **v2** pregunta "¿cuántas repeticiones haces de *este* ejercicio?" y las
  compara con una escalera propia de ese ejercicio. 30 dominadas son 30
  dominadas: no se convierten en nada.

Consecuencias buscadas:

1. **La rutina no cambia.** Progresar es hacer más repeticiones del mismo
   ejercicio, no cambiar de ejercicio. La serie histórica se conserva.
2. **El techo es duro por construcción.** Radiant tiene nombre y número —60
   dominadas, 150 flexiones— y no se alcanza acumulando series fáciles.
3. **Los ejercicios ligeros no pueden mentir.** ``max_tier`` limita hasta
   dónde puede llegar cada uno: 300 crunches no hacen un core de élite.

**Los números siguen siendo provisionales** (decisión D9, abierta). Son
estándares de calistenia razonados, no medidos, y se ajustarán con historial
real. La diferencia con v1 es que ahora son discutibles mirando referencias
publicadas, en vez de derivados de una regla inventada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import TIER_LADDER, Tier
from .tiers import TIER_THRESHOLDS

#: Cuántos umbrales tiene una escalera: uno por rango de ``TIER_LADDER``.
LADDER_STEPS = len(TIER_LADDER)


@dataclass(frozen=True, slots=True)
class ExerciseStandard:
    """Escalera de un ejercicio.

    ``thresholds`` son las marcas —repeticiones para los ejercicios de reps,
    segundos para los isométricos— que corresponden a cada rango, de Iron a
    Radiant. Estrictamente crecientes.
    """

    thresholds: tuple[float, ...]
    #: Rango máximo que este ejercicio puede otorgar por sí solo. Un ejercicio
    #: de poca resistencia no debe poder dar rango alto por muchas
    #: repeticiones que se hagan.
    max_tier: Tier = Tier.RADIANT
    #: Peso con el que se calibró la escalera, para los ejercicios de carga
    #: externa. Usar más peso cuenta proporcionalmente más, de modo que subir
    #: la carga nunca hace bajar de rango. ``None`` = se deduce del historial.
    reference_weight_kg: float | None = None
    #: Marca fuera de la cual la escalera no está calibrada todavía. Se declara
    #: en vez de disimularlo: la UI lo presenta como provisional.
    provisional: bool = False

    def __post_init__(self) -> None:
        if len(self.thresholds) != LADDER_STEPS:
            raise ValueError(f"una escalera necesita {LADDER_STEPS} umbrales")
        if any(b <= a for a, b in zip(self.thresholds, self.thresholds[1:], strict=False)):
            raise ValueError("los umbrales deben ser estrictamente crecientes")


# --------------------------------------------------------------------------
# Escaleras
# --------------------------------------------------------------------------

_R = Tier.RADIANT
_I, _B, _S, _G = Tier.IRON, Tier.BRONZE, Tier.SILVER, Tier.GOLD
_P, _D = Tier.PLATINUM, Tier.DIAMOND

#: Escalera genérica para un ejercicio todavía sin calibrar. Conservadora a
#: propósito: es mejor que un ejercicio nuevo puntúe bajo a que regale rango.
DEFAULT_REPS = ExerciseStandard((10, 20, 32, 45, 60, 78, 96, 118, 140), _G, provisional=True)
DEFAULT_TIME = ExerciseStandard((15, 35, 60, 95, 140, 190, 250, 320, 400), _G, provisional=True)

STANDARDS: dict[str, ExerciseStandard] = {
    # --- Tracción vertical -------------------------------------------------
    # 30 dominadas estrictas seguidas ya son una marca notable; 60 es el techo
    # de la escalera y un proyecto de años.
    "dominadas": ExerciseStandard((3, 8, 15, 25, 33, 40, 47, 53, 60), _R),
    "dominadas_abiertas": ExerciseStandard((3, 8, 15, 25, 33, 40, 47, 53, 60), _R),
    "dominadas_mixtas": ExerciseStandard((3, 8, 15, 25, 33, 40, 47, 53, 60), _R),
    # El lastre entra multiplicando la marca, así que comparte escalera.
    "dominadas_lastradas": ExerciseStandard((3, 8, 15, 25, 33, 40, 47, 53, 60), _R),
    # Con asistencia no se demuestra fuerza máxima: no puede dar rango alto.
    "dominadas_asistidas": ExerciseStandard((5, 12, 20, 30, 40, 50, 60, 70, 80), _S),
    "remo_invertido": ExerciseStandard((8, 16, 26, 38, 50, 64, 78, 94, 110), _D),
    "jalon_polea": DEFAULT_REPS,
    # --- Empuje horizontal -------------------------------------------------
    "flexiones": ExerciseStandard((10, 20, 30, 45, 60, 80, 100, 125, 150), _R),
    "flexiones_abiertas": ExerciseStandard((10, 20, 30, 45, 60, 80, 100, 125, 150), _R),
    "flexiones_declinadas": ExerciseStandard((8, 16, 26, 38, 52, 68, 85, 105, 130), _R),
    "flexiones_diamante": ExerciseStandard((5, 12, 20, 30, 40, 55, 70, 85, 100), _R),
    "flexiones_arquero": ExerciseStandard((3, 8, 14, 22, 30, 40, 50, 62, 75), _R),
    "flexiones_rodillas": ExerciseStandard((10, 25, 40, 60, 85, 115, 150, 190, 235), _B),
    "fondos_paralelas": ExerciseStandard((5, 12, 22, 32, 42, 52, 62, 71, 80), _R),
    "fondos_banco": ExerciseStandard((10, 20, 32, 45, 60, 75, 92, 110, 130), _S),
    # --- Empuje vertical ---------------------------------------------------
    "pike_push_up": ExerciseStandard((5, 10, 18, 28, 38, 50, 62, 75, 90), _R),
    # --- Core --------------------------------------------------------------
    "elevacion_piernas_colgado": ExerciseStandard((5, 12, 20, 30, 38, 45, 51, 56, 60), _R),
    # Crunch y toque de talón son de resistencia, no de fuerza: por muchos que
    # se hagan no demuestran un core fuerte, y el techo lo dice.
    "crunch": ExerciseStandard((20, 50, 80, 120, 170, 230, 300, 400, 520), _S),
    "russian_twist": ExerciseStandard((20, 50, 80, 120, 170, 230, 300, 400, 520), _S),
    "toque_talon": ExerciseStandard((40, 100, 160, 240, 340, 460, 600, 780, 1000), _B),
    "hollow_body": ExerciseStandard((10, 25, 45, 70, 105, 145, 190, 240, 300), _D),
    "plancha": ExerciseStandard((20, 45, 75, 120, 180, 240, 300, 400, 500), _D),
    "plancha_lateral": ExerciseStandard((15, 35, 60, 90, 135, 180, 240, 300, 380), _D),
    "superman": ExerciseStandard((15, 35, 60, 90, 130, 175, 225, 280, 340), _S),
    "hiperextensiones": ExerciseStandard((15, 30, 50, 75, 105, 140, 180, 225, 275), _S),
    # --- Pierna ------------------------------------------------------------
    "sentadilla_corporal": ExerciseStandard((20, 40, 65, 95, 130, 170, 215, 265, 320), _G),
    "sentadilla_bulgara": ExerciseStandard((8, 16, 26, 38, 52, 68, 85, 105, 125), _D),
    "zancadas": ExerciseStandard((10, 20, 34, 50, 68, 88, 110, 135, 160), _G),
    "puente_gluteo": ExerciseStandard((15, 35, 60, 90, 125, 165, 210, 260, 320), _S),
    "elevacion_gemelos": ExerciseStandard((30, 60, 100, 150, 210, 280, 360, 450, 550), _G),
    # --- Cardio y movilidad: cuentan como actividad, no como desarrollo ----
    "saltos_cuerda": ExerciseStandard((50, 100, 180, 280, 400, 550, 720, 920, 1150), _B),
    "jumping_jacks": ExerciseStandard((30, 70, 120, 190, 270, 370, 480, 610, 760), _B),
    "colgarse_barra": ExerciseStandard((20, 45, 75, 120, 180, 240, 310, 390, 480), _G),
    "movilidad_hombro": ExerciseStandard((30, 60, 100, 150, 210, 280, 360, 450, 550), _I),
    # --- Carga externa, calibrada con las mancuernas de casa ---------------
    # La escalera está en repeticiones al peso de referencia. Usar más peso
    # multiplica la marca, así que subir carga también sube rango.
    "aperturas": ExerciseStandard((8, 15, 22, 30, 38, 46, 54, 62, 70), _D, 11.0),
    "arnold_press": ExerciseStandard((5, 10, 16, 24, 32, 40, 48, 56, 65), _D, 14.5),
    "curl_mancuernas": ExerciseStandard((8, 15, 24, 34, 44, 54, 64, 74, 85), _D, 14.5),
    "curl_martillo": ExerciseStandard((8, 15, 24, 34, 44, 54, 64, 74, 85), _D, 14.5),
    "curl_barra": ExerciseStandard((8, 15, 24, 34, 44, 54, 64, 74, 85), _D, 14.5),
    "curl_arm_blaster": ExerciseStandard((8, 15, 24, 34, 44, 54, 64, 74, 85), _D, 11.0),
    "encogimientos": ExerciseStandard((25, 50, 80, 120, 170, 230, 300, 380, 460), _S, 14.5),
    "sentadilla_goblet": ExerciseStandard((10, 20, 32, 45, 60, 80, 100, 125, 150), _G, 14.5),
}


def standard_for(slug: str, *, is_time_based: bool = False) -> ExerciseStandard:
    """Escalera de un ejercicio, o la genérica si aún no está calibrado."""
    found = STANDARDS.get(slug)
    if found is not None:
        return found
    return DEFAULT_TIME if is_time_based else DEFAULT_REPS


# --------------------------------------------------------------------------
# Marca ↔ puntuación
# --------------------------------------------------------------------------


def cap_for(max_tier: Tier) -> float:
    """Puntuación máxima que puede dar un ejercicio con ese techo.

    Justo por debajo del umbral del rango siguiente: con techo Silver se puede
    llegar a lo más alto de Silver, nunca a Gold.
    """
    if max_tier is Tier.RADIANT:
        return 100.0
    if max_tier is Tier.SIN_DATOS:  # pragma: no cover - defensivo
        return 0.0
    upper = TIER_LADDER[TIER_LADDER.index(max_tier) + 1]
    return TIER_THRESHOLDS[upper] - 0.01


def score_for_mark(mark: float, standard: ExerciseStandard) -> float:
    """Puntuación 0–100 de una marca en su escalera.

    Interpola linealmente entre umbrales, de modo que **cada repetición
    cuenta**: la barra de progreso se mueve sin esperar a cambiar de rango.
    """
    thresholds = standard.thresholds
    scores = [TIER_THRESHOLDS[t] for t in TIER_LADDER]

    if mark <= thresholds[0]:
        # El primer umbral ya vale 0 puntos (Iron): por debajo no hay escalera
        # que repartir, y decir "0" es más honesto que inventar una fracción.
        return 0.0
    if mark >= thresholds[-1]:
        raw = 100.0
    else:
        raw = scores[-1]
        for i in range(len(thresholds) - 1):
            low, high = thresholds[i], thresholds[i + 1]
            if low <= mark < high:
                fraction = (mark - low) / (high - low)
                raw = scores[i] + fraction * (scores[i + 1] - scores[i])
                break

    return min(raw, cap_for(standard.max_tier))


def tier_cap_reached(mark: float, standard: ExerciseStandard) -> bool:
    """Si el ejercicio ya no puede dar más rango por su propio techo.

    Se dice en la ficha del músculo: seguir sumando repeticiones de crunch no
    va a mover nada, y ocultarlo sería dejar al usuario entrenando en vano.
    """
    return standard.max_tier is not Tier.RADIANT and score_for_mark(mark, standard) >= cap_for(
        standard.max_tier
    )


def mark_for_score(score: float, standard: ExerciseStandard) -> float | None:
    """Marca necesaria para alcanzar una puntuación. Inversa de :func:`score_for_mark`.

    Devuelve ``None`` si esa puntuación queda por encima del techo del
    ejercicio: no hay número de repeticiones que la alcance, y decirlo es más
    útil que dar una cifra imposible.
    """
    if score > cap_for(standard.max_tier) + 1e-9:
        return None

    thresholds = standard.thresholds
    scores = [TIER_THRESHOLDS[t] for t in TIER_LADDER]
    if score <= scores[0]:
        return thresholds[0]

    for i in range(len(thresholds) - 1):
        if scores[i] <= score <= scores[i + 1]:
            span = scores[i + 1] - scores[i]
            fraction = (score - scores[i]) / span if span else 0.0
            return thresholds[i] + fraction * (thresholds[i + 1] - thresholds[i])
    return thresholds[-1]
