"""Ranking muscular v1.

Los valores exactos son provisionales; lo que se fija aquí son las
**propiedades** que cualquier versión futura de la fórmula debe conservar.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitup.domain.enums import Tier
from fitup.domain.ranking.tiers import (
    TIER_THRESHOLDS,
    next_tier,
    points_to_next_tier,
    tier_for,
)
from fitup.domain.ranking.v1 import (
    DECAY_FLOOR,
    DEVELOPMENT_WINDOW_DAYS,
    RankingConfig,
    StimulusEvent,
    compute_muscle_score,
)

TODAY = date(2026, 3, 15)
BW = 75.0
CFG = RankingConfig(reference_ratio={"pectoral": 1.2}, default_reference_ratio=1.0)


def ev(days_ago: int, e1rm: float | None = 60.0, *, slug="press_banca", role=1.0, volume=1500.0):
    return StimulusEvent(
        date=TODAY - timedelta(days=days_ago),
        exercise_slug=slug,
        role_factor=role,
        volume_kg=volume,
        e1rm_kg=e1rm,
    )


def score(events, *, bodyweight=BW, today=TODAY, muscle="pectoral"):
    return compute_muscle_score(muscle, events, today=today, bodyweight_kg=bodyweight, config=CFG)


# --------------------------------------------------------------------------
# Escalera de rangos
# --------------------------------------------------------------------------


def test_la_escalera_de_umbrales_es_estrictamente_creciente():
    values = list(TIER_THRESHOLDS.values())
    assert values == sorted(values)
    assert len(set(values)) == len(values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, Tier.IRON),
        (11.9, Tier.IRON),
        (12.0, Tier.BRONZE),
        (56.0, Tier.PLATINUM),
        (97.0, Tier.RADIANT),
        (100.0, Tier.RADIANT),
    ],
)
def test_umbral_a_rango(value, expected):
    assert tier_for(value) is expected


def test_el_rango_es_monotono_respecto_a_la_puntuacion():
    previous = -1
    ladder = list(TIER_THRESHOLDS)
    for s in range(0, 101):
        idx = ladder.index(tier_for(float(s)))
        assert idx >= previous
        previous = idx


def test_radiant_no_tiene_siguiente_rango():
    assert next_tier(Tier.RADIANT) is None
    assert points_to_next_tier(99.0) is None


def test_puntos_para_el_siguiente_rango_son_accionables():
    """La ficha de músculo debe poder decir qué falta, no solo dónde estás."""
    assert points_to_next_tier(10.0) == pytest.approx(2.0)


# --------------------------------------------------------------------------
# Sin datos ≠ Iron
# --------------------------------------------------------------------------


def test_musculo_sin_estimulos_es_sin_datos_no_iron():
    """ "No medido" y "débil" son cosas distintas: cuello y antebrazos mentirían."""
    result = score([])
    assert result.tier is Tier.SIN_DATOS
    assert not result.has_data
    assert result.notes


def test_sin_peso_corporal_no_se_inventa_un_rango():
    result = score([ev(2)], bodyweight=None)
    assert result.tier is Tier.SIN_DATOS
    assert any("peso corporal" in n for n in result.notes)


def test_entrenamiento_sin_series_medibles_no_produce_rango():
    result = score([ev(2, e1rm=None)])
    assert result.tier is Tier.SIN_DATOS
    assert any("estimar" in n for n in result.notes)
    # Pero la actividad sí es medible: hubo volumen.
    assert result.activity > 0


# --------------------------------------------------------------------------
# Desarrollo
# --------------------------------------------------------------------------


def test_mas_fuerza_produce_mas_desarrollo():
    weak = score([ev(2, 40.0), ev(9, 40.0)])
    strong = score([ev(2, 90.0), ev(9, 90.0)])
    assert strong.development > weak.development


def test_el_rol_secundario_aporta_menos_que_el_primario():
    primary = score([ev(2, 60.0, role=1.0)])
    secondary = score([ev(2, 60.0, role=0.5)])
    assert secondary.development < primary.development


def test_progresar_sube_el_desarrollo_frente_a_solo_acumular():
    """Es el término que hace que aplicar sobrecarga progresiva suba el rango."""
    flat = score([ev(120, 60.0), ev(5, 60.0)])
    improving = score([ev(120, 60.0), ev(5, 72.0)])
    assert improving.development > flat.development
    assert improving.factors["bonus_progresion"] > 0
    assert flat.factors["bonus_progresion"] == 0


def test_la_variedad_aporta_pero_no_sustituye_a_la_fuerza():
    single = score([ev(2, 80.0, slug="press_banca")])
    varied = score([ev(2, 80.0, slug="press_banca"), ev(3, 30.0, slug="aperturas")])
    assert varied.development > single.development
    assert varied.factors["bonus_variedad"] <= 0.30


def test_el_desarrollo_nunca_supera_los_cien_puntos():
    result = score([ev(2, 500.0), ev(60, 100.0)])
    assert result.development <= 100.0


# --------------------------------------------------------------------------
# Decaimiento: descansar no debe castigar
# --------------------------------------------------------------------------


def test_tres_semanas_sin_entrenar_no_penalizan():
    fresh = score([ev(1, 60.0)])
    rested = score([ev(21, 60.0)])
    assert rested.factors["decaimiento"] == 1.0
    assert rested.development == pytest.approx(fresh.development)


def test_el_decaimiento_tiene_suelo_para_no_borrar_el_progreso():
    """Dentro de la ventana, ni tres meses parado hunden el rango más de un escalón."""
    gap = score([ev(DEVELOPMENT_WINDOW_DAYS - 1, 60.0)])
    assert gap.factors["decaimiento"] == pytest.approx(DECAY_FLOOR)
    assert gap.tier is not Tier.SIN_DATOS


def test_el_decaimiento_es_monotono_y_acotado():
    previous = 1.0
    for days in range(0, DEVELOPMENT_WINDOW_DAYS, 7):
        factor = score([ev(days, 60.0)]).factors["decaimiento"]
        assert DECAY_FLOOR - 1e-9 <= factor <= previous + 1e-9
        previous = factor


def test_pasada_la_ventana_el_rango_vuelve_a_sin_datos_no_a_uno_bajo():
    """Sin marcas en seis meses el sistema deja de afirmar una capacidad que ya
    no puede sostener con evidencia: prefiere "no lo sé" a un rango obsoleto."""
    stale = score([ev(DEVELOPMENT_WINDOW_DAYS + 1, 60.0)])
    assert stale.tier is Tier.SIN_DATOS
    assert any("Sin marcas" in n for n in stale.notes)


# --------------------------------------------------------------------------
# Actividad: métrica distinta, no el rango
# --------------------------------------------------------------------------


def test_la_actividad_refleja_el_presente_y_el_desarrollo_no():
    """La separación de ADR-0003: entrenar hoy y ser fuerte no son lo mismo."""
    recent = score([ev(1, 60.0), ev(3, 60.0), ev(5, 60.0)])
    stale = score([ev(70, 60.0), ev(72, 60.0), ev(74, 60.0)])

    assert recent.activity > stale.activity
    assert stale.activity == 0.0  # fuera de la ventana de 28 días
    assert stale.development > 0  # pero la capacidad sigue ahí
    assert stale.tier is not Tier.SIN_DATOS


def test_mas_volumen_reciente_es_mas_actividad():
    low = score([ev(2, 60.0, volume=500.0)])
    high = score([ev(2, 60.0, volume=5000.0)])
    assert high.activity > low.activity


def test_la_actividad_esta_acotada_a_cien():
    huge = [ev(d, 60.0, volume=100_000.0) for d in range(0, 28)]
    assert score(huge).activity <= 100.0


def test_dias_sin_estimulo_alimentan_el_halo_del_mapa_corporal():
    assert score([ev(9, 60.0)]).days_since_stimulus == 9


# --------------------------------------------------------------------------
# Explicabilidad
# --------------------------------------------------------------------------


def test_el_resultado_explica_de_donde_sale():
    """Un ranking que no se explica es un número mágico, y la IA no puede razonarlo."""
    result = score([ev(2, 60.0), ev(9, 55.0)])
    for key in (
        "mejor_1rm_equivalente_kg",
        "ratio_sobre_peso_corporal",
        "referencia",
        "bonus_variedad",
        "bonus_progresion",
        "decaimiento",
        "actividad",
    ):
        assert key in result.factors


def test_la_referencia_por_musculo_cambia_la_escala():
    events = [ev(2, 60.0)]
    strict = compute_muscle_score(
        "pectoral",
        events,
        today=TODAY,
        bodyweight_kg=BW,
        config=RankingConfig(reference_ratio={"pectoral": 2.0}),
    )
    lenient = compute_muscle_score(
        "pectoral",
        events,
        today=TODAY,
        bodyweight_kg=BW,
        config=RankingConfig(reference_ratio={"pectoral": 0.5}),
    )
    assert lenient.development > strict.development
