"""Escalera de rangos del ranking muscular.

Los umbrales se aplican sobre una puntuación 0–100 de **desarrollo**, no de
actividad: el rango representa capacidad demostrada (ADR-0003). Están
separados de la fórmula a propósito, para poder recalibrarlos sin tocar el
cálculo.
"""

from __future__ import annotations

from ..enums import TIER_LADDER, Tier

#: Puntuación mínima de cada rango. Calibración provisional: los umbrales se
#: ajustarán con datos reales, y por eso viven aislados en esta constante.
TIER_THRESHOLDS: dict[Tier, float] = {
    Tier.IRON: 0.0,
    Tier.BRONZE: 12.0,
    Tier.SILVER: 25.0,
    Tier.GOLD: 40.0,
    Tier.PLATINUM: 55.0,
    Tier.DIAMOND: 68.0,
    Tier.ASCENDANT: 80.0,
    Tier.IMMORTAL: 90.0,
    Tier.RADIANT: 97.0,
}


def tier_for(score: float) -> Tier:
    """Rango correspondiente a una puntuación de desarrollo 0–100."""
    result = Tier.IRON
    for tier in TIER_LADDER:
        if score + 1e-9 >= TIER_THRESHOLDS[tier]:
            result = tier
        else:
            break
    return result


def next_tier(tier: Tier) -> Tier | None:
    """Rango inmediatamente superior, o ``None`` si ya es el máximo."""
    if tier in (Tier.SIN_DATOS, Tier.RADIANT):
        return None
    idx = TIER_LADDER.index(tier)
    return TIER_LADDER[idx + 1] if idx + 1 < len(TIER_LADDER) else None


def points_to_next_tier(score: float) -> float | None:
    """Puntos que faltan para subir de rango.

    Alimenta el "qué me falta para el siguiente tier" de la ficha de músculo:
    un ranking que no sabe explicar cómo mejorar no sirve de nada.
    """
    upcoming = next_tier(tier_for(score))
    if upcoming is None:
        return None
    return max(0.0, TIER_THRESHOLDS[upcoming] - score)


def tier_distance(a: Tier, b: Tier) -> int:
    """Número de escalones entre dos rangos. ``SIN_DATOS`` no participa."""
    if a is Tier.SIN_DATOS or b is Tier.SIN_DATOS:
        raise ValueError("SIN_DATOS no forma parte de la escalera")
    return TIER_LADDER.index(a) - TIER_LADDER.index(b)
