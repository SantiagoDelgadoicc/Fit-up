"""Motor de sobrecarga progresiva.

Dos familias de test:

- **Comportamiento**: cada estrategia propone lo que debe, y el motor sabe
  decir NOT_YET / UNDETERMINED / DELOAD cuando toca.
- **Invariantes**: barridos sobre rejillas de entradas que comprueban que las
  guardas no se violan *nunca*, no solo en los casos que se me ocurrieron.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from conftest import history, make_exercise, performed, planned, rule
from fitup.domain.enums import Modality, ProgressionOutcome, Strategy
from fitup.domain.models import Guards, PerformedExercise, PerformedSet, PlannedSet
from fitup.domain.progression.engine import describe_sets, evaluate

TODAY = date(2026, 3, 15)
D1, D2, D3 = TODAY - timedelta(days=7), TODAY - timedelta(days=4), TODAY - timedelta(days=1)


def run(*, exercise=None, plan=None, r=None, hist=None, last_progression=None, today=TODAY):
    return evaluate(
        exercise=exercise or make_exercise(),
        planned=plan if plan is not None else planned(),
        rule=r,
        history=hist if hist is not None else [],
        today=today,
        last_progression_date=last_progression,
    )


def two_good_sessions(**kw):
    return history((D2, performed(**kw)), (D3, performed(**kw)))


# --------------------------------------------------------------------------
# Puertas previas
# --------------------------------------------------------------------------


def test_sin_regla_es_indeterminado_no_una_suposicion():
    result = run(r=None, hist=two_good_sessions())
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "regla de progresión" in result.reason


def test_regla_manual_nunca_propone():
    result = run(r=rule(Strategy.MANUAL), hist=two_good_sessions())
    assert result.outcome is ProgressionOutcome.NOT_YET
    assert result.proposal is None


def test_no_progresa_con_historial_insuficiente():
    """Regla R12: hacen falta al menos dos sesiones registradas."""
    result = run(r=rule(Strategy.REPS_LINEAL), hist=history((D3, performed())))
    assert result.outcome is ProgressionOutcome.NOT_YET
    assert "Falta" in result.reason


def test_respeta_el_cooldown_entre_progresiones():
    result = run(
        r=rule(Strategy.REPS_LINEAL, guards=Guards(cooldown_days=7)),
        hist=two_good_sessions(),
        last_progression=TODAY - timedelta(days=3),
    )
    assert result.outcome is ProgressionOutcome.NOT_YET
    assert "margen mínimo" in result.reason


def test_cooldown_cumplido_permite_progresar():
    result = run(
        r=rule(Strategy.REPS_LINEAL, guards=Guards(cooldown_days=7)),
        hist=two_good_sessions(),
        last_progression=TODAY - timedelta(days=8),
    )
    assert result.outcome is ProgressionOutcome.READY


def test_no_progresa_si_la_ultima_sesion_no_alcanzo_el_objetivo():
    hist = history((D2, performed(reps=15)), (D3, performed(reps=12)))
    result = run(r=rule(Strategy.REPS_LINEAL), hist=hist)
    assert result.outcome is ProgressionOutcome.NOT_YET
    assert "no alcanzó el objetivo" in result.reason


def test_no_progresa_si_alguna_serie_quedo_sin_completar():
    hist = history((D2, performed()), (D3, performed(completed=False)))
    assert run(r=rule(Strategy.REPS_LINEAL), hist=hist).outcome is ProgressionOutcome.NOT_YET


def test_rir_cero_bloquea_la_progresion():
    """Subir desde el fallo muscular es justo la subida irresponsable a evitar."""
    hist = two_good_sessions(rir=0)
    assert run(r=rule(Strategy.REPS_LINEAL), hist=hist).outcome is ProgressionOutcome.NOT_YET


def test_rir_holgado_permite_progresar():
    hist = two_good_sessions(rir=2)
    assert run(r=rule(Strategy.REPS_LINEAL), hist=hist).outcome is ProgressionOutcome.READY


def test_datos_incompletos_dan_indeterminado_no_un_no_todavia():
    """Faltan repeticiones: el sistema no puede saber si se cumplió el objetivo."""
    hist = two_good_sessions(reps=None)
    result = run(r=rule(Strategy.REPS_LINEAL), hist=hist)
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "sin datos suficientes" in result.reason


# --------------------------------------------------------------------------
# Estrategias
# --------------------------------------------------------------------------


def test_reps_lineal_sube_todas_las_series():
    """El caso del enunciado: flexiones 3x15 → 3x16."""
    result = run(r=rule(Strategy.REPS_LINEAL), hist=two_good_sessions())
    assert result.outcome is ProgressionOutcome.READY
    assert result.proposal.summary == "3x15 → 3x16"
    assert all(s.target_reps == 16 for s in result.proposal.sets)


def test_reps_lineal_en_el_techo_declara_indeterminado_en_vez_de_inventar():
    """Al llegar al tope, la regla no sabe seguir. Decirlo es lo correcto."""
    plan = planned(reps=20)
    result = run(
        plan=plan,
        r=rule(Strategy.REPS_LINEAL, params={"rep_max": 20}),
        hist=two_good_sessions(reps=20),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "techo de 20 repeticiones" in result.reason
    assert "variante" in result.reason


def test_doble_progresion_sube_repeticiones_bajo_el_techo():
    plan = planned(reps=10, weight=40)
    result = run(
        plan=plan,
        r=rule(Strategy.DOBLE_PROGRESION, params={"rep_min": 8, "rep_max": 12}),
        hist=two_good_sessions(reps=10, weight=40),
    )
    assert result.outcome is ProgressionOutcome.READY
    assert all(s.target_reps == 11 for s in result.proposal.sets)
    assert all(s.target_weight_kg == 40 for s in result.proposal.sets)


def test_doble_progresion_en_el_techo_sube_peso_y_reinicia_repeticiones():
    plan = planned(reps=12, weight=40)
    result = run(
        plan=plan,
        r=rule(
            Strategy.DOBLE_PROGRESION,
            params={"rep_min": 8, "rep_max": 12, "incremento_peso": 2.5},
        ),
        hist=two_good_sessions(reps=12, weight=40),
    )
    assert result.outcome is ProgressionOutcome.READY
    assert all(s.target_reps == 8 for s in result.proposal.sets)
    assert all(s.target_weight_kg == pytest.approx(42.5) for s in result.proposal.sets)


def test_doble_progresion_sin_techo_definido_es_indeterminada():
    result = run(
        plan=planned(reps=12, weight=40),
        r=rule(Strategy.DOBLE_PROGRESION, params={"rep_min": 8}),
        hist=two_good_sessions(reps=12, weight=40),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "rep_max" in result.reason


def test_doble_progresion_en_el_techo_sin_peso_no_deduce_cuanto_anadir():
    result = run(
        plan=planned(reps=12),
        r=rule(Strategy.DOBLE_PROGRESION, params={"rep_min": 8, "rep_max": 12}),
        hist=two_good_sessions(reps=12),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "no registra peso" in result.reason


def test_peso_lineal_suma_el_incremento():
    result = run(
        plan=planned(reps=8, weight=50),
        r=rule(Strategy.PESO_LINEAL, params={"incremento": 2.5}),
        hist=two_good_sessions(reps=8, weight=50),
    )
    assert result.outcome is ProgressionOutcome.READY
    assert all(s.target_weight_kg == pytest.approx(52.5) for s in result.proposal.sets)


def test_peso_lineal_sin_peso_planificado_es_indeterminado():
    result = run(
        plan=planned(reps=8),
        r=rule(Strategy.PESO_LINEAL),
        hist=two_good_sessions(reps=8),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED


def test_series_anade_una_serie():
    result = run(
        r=rule(Strategy.SERIES, params={"set_max": 5}),
        hist=two_good_sessions(),
    )
    assert result.outcome is ProgressionOutcome.READY
    assert len(result.proposal.sets) == 4
    assert result.proposal.sets[-1].set_no == 4


def test_series_en_el_techo_es_indeterminado():
    result = run(
        plan=planned(sets=5),
        r=rule(Strategy.SERIES, params={"set_max": 5}),
        hist=two_good_sessions(sets=5),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "techo de 5 series" in result.reason


def test_tiempo_suma_segundos():
    ex = make_exercise("plancha", modality=Modality.TIEMPO)
    plan = planned(reps=None, time_s=45)
    hist = history((D2, performed(reps=None, time_s=45)), (D3, performed(reps=None, time_s=45)))
    result = run(
        exercise=ex,
        plan=plan,
        r=rule(Strategy.TIEMPO, params={"incremento_s": 5, "tiempo_max": 120}),
        hist=hist,
    )
    assert result.outcome is ProgressionOutcome.READY
    assert all(s.target_time_s == 50 for s in result.proposal.sets)


def test_variante_propone_el_siguiente_ejercicio_de_la_cadena():
    ex = make_exercise("flexiones", next_variant="flexiones_declinadas")
    result = run(exercise=ex, r=rule(Strategy.VARIANTE), hist=two_good_sessions())
    assert result.outcome is ProgressionOutcome.READY
    assert result.proposal.next_exercise_slug == "flexiones_declinadas"


def test_variante_sin_siguiente_definida_es_indeterminada():
    result = run(
        exercise=make_exercise("flexiones", next_variant=None),
        r=rule(Strategy.VARIANTE),
        hist=two_good_sessions(),
    )
    assert result.outcome is ProgressionOutcome.UNDETERMINED
    assert "siguiente de la cadena" in result.reason


# --------------------------------------------------------------------------
# Regresión y descarga
# --------------------------------------------------------------------------


def test_dos_regresiones_seguidas_sugieren_descarga_no_subida():
    hist = history(
        (TODAY - timedelta(days=14), performed(reps=12, weight=50)),
        (D1, performed(reps=10, weight=50)),
        (D2, performed(reps=8, weight=50)),
    )
    result = run(
        plan=planned(reps=12, weight=50),
        r=rule(Strategy.PESO_LINEAL),
        hist=hist,
    )
    assert result.outcome is ProgressionOutcome.DELOAD_SUGGESTED
    assert result.proposal is not None
    assert all(s.target_weight_kg == pytest.approx(45.0) for s in result.proposal.sets)


def test_una_sola_regresion_no_dispara_la_descarga():
    hist = history((D2, performed(reps=15)), (D3, performed(reps=13)))
    result = run(r=rule(Strategy.REPS_LINEAL), hist=hist)
    assert result.outcome is ProgressionOutcome.NOT_YET


def test_descarga_sin_peso_retira_una_serie():
    hist = history(
        (TODAY - timedelta(days=14), performed(reps=15)),
        (D1, performed(reps=12)),
        (D2, performed(reps=9)),
    )
    result = run(r=rule(Strategy.REPS_LINEAL), hist=hist)
    assert result.outcome is ProgressionOutcome.DELOAD_SUGGESTED
    assert len(result.proposal.sets) == 2


# --------------------------------------------------------------------------
# Invariantes de las guardas
# --------------------------------------------------------------------------


@pytest.mark.parametrize("current_weight", [1.0, 2.5, 20.0, 60.0, 100.0, 180.0])
@pytest.mark.parametrize("step", [1.25, 2.5, 5.0, 10.0, 25.0])
def test_ninguna_propuesta_supera_nunca_el_incremento_maximo_de_carga(current_weight, step):
    """Invariante duro: subir más de un 10 % de golpe no debe ser posible."""
    pct = 0.10
    result = run(
        plan=planned(reps=8, weight=current_weight),
        r=rule(
            Strategy.PESO_LINEAL,
            params={"incremento": step},
            guards=Guards(max_load_increase_pct=pct),
        ),
        hist=two_good_sessions(reps=8, weight=current_weight),
    )
    if result.outcome is not ProgressionOutcome.READY:
        return
    for s in result.proposal.sets:
        assert s.target_weight_kg <= current_weight * (1 + pct) + 1e-6


@pytest.mark.parametrize("start", [5, 10, 14, 19])
@pytest.mark.parametrize("step", [1, 2, 5])
def test_ninguna_propuesta_supera_nunca_el_techo_de_repeticiones(start, step):
    ceiling = 20
    result = run(
        plan=planned(reps=start),
        r=rule(Strategy.REPS_LINEAL, params={"incremento": step, "rep_max": ceiling}),
        hist=two_good_sessions(reps=start),
    )
    if result.outcome is not ProgressionOutcome.READY:
        return
    assert all(s.target_reps <= ceiling for s in result.proposal.sets)


@pytest.mark.parametrize("max_weight", [50.0, 100.0])
def test_el_techo_absoluto_de_peso_nunca_se_rebasa(max_weight):
    current = max_weight - 1.0
    result = run(
        plan=planned(reps=8, weight=current),
        r=rule(
            Strategy.PESO_LINEAL,
            params={"incremento": 10.0},
            guards=Guards(max_weight_kg=max_weight),
        ),
        hist=two_good_sessions(reps=8, weight=current),
    )
    if result.outcome is ProgressionOutcome.READY:
        assert all(s.target_weight_kg <= max_weight + 1e-6 for s in result.proposal.sets)


@pytest.mark.parametrize("strategy", list(Strategy))
def test_ninguna_estrategia_devuelve_ready_sin_propuesta(strategy):
    """Contrato del veredicto: READY siempre trae un plan concreto."""
    ex = make_exercise("flexiones", next_variant="flexiones_declinadas")
    result = run(
        exercise=ex,
        plan=planned(reps=10, weight=40, time_s=None),
        r=rule(strategy, params={"rep_min": 8, "rep_max": 12, "set_max": 5, "tiempo_max": 120}),
        hist=two_good_sessions(reps=10, weight=40),
    )
    assert (result.proposal is not None) == (result.outcome is ProgressionOutcome.READY)


# --------------------------------------------------------------------------
# Calentamiento y descripción
# --------------------------------------------------------------------------


def test_las_series_de_calentamiento_no_se_progresan_ni_se_evaluan():
    plan = planned(reps=10, weight=40)
    plan = plan.__class__(
        exercise_slug=plan.exercise_slug,
        position=plan.position,
        sets=(
            PlannedSet(set_no=0, target_reps=10, target_weight_kg=20, is_warmup=True),
            *plan.sets,
        ),
    )
    warm = PerformedSet(set_no=0, reps=10, weight_kg=20, is_warmup=True)
    perf = PerformedExercise(
        exercise_slug="flexiones",
        position=0,
        sets=(warm, *performed(reps=10, weight=40).sets),
    )
    result = run(
        plan=plan,
        r=rule(Strategy.PESO_LINEAL, params={"incremento": 2.5}),
        hist=history((D2, perf), (D3, perf)),
    )
    assert result.outcome is ProgressionOutcome.READY
    warmups = [s for s in result.proposal.sets if s.is_warmup]
    assert warmups and all(s.target_weight_kg == 20 for s in warmups)


@pytest.mark.parametrize(
    ("sets", "expected"),
    [
        ((PlannedSet(1, target_reps=15), PlannedSet(2, target_reps=15)), "2x15"),
        ((PlannedSet(1, target_reps=8, target_weight_kg=40.0),), "1x8 @ 40kg"),
        ((PlannedSet(1, target_time_s=45),), "1x45s"),
        ((PlannedSet(1, target_reps=12), PlannedSet(2, target_reps=10)), "12 / 10"),
        ((), "sin series"),
    ],
)
def test_descripcion_legible_de_un_plan(sets, expected):
    assert describe_sets(sets) == expected
