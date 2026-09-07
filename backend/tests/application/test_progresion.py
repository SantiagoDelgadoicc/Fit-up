"""Casos de uso de sobrecarga progresiva.

El motor ya está probado en `tests/domain/test_progression.py`; aquí se prueba
lo que el dominio no puede hacer: leer historial real, resolver la regla,
escribir una versión nueva sin tocar la anterior y poder deshacerlo.
"""

from __future__ import annotations

from datetime import date

import pytest

from fitup.application.errors import Conflict, Invalid, NotFound
from fitup.application.services import planning as planning_svc
from fitup.application.services import progression as svc
from fitup.application.services import training as training_svc
from fitup.domain.enums import ProgressionOutcome
from fitup.domain.models import PerformedExercise, PerformedSet
from helpers_app import plan

TODAY = date(2026, 3, 15)  # domingo
MONDAY = date(2026, 3, 9)
WEDNESDAY = date(2026, 3, 11)
FRIDAY = date(2026, 3, 13)


def item(evaluation, slug):
    return next(i for i in evaluation.items if i.exercise_slug == slug)


def train(db, *days):
    """Registra los días indicados exactamente como estaban planificados."""
    for day in days:
        training_svc.log_as_planned(db, day, today=TODAY)


def performed(slug, *, reps, weight, sets=3):
    return PerformedExercise(
        exercise_slug=slug,
        position=0,
        sets=tuple(PerformedSet(set_no=n + 1, reps=reps, weight_kg=weight) for n in range(sets)),
    )


# --------------------------------------------------------------------------
# Evaluación
# --------------------------------------------------------------------------


def test_sin_historial_no_propone_nada_y_dice_por_que(db, weekly):
    evaluation = svc.evaluate_routine(db, weekly, today=TODAY)

    assert evaluation.ready == 0
    assert all(i.outcome is ProgressionOutcome.NOT_YET for i in evaluation.items)
    assert all("sesión" in i.reason for i in evaluation.items)


def test_la_regla_se_hereda_del_catalogo_cuando_la_rutina_no_la_fija(db, weekly):
    """Decisión de F3: sin regla en la rutina vale la que declara el catálogo.

    No es suponer nada — está escrita, solo que en el ejercicio y no en la
    rutina — y sin esto ninguna rutina creada en F1 podría progresar.
    """
    flexiones = item(svc.evaluate_routine(db, weekly, today=TODAY), "flexiones")

    assert flexiones.rule_slug == "reps_hasta_20"
    assert flexiones.rule_inherited is True


def test_la_regla_de_la_rutina_manda_sobre_la_del_catalogo(db):
    detail = planning_svc.create_routine(
        db,
        name="Calistenia",
        exercises=[plan("flexiones", count=3, reps=15, rule_slug="manual")],
    )
    flexiones = item(svc.evaluate_routine(db, detail.id, today=TODAY), "flexiones")

    assert flexiones.rule_slug == "manual"
    assert flexiones.rule_inherited is False
    assert flexiones.outcome is ProgressionOutcome.NOT_YET


def test_dos_sesiones_cumpliendo_el_objetivo_habilitan_la_progresion(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    evaluation = svc.evaluate_routine(db, weekly, today=TODAY)

    assert evaluation.ready == 3
    assert item(evaluation, "flexiones").proposed == "3x16"
    assert item(evaluation, "press_banca").proposed == "3x9 @ 40kg"
    assert item(evaluation, "plancha").proposed == "3x50s"


def test_el_resumen_para_hoy_solo_lista_rutinas_con_algo_que_ofrecer(db, weekly):
    assert svc.readiness(db, today=TODAY) == []

    train(db, MONDAY, WEDNESDAY)
    resumen = svc.readiness(db, today=TODAY)

    assert len(resumen) == 1
    assert resumen[0].routine_id == weekly
    assert resumen[0].ready == 3


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------


def test_aplicar_un_lote_crea_una_sola_version_y_un_evento_por_ejercicio(db, weekly):
    train(db, MONDAY, WEDNESDAY)

    result = svc.apply(
        db, weekly, exercise_slugs=["flexiones", "press_banca", "plancha"], today=TODAY
    )

    assert result.routine.version_no == 2
    assert len(result.events) == 3
    assert {e.exercise_slug for e in result.events} == {"flexiones", "press_banca", "plancha"}


def test_aplicar_no_muta_la_version_ya_entrenada(db, weekly):
    """Regla R3: la sesión del lunes debe seguir describiendo lo de aquel día."""
    train(db, MONDAY, WEDNESDAY)
    svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    anterior = planning_svc.get_routine(db, weekly, version_no=1)
    flexiones = next(e for e in anterior.exercises if e.exercise_slug == "flexiones")

    assert [s.target_reps for s in flexiones.work_sets] == [15, 15, 15]


def test_aplicar_solo_cambia_los_ejercicios_elegidos(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    result = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    por_slug = {e.exercise_slug: e for e in result.routine.exercises}
    assert [s.target_reps for s in por_slug["flexiones"].work_sets] == [16, 16, 16]
    assert [s.target_reps for s in por_slug["press_banca"].work_sets] == [8, 8, 8]


def test_aplicar_reevalua_y_rechaza_lo_que_no_puede_progresar(db, weekly):
    """El cliente elige qué ejercicios, nunca cuánto: la propuesta se recalcula."""
    train(db, MONDAY)  # una sola sesión: aún no hay base para subir

    with pytest.raises(Conflict, match="no puede progresar"):
        svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    assert planning_svc.get_routine(db, weekly).version_no == 1


def test_aplicar_un_ejercicio_ajeno_a_la_rutina_no_existe(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    with pytest.raises(NotFound):
        svc.apply(db, weekly, exercise_slugs=["remo_barra"], today=TODAY)


def test_aplicar_sin_seleccion_es_invalido(db, weekly):
    with pytest.raises(Invalid):
        svc.apply(db, weekly, exercise_slugs=[], today=TODAY)


def test_tras_aplicar_el_cooldown_bloquea_la_siguiente_subida(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    # `applied_at` es un instante de auditoría y lo pone el reloj, no la fecha
    # inyectada: se fija aquí para que el test no dependa del día en que corra.
    db.execute(
        "UPDATE progression_event SET applied_at = ? WHERE id = ?",
        ("2026-03-13T19:00:00+01:00", aplicado.events[0].id),
    )
    db.commit()

    flexiones = item(svc.evaluate_routine(db, weekly, today=TODAY), "flexiones")

    assert flexiones.last_progression == FRIDAY
    assert flexiones.outcome is ProgressionOutcome.NOT_YET
    assert "margen mínimo" in flexiones.reason  # la regla pide 5 días y han pasado 2


# --------------------------------------------------------------------------
# Variantes (M8)
# --------------------------------------------------------------------------


@pytest.fixture
def calistenia(db) -> int:
    detail = planning_svc.create_routine(
        db,
        name="Calistenia",
        exercises=[plan("flexiones", count=3, reps=15, rule_slug="variante_calistenia")],
    )
    planning_svc.set_week(db, {0: detail.id, 2: detail.id}, effective_from=date(2026, 3, 1))
    return detail.id


def test_la_estrategia_variante_sustituye_el_ejercicio_por_el_siguiente(db, calistenia):
    train(db, MONDAY, WEDNESDAY)
    result = svc.apply(db, calistenia, exercise_slugs=["flexiones"], today=TODAY)

    assert [e.exercise_slug for e in result.routine.exercises] == ["flexiones_declinadas"]
    # El evento se atribuye al ejercicio de partida, que es el que progresó.
    assert result.events[0].exercise_slug == "flexiones"
    assert result.events[0].after["exercise_slug"] == "flexiones_declinadas"


def test_la_variante_se_rechaza_si_ya_estaba_en_la_rutina(db):
    """Mejor negarse con motivo que dejar el mismo ejercicio dos veces."""
    detail = planning_svc.create_routine(
        db,
        name="Calistenia doble",
        exercises=[
            plan("flexiones", count=3, reps=15, rule_slug="variante_calistenia"),
            plan("flexiones_declinadas", count=3, reps=10),
        ],
    )
    planning_svc.set_week(db, {0: detail.id, 2: detail.id}, effective_from=date(2026, 3, 1))
    train(db, MONDAY, WEDNESDAY)

    with pytest.raises(Invalid, match="dos veces"):
        svc.apply(db, detail.id, exercise_slugs=["flexiones"], today=TODAY)


# --------------------------------------------------------------------------
# Descarga (M3)
# --------------------------------------------------------------------------


def test_tres_sesiones_a_peor_sugieren_descarga_y_puede_aplicarse(db, weekly):
    for day, reps in ((MONDAY, 8), (WEDNESDAY, 7), (FRIDAY, 6)):
        training_svc.log_session(
            db,
            day=day,
            exercises=[performed("press_banca", reps=reps, weight=40.0)],
            today=TODAY,
        )

    press = item(svc.evaluate_routine(db, weekly, today=TODAY), "press_banca")
    assert press.outcome is ProgressionOutcome.DELOAD_SUGGESTED
    assert press.proposed == "3x8 @ 36kg"

    result = svc.apply(db, weekly, exercise_slugs=["press_banca"], today=TODAY)
    nuevo = next(e for e in result.routine.exercises if e.exercise_slug == "press_banca")
    assert [s.target_weight_kg for s in nuevo.work_sets] == [36.0, 36.0, 36.0]


# --------------------------------------------------------------------------
# Deshacer
# --------------------------------------------------------------------------


def test_deshacer_crea_otra_version_que_restaura_el_plan(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    deshecho = svc.undo(db, aplicado.events[0].id)

    assert deshecho.routine.version_no == 3  # nunca se borra: se añade
    flexiones = next(e for e in deshecho.routine.exercises if e.exercise_slug == "flexiones")
    assert [s.target_reps for s in flexiones.work_sets] == [15, 15, 15]


def test_deshacer_marca_el_evento_original_y_deja_rastro(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)
    svc.undo(db, aplicado.events[0].id)

    eventos = svc.list_events(db, routine_id=weekly)
    original = next(e for e in eventos if e.id == aplicado.events[0].id)

    assert original.reverted is True
    assert len(eventos) == 2
    assert any(e.is_reversal for e in eventos)


def test_deshacer_libera_el_cooldown(db, weekly):
    """Si la subida ya no está, esperar una semana por ella no tiene sentido."""
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)
    svc.undo(db, aplicado.events[0].id)

    flexiones = item(svc.evaluate_routine(db, weekly, today=TODAY), "flexiones")
    assert flexiones.last_progression is None
    assert flexiones.outcome is ProgressionOutcome.READY


def test_no_se_deshace_dos_veces(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)
    svc.undo(db, aplicado.events[0].id)

    with pytest.raises(Conflict, match="ya se deshizo"):
        svc.undo(db, aplicado.events[0].id)


def test_deshacer_se_niega_si_el_plan_cambio_despues(db, weekly):
    """Decisión de F3: antes que pisar una edición manual, decir que no se puede."""
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    actual = planning_svc.get_routine(db, weekly)
    planning_svc.update_routine(
        db,
        weekly,
        exercises=[
            plan("flexiones", count=4, reps=16) if e.exercise_slug == "flexiones" else e
            for e in actual.exercises
        ],
    )

    with pytest.raises(Conflict, match="cambió después"):
        svc.undo(db, aplicado.events[0].id)


def test_deshacer_se_niega_si_el_ejercicio_ya_no_esta_en_la_rutina(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)

    actual = planning_svc.get_routine(db, weekly)
    planning_svc.update_routine(
        db,
        weekly,
        exercises=[e for e in actual.exercises if e.exercise_slug != "flexiones"],
    )

    with pytest.raises(Conflict, match="ya no está"):
        svc.undo(db, aplicado.events[0].id)


def test_una_reversion_no_se_deshace(db, weekly):
    train(db, MONDAY, WEDNESDAY)
    aplicado = svc.apply(db, weekly, exercise_slugs=["flexiones"], today=TODAY)
    reversion = svc.undo(db, aplicado.events[0].id)

    with pytest.raises(Conflict, match="reversión"):
        svc.undo(db, reversion.events[0].id)
