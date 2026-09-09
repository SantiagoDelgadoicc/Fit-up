"""Ranking muscular v2.

Los valores exactos de las escaleras son provisionales; lo que se fija aquí
son las **propiedades** que cualquier versión futura de la fórmula debe
conservar. Varias vienen tal cual de v1 —sin datos ≠ Iron, el descanso no
castiga, actividad y desarrollo son cosas distintas— porque no dependían de
cómo se midiera la fuerza, sino de qué significa el rango.

Las propias de v2 son las que motivaron el cambio: la marca no se extrapola,
un día bueno suelto no sube el rango, y un ejercicio ligero no puede dar rango
alto por muchas repeticiones que se acumulen.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitup.domain.enums import Tier
from fitup.domain.ranking.standards import (
    ExerciseStandard,
    cap_for,
    mark_for_score,
    score_for_mark,
    standard_for,
)
from fitup.domain.ranking.tiers import (
    TIER_THRESHOLDS,
    next_tier,
    points_to_next_tier,
    tier_for,
)
from fitup.domain.ranking.v2 import (
    CONFIRMATIONS_REQUIRED,
    DECAY_FLOOR,
    DEVELOPMENT_WINDOW_DAYS,
    StimulusEvent,
    compute_muscle_score,
)

TODAY = date(2026, 3, 15)

#: Escalera de juguete, con umbrales redondos para que los tests se lean.
ESCALERA = ExerciseStandard((10, 20, 30, 40, 50, 60, 70, 80, 90))
#: La misma, pero de un ejercicio ligero: no puede pasar de Silver.
LIGERA = ExerciseStandard((10, 20, 30, 40, 50, 60, 70, 80, 90), Tier.SILVER)


def ev(days_ago: int, mark: float | None = 40.0, *, slug="flexiones", role=1.0, volume=1500.0):
    return StimulusEvent(
        date=TODAY - timedelta(days=days_ago),
        exercise_slug=slug,
        role_factor=role,
        volume_kg=volume,
        mark=mark,
        standard=ESCALERA if mark is not None else None,
    )


def score(events, *, today=TODAY, muscle="pectoral"):
    return compute_muscle_score(muscle, events, today=today)


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
# Escaleras por ejercicio: la marca no se convierte en nada
# --------------------------------------------------------------------------


def test_la_marca_se_mapea_a_su_escalon():
    assert tier_for(score_for_mark(30, ESCALERA)) is Tier.SILVER
    assert tier_for(score_for_mark(40, ESCALERA)) is Tier.GOLD
    assert tier_for(score_for_mark(90, ESCALERA)) is Tier.RADIANT


def test_cada_repeticion_cuenta_dentro_del_escalon():
    """Sin interpolación, la barra de progreso se quedaría quieta entre rangos."""
    assert score_for_mark(35, ESCALERA) > score_for_mark(31, ESCALERA)
    assert tier_for(score_for_mark(35, ESCALERA)) is tier_for(score_for_mark(31, ESCALERA))


def test_la_marca_satura_en_el_tope_de_la_escalera():
    """El fallo que hundió a v1: Epley multiplicaba sin límite a muchas reps."""
    assert score_for_mark(90, ESCALERA) == 100.0
    assert score_for_mark(900, ESCALERA) == 100.0


def test_un_ejercicio_ligero_no_puede_dar_rango_alto():
    """300 crunches no hacen un core de élite, por muchos que sean."""
    assert tier_for(score_for_mark(10_000, LIGERA)) is Tier.SILVER
    assert score_for_mark(10_000, LIGERA) == cap_for(Tier.SILVER)


def test_la_marca_necesaria_es_la_inversa_de_la_puntuacion():
    for mark in (15.0, 33.0, 62.0, 88.0):
        assert mark_for_score(score_for_mark(mark, ESCALERA), ESCALERA) == pytest.approx(mark)


def test_una_puntuacion_sobre_el_techo_no_tiene_marca_posible():
    """Decir "no hay número que valga" es más útil que dar una cifra imposible."""
    assert mark_for_score(90.0, LIGERA) is None


def test_un_ejercicio_sin_calibrar_usa_la_generica_y_lo_declara():
    generic = standard_for("ejercicio_inventado")
    assert generic.provisional
    assert generic.max_tier is not Tier.RADIANT


# --------------------------------------------------------------------------
# Sin datos ≠ Iron
# --------------------------------------------------------------------------


def test_musculo_sin_estimulos_es_sin_datos_no_iron():
    """ "No medido" y "débil" son cosas distintas: cuello y antebrazos mentirían."""
    result = score([])
    assert result.tier is Tier.SIN_DATOS
    assert not result.has_data
    assert result.notes


def test_entrenamiento_sin_series_medibles_no_produce_rango():
    result = score([ev(2, mark=None)])
    assert result.tier is Tier.SIN_DATOS
    assert any("medir una marca" in n for n in result.notes)
    # Pero la actividad sí es medible: hubo volumen.
    assert result.activity > 0


def test_el_rango_ya_no_depende_del_peso_corporal():
    """v1 exigía peso corporal para normalizar; v2 mide repeticiones y no lo necesita."""
    assert score([ev(2, 40.0)]).tier is Tier.GOLD


# --------------------------------------------------------------------------
# Desarrollo
# --------------------------------------------------------------------------


def test_mas_repeticiones_producen_mas_desarrollo():
    weak = score([ev(2, 20.0), ev(9, 20.0)])
    strong = score([ev(2, 60.0), ev(9, 60.0)])
    assert strong.development > weak.development


def test_el_rol_secundario_aporta_menos_que_el_primario():
    primary = score([ev(2, 40.0, role=1.0)])
    secondary = score([ev(2, 40.0, role=0.5)])
    assert secondary.development < primary.development
    assert any("secundario" in n for n in secondary.notes)


def test_manda_el_ejercicio_que_mas_aporta_ya_ponderado_por_rol():
    """Una marca alta como secundario no debe tapar a una menor como principal."""
    result = score(
        [
            ev(2, 80.0, slug="dominadas", role=0.2),
            ev(2, 40.0, slug="flexiones", role=1.0),
        ]
    )
    assert result.leading_exercise == "flexiones"


def test_cuenta_la_mejor_serie_no_la_suma_de_muchas():
    """Acumular volumen no puede sustituir a demostrar capacidad."""
    una_buena = score([ev(2, 60.0), ev(9, 60.0)])
    muchas_flojas = score([ev(d, 20.0) for d in range(2, 20)])
    assert una_buena.development > muchas_flojas.development


def test_un_dia_bueno_suelto_no_sube_el_rango():
    """El trinquete: para que una marca cuente hay que repetirla."""
    suelto = score([ev(2, 90.0), ev(9, 30.0), ev(16, 30.0)])
    confirmado = score([ev(2, 90.0), ev(9, 90.0), ev(16, 30.0)])
    assert confirmado.development > suelto.development
    assert suelto.factors["marca_confirmada"] == 30.0
    assert confirmado.factors["marca_confirmada"] == 90.0


def test_con_una_sola_sesion_la_marca_cuenta_igual():
    """Un dato es un dato: el trinquete gobierna las mejoras, no el estreno."""
    assert score([ev(2, 40.0)]).factors["marca_confirmada"] == 40.0
    assert CONFIRMATIONS_REQUIRED == 2


def test_el_desarrollo_nunca_supera_los_cien_puntos():
    assert score([ev(2, 5000.0), ev(9, 5000.0)]).development <= 100.0


def test_el_siguiente_hito_es_del_musculo_no_del_ejercicio():
    """Con rol secundario hacen falta más repeticiones que las de la escalera.

    Comparar las dos cifras a secas no diría nada —cada uno persigue un rango
    distinto—, así que lo que se comprueba es que para **alcanzar Silver** el
    secundario necesita más que el umbral de Silver del propio ejercicio: dar
    la cifra del ejercicio prometería una subida que no llega.
    """
    secondary = score([ev(2, 40.0, role=0.5)])
    assert secondary.next_tier is Tier.SILVER
    umbral_del_ejercicio = ESCALERA.thresholds[2]  # Silver
    assert secondary.next_mark > umbral_del_ejercicio

    primary = score([ev(2, 30.0, role=1.0)])
    assert primary.next_tier is Tier.GOLD
    assert primary.next_mark == pytest.approx(ESCALERA.thresholds[3])


def test_cuando_el_ejercicio_no_da_para_mas_se_dice():
    result = compute_muscle_score(
        "abdominales",
        [
            StimulusEvent(TODAY, "crunch", 1.0, 1500.0, mark=10_000.0, standard=LIGERA),
            StimulusEvent(TODAY - timedelta(days=7), "crunch", 1.0, 1500.0, 10_000.0, LIGERA),
        ],
        today=TODAY,
    )
    assert result.next_mark is None
    assert any("techo" in n for n in result.notes)


# --------------------------------------------------------------------------
# Decaimiento: descansar no debe castigar
# --------------------------------------------------------------------------


def test_tres_semanas_sin_entrenar_no_penalizan():
    fresh = score([ev(1, 40.0)])
    rested = score([ev(21, 40.0)])
    assert rested.factors["decaimiento"] == 1.0
    assert rested.development == pytest.approx(fresh.development)


def test_el_decaimiento_tiene_suelo_para_no_borrar_el_progreso():
    """Dentro de la ventana, ni tres meses parado hunden el rango más de un escalón."""
    gap = score([ev(DEVELOPMENT_WINDOW_DAYS - 1, 40.0)])
    assert gap.factors["decaimiento"] == pytest.approx(DECAY_FLOOR)
    assert gap.tier is not Tier.SIN_DATOS


def test_el_decaimiento_es_monotono_y_acotado():
    previous = 1.0
    for days in range(0, DEVELOPMENT_WINDOW_DAYS, 7):
        factor = score([ev(days, 40.0)]).factors["decaimiento"]
        assert DECAY_FLOOR - 1e-9 <= factor <= previous + 1e-9
        previous = factor


def test_pasada_la_ventana_el_rango_vuelve_a_sin_datos_no_a_uno_bajo():
    """Sin marcas en seis meses el sistema deja de afirmar una capacidad que ya
    no puede sostener con evidencia: prefiere "no lo sé" a un rango obsoleto."""
    stale = score([ev(DEVELOPMENT_WINDOW_DAYS + 1, 40.0)])
    assert stale.tier is Tier.SIN_DATOS


# --------------------------------------------------------------------------
# Actividad: métrica distinta, no el rango
# --------------------------------------------------------------------------


def test_la_actividad_refleja_el_presente_y_el_desarrollo_no():
    """La separación de ADR-0003: entrenar hoy y ser fuerte no son lo mismo."""
    recent = score([ev(1, 40.0), ev(3, 40.0), ev(5, 40.0)])
    stale = score([ev(70, 40.0), ev(72, 40.0), ev(74, 40.0)])

    assert recent.activity > stale.activity
    assert stale.activity == 0.0  # fuera de la ventana de 28 días
    assert stale.development > 0  # pero la capacidad sigue ahí
    assert stale.tier is not Tier.SIN_DATOS


def test_mas_volumen_reciente_es_mas_actividad():
    low = score([ev(2, 40.0, volume=500.0)])
    high = score([ev(2, 40.0, volume=5000.0)])
    assert high.activity > low.activity


def test_la_actividad_esta_acotada_a_cien():
    huge = [ev(d, 40.0, volume=100_000.0) for d in range(0, 28)]
    assert score(huge).activity <= 100.0


def test_dias_sin_estimulo_alimentan_el_halo_del_mapa_corporal():
    assert score([ev(9, 40.0)]).days_since_stimulus == 9


# --------------------------------------------------------------------------
# Explicabilidad
# --------------------------------------------------------------------------


def test_el_resultado_explica_de_donde_sale():
    """Un ranking que no se explica es un número mágico, y la IA no puede razonarlo."""
    result = score([ev(2, 40.0), ev(9, 35.0)])
    for key in (
        "marca_confirmada",
        "puntuación_del_ejercicio",
        "factor_de_rol",
        "decaimiento",
        "actividad",
    ):
        assert key in result.factors
    assert result.leading_exercise == "flexiones"
    assert result.leading_mark == 35.0
