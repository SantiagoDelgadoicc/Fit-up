"""Normalización de carga y volumen.

El problema que resuelve este módulo: una plancha, una flexión y un press
banca no son comparables tal cual, pero el ranking muscular necesita sumarlos.
Todo se convierte a **kilogramos equivalentes** mediante ``load_factor``.

Esa conversión es una aproximación **documentada y editable**, no una verdad
física. La UI debe presentarla como tal.
"""

from __future__ import annotations

from ..enums import LoadType, Modality
from ..models import Exercise, PerformedSet

#: Segundos de isométrico considerados equivalentes a una repetición.
#: Convención, no biomecánica: sirve para que las planchas no queden fuera del
#: cómputo, y es ajustable sin tocar datos.
SECONDS_PER_REP_EQUIVALENT = 3.0

#: Los isométricos generan menos daño mecánico por unidad de tiempo que el
#: trabajo dinámico con la misma carga.
ISOMETRIC_FACTOR = 0.6


class LoadUndeterminable(ValueError):
    """La carga de una serie no puede calcularse con los datos disponibles.

    Se lanza en lugar de asumir un valor. Es la traducción a código de la
    regla "si el sistema no puede determinarlo con seguridad, lo indica".
    """


def effective_load_kg(
    exercise: Exercise,
    *,
    weight_kg: float | None,
    bodyweight_kg: float | None,
) -> float:
    """Carga efectiva de una serie, en kilogramos equivalentes.

    - ``externa``  → el peso registrado.
    - ``corporal`` → fracción del peso corporal + lastre opcional.
    - ``asistida`` → fracción del peso corporal menos la asistencia
      (``weight_kg`` negativo), con suelo en 0.
    - ``ninguna``  → 0.

    Lanza :class:`LoadUndeterminable` si faltan datos imprescindibles, en vez
    de inventar un valor por defecto que contaminaría las métricas.
    """
    if exercise.load_type is LoadType.NINGUNA:
        return 0.0

    if exercise.load_type is LoadType.EXTERNA:
        if weight_kg is None:
            raise LoadUndeterminable(
                f"'{exercise.slug}' es de carga externa y la serie no registra peso"
            )
        return max(0.0, weight_kg)

    # Corporal o asistida: hace falta saber cuánto pesa el usuario.
    if bodyweight_kg is None:
        raise LoadUndeterminable(
            f"'{exercise.slug}' depende del peso corporal y no hay registro de peso"
        )

    base = bodyweight_kg * exercise.load_factor
    return max(0.0, base + (weight_kg or 0.0))


def set_volume_kg(
    exercise: Exercise,
    performed: PerformedSet,
    *,
    bodyweight_kg: float | None,
) -> float:
    """Volumen de una serie en kg equivalentes.

    Las series no completadas y las de calentamiento aportan 0: representan
    esfuerzo, no estímulo computable.
    """
    if performed.is_warmup or not performed.completed:
        return 0.0

    load = effective_load_kg(exercise, weight_kg=performed.weight_kg, bodyweight_kg=bodyweight_kg)
    laterality = 2.0 if exercise.is_unilateral else 1.0

    if exercise.modality is Modality.REPS:
        if performed.reps is None:
            raise LoadUndeterminable(
                f"serie {performed.set_no} de '{exercise.slug}' sin repeticiones"
            )
        return load * performed.reps * laterality

    if exercise.modality is Modality.TIEMPO:
        if performed.time_s is None:
            raise LoadUndeterminable(f"serie {performed.set_no} de '{exercise.slug}' sin tiempo")
        reps_eq = performed.time_s / SECONDS_PER_REP_EQUIVALENT
        return load * reps_eq * ISOMETRIC_FACTOR * laterality

    # Distancia: sin modelo de carga fiable todavía. Se declara en vez de
    # aproximarlo con un número arbitrario.
    raise LoadUndeterminable(f"la modalidad '{exercise.modality}' aún no tiene modelo de volumen")


def epley_1rm(load_kg: float, reps: int) -> float:
    """Estimación de 1RM por la fórmula de Epley.

    Pierde fiabilidad por encima de ~12 repeticiones; el ranking lo tiene en
    cuenta y no la usa como medida absoluta, sino comparativa contra uno mismo.
    """
    if reps <= 0:
        raise ValueError("reps debe ser > 0")
    if reps == 1:
        return load_kg
    return load_kg * (1.0 + reps / 30.0)


def set_e1rm_kg(
    exercise: Exercise,
    performed: PerformedSet,
    *,
    bodyweight_kg: float | None,
) -> float | None:
    """1RM equivalente de una serie, o ``None`` si no es estimable.

    Devuelve ``None`` en lugar de lanzar: en el cálculo del ranking una serie
    sin datos suficientes simplemente no aporta, y eso no es un error.
    """
    if performed.is_warmup or not performed.completed:
        return None
    try:
        load = effective_load_kg(
            exercise, weight_kg=performed.weight_kg, bodyweight_kg=bodyweight_kg
        )
    except LoadUndeterminable:
        return None

    if exercise.modality is Modality.REPS and performed.reps:
        return epley_1rm(load, performed.reps)

    if exercise.modality is Modality.TIEMPO and performed.time_s:
        reps_eq = performed.time_s / SECONDS_PER_REP_EQUIVALENT
        return epley_1rm(load * ISOMETRIC_FACTOR, max(1, round(reps_eq)))

    return None
