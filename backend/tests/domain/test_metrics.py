"""Normalización de carga y volumen."""

from __future__ import annotations

import pytest

from conftest import make_exercise
from fitup.domain.enums import LoadType, Modality
from fitup.domain.metrics.load import (
    LoadUndeterminable,
    effective_load_kg,
    epley_1rm,
    set_e1rm_kg,
    set_volume_kg,
)
from fitup.domain.models import PerformedSet


def test_carga_externa_usa_el_peso_registrado():
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA, load_factor=0.0)
    assert effective_load_kg(ex, weight_kg=60, bodyweight_kg=75) == 60


def test_carga_corporal_usa_la_fraccion_del_peso_corporal():
    ex = make_exercise("flexiones", load_type=LoadType.CORPORAL, load_factor=0.64)
    assert effective_load_kg(ex, weight_kg=None, bodyweight_kg=75) == pytest.approx(48.0)


def test_lastre_se_suma_a_la_carga_corporal():
    ex = make_exercise("dominadas", load_type=LoadType.CORPORAL, load_factor=1.0)
    assert effective_load_kg(ex, weight_kg=10, bodyweight_kg=75) == pytest.approx(85.0)


def test_asistencia_resta_carga_y_nunca_baja_de_cero():
    ex = make_exercise("dominadas_asistidas", load_type=LoadType.ASISTIDA, load_factor=1.0)
    assert effective_load_kg(ex, weight_kg=-30, bodyweight_kg=75) == pytest.approx(45.0)
    assert effective_load_kg(ex, weight_kg=-200, bodyweight_kg=75) == 0.0


def test_sin_peso_registrado_en_carga_externa_se_declara_no_determinable():
    """Asumir un peso por defecto contaminaría todas las métricas derivadas."""
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA)
    with pytest.raises(LoadUndeterminable, match="no registra peso"):
        effective_load_kg(ex, weight_kg=None, bodyweight_kg=75)


def test_sin_peso_corporal_los_ejercicios_de_calistenia_no_son_calculables():
    ex = make_exercise("flexiones", load_type=LoadType.CORPORAL)
    with pytest.raises(LoadUndeterminable, match="peso corporal"):
        effective_load_kg(ex, weight_kg=None, bodyweight_kg=None)


def test_movilidad_sin_carga_vale_cero():
    ex = make_exercise("movilidad", load_type=LoadType.NINGUNA, load_factor=0.0)
    assert effective_load_kg(ex, weight_kg=None, bodyweight_kg=None) == 0.0


# --------------------------------------------------------------------------
# Volumen
# --------------------------------------------------------------------------


def test_volumen_es_carga_por_repeticiones():
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA)
    s = PerformedSet(set_no=1, reps=10, weight_kg=50)
    assert set_volume_kg(ex, s, bodyweight_kg=75) == pytest.approx(500.0)


def test_unilateral_cuenta_por_los_dos_lados():
    ex = make_exercise("bulgara", load_type=LoadType.EXTERNA, is_unilateral=True)
    s = PerformedSet(set_no=1, reps=10, weight_kg=20)
    assert set_volume_kg(ex, s, bodyweight_kg=75) == pytest.approx(400.0)


def test_calentamiento_y_series_no_completadas_no_aportan_estimulo():
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA)
    warmup = PerformedSet(set_no=1, reps=10, weight_kg=50, is_warmup=True)
    failed = PerformedSet(set_no=2, reps=10, weight_kg=50, completed=False)
    assert set_volume_kg(ex, warmup, bodyweight_kg=75) == 0.0
    assert set_volume_kg(ex, failed, bodyweight_kg=75) == 0.0


def test_isometrico_convierte_tiempo_en_repeticiones_equivalentes():
    ex = make_exercise(
        "plancha", modality=Modality.TIEMPO, load_type=LoadType.CORPORAL, load_factor=0.6
    )
    s = PerformedSet(set_no=1, time_s=60)
    # 45 kg de carga · (60 s / 3) reps equivalentes · 0.6 de factor isométrico
    assert set_volume_kg(ex, s, bodyweight_kg=75) == pytest.approx(45.0 * 20 * 0.6)


def test_modalidad_distancia_se_declara_sin_modelo_en_lugar_de_aproximarse():
    ex = make_exercise("carrera", modality=Modality.DISTANCIA, load_type=LoadType.CORPORAL)
    s = PerformedSet(set_no=1, reps=1)
    with pytest.raises(LoadUndeterminable, match="modelo de volumen"):
        set_volume_kg(ex, s, bodyweight_kg=75)


def test_serie_sin_repeticiones_no_se_inventa():
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA)
    s = PerformedSet(set_no=1, reps=None, weight_kg=50)
    with pytest.raises(LoadUndeterminable, match="sin repeticiones"):
        set_volume_kg(ex, s, bodyweight_kg=75)


# --------------------------------------------------------------------------
# 1RM estimado
# --------------------------------------------------------------------------


def test_epley_con_una_repeticion_es_la_carga():
    assert epley_1rm(100, 1) == 100


def test_epley_crece_con_las_repeticiones():
    assert epley_1rm(100, 10) == pytest.approx(133.333, rel=1e-3)
    assert epley_1rm(100, 5) < epley_1rm(100, 10)


def test_epley_rechaza_repeticiones_no_positivas():
    with pytest.raises(ValueError):
        epley_1rm(100, 0)


def test_e1rm_devuelve_none_cuando_no_es_estimable():
    """En el ranking una serie sin datos no aporta; eso no es un error."""
    ex = make_exercise("press_banca", load_type=LoadType.EXTERNA)
    assert set_e1rm_kg(ex, PerformedSet(set_no=1, reps=5), bodyweight_kg=75) is None
    assert (
        set_e1rm_kg(
            ex, PerformedSet(set_no=1, reps=5, weight_kg=50, is_warmup=True), bodyweight_kg=75
        )
        is None
    )
