"""Avisos de equilibrio muscular (M7).

Compara grupos antagonistas y avisa cuando uno se queda muy por detrás del
otro. No es un diagnóstico médico ni una regla de oro del entrenamiento: es
una señal para mirar el plan, y así se redacta.

Función pura sobre puntuaciones de desarrollo ya calculadas. Dos cosas que
hace explícitamente:

- **No compara lo que no puede.** Si un lado no tiene datos, el resultado es
  ``SIN_DATOS`` con el motivo, nunca un desequilibrio inventado.
- **Compara desarrollo, no actividad.** Un desequilibrio es de capacidad; que
  esta semana hayas entrenado más empuje que tirón no lo es.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: Fuera de esta horquilla, la diferencia entre antagonistas se considera
#: reseñable. Amplia a propósito: un 20 % de diferencia entre empuje y tirón
#: es normal y avisar de ella sería ruido.
BALANCED_LOW = 0.75
BALANCED_HIGH = 1.0 / BALANCED_LOW


class BalanceVerdict(StrEnum):
    EQUILIBRADO = "equilibrado"
    DESEQUILIBRIO = "desequilibrio"
    SIN_DATOS = "sin_datos"


@dataclass(frozen=True, slots=True)
class BalancePair:
    """Definición de un par antagonista a vigilar."""

    key: str
    name: str
    left_name: str
    right_name: str
    left: tuple[str, ...]
    right: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BalanceCheck:
    key: str
    name: str
    verdict: BalanceVerdict
    message: str
    left_name: str
    right_name: str
    left_score: float | None = None
    right_score: float | None = None
    ratio: float | None = None
    #: Músculos del par que aún no tienen desarrollo medible.
    missing: tuple[str, ...] = ()


#: Los dos pares que el plan pedía vigilar. Se eligieron porque su
#: desequilibrio es el más común y el que más se asocia a molestias: hombro en
#: el primer caso, rodilla en el segundo.
PAIRS: tuple[BalancePair, ...] = (
    BalancePair(
        key="empuje_tiron",
        name="Empuje y tirón",
        left_name="Empuje",
        right_name="Tirón",
        left=("pectoral", "deltoide_anterior", "triceps"),
        right=("dorsal_ancho", "romboides", "biceps"),
    ),
    BalancePair(
        key="cuadriceps_femoral",
        name="Cuádriceps e isquiotibiales",
        left_name="Cuádriceps",
        right_name="Isquiotibiales",
        left=("cuadriceps",),
        right=("isquiotibiales", "gluteo"),
    ),
)


def check_balance(
    development: dict[str, float | None], *, pairs: tuple[BalancePair, ...] = PAIRS
) -> list[BalanceCheck]:
    """Evalúa cada par antagonista.

    ``development`` lleva la puntuación de desarrollo por músculo, o ``None``
    para los que no tienen rango determinable.
    """
    return [_check(pair, development) for pair in pairs]


def _check(pair: BalancePair, development: dict[str, float | None]) -> BalanceCheck:
    left, missing_left = _side_score(pair.left, development)
    right, missing_right = _side_score(pair.right, development)
    missing = missing_left + missing_right

    if left is None or right is None:
        ausentes = ", ".join(missing) or "los dos lados"
        return BalanceCheck(
            key=pair.key,
            name=pair.name,
            verdict=BalanceVerdict.SIN_DATOS,
            message=f"Sin rango todavía en {ausentes}: no hay con qué comparar",
            left_name=pair.left_name,
            right_name=pair.right_name,
            left_score=left,
            right_score=right,
            missing=missing,
        )

    if right <= 0:
        # Con un lado a cero cualquier cociente sería infinito o engañoso.
        return BalanceCheck(
            key=pair.key,
            name=pair.name,
            verdict=BalanceVerdict.SIN_DATOS,
            message=f"{pair.right_name} está a cero: no hay proporción que calcular",
            left_name=pair.left_name,
            right_name=pair.right_name,
            left_score=left,
            right_score=right,
            missing=missing,
        )

    ratio = left / right
    if BALANCED_LOW <= ratio <= BALANCED_HIGH:
        message = f"{pair.left_name} y {pair.right_name} van parejos"
        verdict = BalanceVerdict.EQUILIBRADO
    else:
        fuerte, debil = (
            (pair.left_name, pair.right_name) if ratio > 1 else (pair.right_name, pair.left_name)
        )
        desvio = ratio if ratio > 1 else 1 / ratio
        message = (
            f"{fuerte} va un {round((desvio - 1) * 100)} % por delante de {debil}. "
            f"Añadir trabajo de {debil.lower()} equilibraría el plan"
        )
        verdict = BalanceVerdict.DESEQUILIBRIO

    return BalanceCheck(
        key=pair.key,
        name=pair.name,
        verdict=verdict,
        message=message,
        left_name=pair.left_name,
        right_name=pair.right_name,
        left_score=round(left, 2),
        right_score=round(right, 2),
        ratio=round(ratio, 3),
        missing=missing,
    )


def _side_score(
    muscles: tuple[str, ...], development: dict[str, float | None]
) -> tuple[float | None, tuple[str, ...]]:
    """Media de los músculos con rango, y los que faltan.

    Basta con que uno del lado tenga datos: exigir los tres dejaría el aviso
    mudo casi siempre, porque romboides y deltoide posterior rara vez son
    primarios en algo.
    """
    values = [development.get(m) for m in muscles]
    missing = tuple(m for m, v in zip(muscles, values, strict=True) if v is None)
    known = [v for v in values if v is not None]
    if not known:
        return None, missing
    return sum(known) / len(known), missing
