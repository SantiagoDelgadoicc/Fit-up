"""Marca de una serie: el dato que alimenta el ranking v2.

Es la pieza que sustituye a Epley. Lo que se fija aquí es que la marca **no
se extrapola** y que la carga solo entra como multiplicador cuando de verdad
cambia respecto a la referencia de la escalera.
"""

from __future__ import annotations

import pytest

from fitup.domain.enums import LoadType, Modality, Tier
from fitup.domain.metrics.load import set_mark
from fitup.domain.models import Exercise, PerformedSet
from fitup.domain.ranking.standards import ExerciseStandard


def ejercicio(
    slug="flexiones", *, load_type=LoadType.CORPORAL, factor=0.64, modality=Modality.REPS
):
    return Exercise(
        slug=slug,
        name=slug,
        modality=modality,
        load_type=load_type,
        load_factor=factor,
    )


def serie(**kwargs):
    base = {"set_no": 1, "completed": True, "is_warmup": False}
    return PerformedSet(**(base | kwargs))


def test_la_marca_de_un_ejercicio_de_reps_son_sus_repeticiones():
    """Sin conversión: 30 flexiones son 30, no "un 1RM de 76 kg"."""
    assert (
        set_mark(ejercicio(), serie(reps=30), bodyweight_kg=60.0, reference_weight_kg=None) == 30.0
    )


def test_la_marca_de_un_isometrico_son_sus_segundos():
    assert (
        set_mark(
            ejercicio(modality=Modality.TIEMPO),
            serie(time_s=90),
            bodyweight_kg=60.0,
            reference_weight_kg=None,
        )
        == 90.0
    )


def test_el_lastre_multiplica_la_marca():
    """Dominadas lastradas valen más que las mismas repeticiones sin lastre."""
    dominadas = ejercicio("dominadas", factor=1.0)
    limpia = set_mark(dominadas, serie(reps=10), bodyweight_kg=60.0, reference_weight_kg=None)
    lastrada = set_mark(
        dominadas, serie(reps=10, weight_kg=12.0), bodyweight_kg=60.0, reference_weight_kg=None
    )
    assert lastrada == pytest.approx(limpia * 72 / 60)


def test_sin_peso_corporal_el_lastre_no_se_inventa():
    """Mejor una marca conservadora que un multiplicador supuesto."""
    dominadas = ejercicio("dominadas", factor=1.0)
    assert (
        set_mark(
            dominadas, serie(reps=10, weight_kg=12.0), bodyweight_kg=None, reference_weight_kg=None
        )
        == 10.0
    )


def test_mas_peso_externo_vale_mas_repeticiones():
    """Subir la carga nunca debe hacer bajar de rango."""
    curl = ejercicio("curl_mancuernas", load_type=LoadType.EXTERNA, factor=0.0)
    igual = set_mark(
        curl, serie(reps=20, weight_kg=14.5), bodyweight_kg=60.0, reference_weight_kg=14.5
    )
    mas = set_mark(
        curl, serie(reps=20, weight_kg=20.0), bodyweight_kg=60.0, reference_weight_kg=14.5
    )
    assert igual == 20.0
    assert mas > igual


def test_calentamiento_y_series_no_completadas_no_dejan_marca():
    assert (
        set_mark(
            ejercicio(),
            serie(reps=30, is_warmup=True),
            bodyweight_kg=60.0,
            reference_weight_kg=None,
        )
        is None
    )
    assert (
        set_mark(
            ejercicio(),
            serie(reps=30, completed=False),
            bodyweight_kg=60.0,
            reference_weight_kg=None,
        )
        is None
    )


def test_una_serie_sin_repeticiones_no_produce_marca():
    assert set_mark(ejercicio(), serie(), bodyweight_kg=60.0, reference_weight_kg=None) is None


def test_una_modalidad_sin_escalera_lo_declara_en_vez_de_aproximar():
    corriendo = ejercicio("carrera", modality=Modality.DISTANCIA)
    assert set_mark(corriendo, serie(reps=5), bodyweight_kg=60.0, reference_weight_kg=None) is None


def test_una_escalera_mal_definida_falla_ruidosamente():
    """Un umbral que no crece produciría rangos incoherentes en silencio."""
    with pytest.raises(ValueError):
        ExerciseStandard((10, 20, 20, 40, 50, 60, 70, 80, 90))
    with pytest.raises(ValueError):
        ExerciseStandard((10, 20, 30), Tier.GOLD)
