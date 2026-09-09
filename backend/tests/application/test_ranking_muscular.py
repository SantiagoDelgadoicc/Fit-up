"""Ranking muscular sobre historial real.

La fórmula ya está probada en `tests/domain/test_ranking.py` con estímulos
sintéticos. Aquí se prueba el puente: que el historial se traduzca a esos
estímulos sin inventar nada, que la ficha explique de dónde sale el rango y
que los snapshots sean caché y no verdad.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitup.application.errors import NotFound
from fitup.application.repositories import history as history_repo
from fitup.application.services import ranking as svc
from fitup.application.services import training as training_svc
from fitup.domain.enums import SessionStatus, Tier
from fitup.domain.models import PerformedExercise, PerformedSet
from fitup.domain.ranking.v2 import FORMULA_VERSION

TODAY = date(2026, 3, 15)
MONDAY = date(2026, 3, 9)
WEDNESDAY = date(2026, 3, 11)
FRIDAY = date(2026, 3, 13)


@pytest.fixture
def con_peso(db):
    history_repo.set_bodyweight(db, date(2026, 1, 1), 75.0)
    db.commit()
    return db


def entrenar(db, *days):
    for day in days:
        training_svc.log_as_planned(db, day, today=TODAY)


def entry(view, slug):
    return next(e for e in view.entries if e.muscle_slug == slug)


# --------------------------------------------------------------------------
# Traducción del historial a estímulo
# --------------------------------------------------------------------------


def test_sin_peso_corporal_sigue_habiendo_rango_pero_no_volumen(db, weekly):
    """Cambio de v1 a v2: la escalera está en repeticiones, no en kilos.

    v1 no podía normalizar la fuerza sin peso corporal y dejaba el mapa entero
    en blanco. v2 mide marcas, así que el rango aparece igual; lo que sí se
    pierde es el volumen de los ejercicios corporales, y eso se dice.
    """
    entrenar(db, MONDAY, WEDNESDAY)
    view = svc.ranking(db, today=TODAY)

    assert view.measured > 0
    assert any(e.tier is not Tier.SIN_DATOS for e in view.entries)
    assert any("peso corporal" in n for n in view.notes)


def test_el_historial_se_reparte_entre_los_musculos_del_ejercicio(con_peso, weekly):
    """Press banca puntúa pectoral entero, tríceps y deltoide anterior a medias."""
    entrenar(con_peso, MONDAY, WEDNESDAY)
    view = svc.ranking(con_peso, today=TODAY)

    pectoral = entry(view, "pectoral")
    triceps = entry(view, "triceps")

    assert pectoral.development is not None
    assert triceps.development is not None
    assert pectoral.development > triceps.development


def test_un_musculo_que_nada_estimula_queda_sin_datos_no_en_iron(con_peso, weekly):
    """Regla explícita de ADR-0003: "no medido" y "débil" son cosas distintas."""
    entrenar(con_peso, MONDAY, WEDNESDAY)
    view = svc.ranking(con_peso, today=TODAY)

    gemelos = entry(view, "gemelos")
    assert gemelos.tier is Tier.SIN_DATOS
    assert gemelos.development is None
    assert gemelos.score.notes


def test_las_sesiones_no_realizadas_no_aportan_estimulo(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    antes = entry(svc.ranking(con_peso, today=TODAY), "pectoral").development

    training_svc.skip_day(con_peso, FRIDAY, today=TODAY)
    despues = entry(svc.ranking(con_peso, today=TODAY), "pectoral").development

    assert antes == despues


def test_las_series_sin_datos_se_cuentan_y_se_dicen(db, weekly):
    """Una serie que no se puede convertir no vale cero: se declara."""
    history_repo.set_bodyweight(db, date(2026, 1, 1), 75.0)
    db.commit()
    training_svc.log_session(
        db,
        day=MONDAY,
        today=TODAY,
        exercises=[
            PerformedExercise(
                exercise_slug="press_banca",
                position=0,
                # Carga externa sin peso registrado: indeterminable a propósito.
                sets=(PerformedSet(set_no=1, reps=8, weight_kg=None),),
            )
        ],
    )
    view = svc.ranking(db, today=TODAY)

    assert any("quedaron fuera del cálculo" in n for n in view.notes)


def test_el_calentamiento_no_cuenta_como_estimulo(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    con_calentamiento = entry(svc.ranking(con_peso, today=TODAY), "pectoral").development

    training_svc.log_session(
        con_peso,
        day=FRIDAY,
        today=TODAY,
        status=SessionStatus.COMPLETED,
        exercises=[
            PerformedExercise(
                exercise_slug="press_banca",
                position=0,
                sets=(PerformedSet(set_no=1, reps=20, weight_kg=200.0, is_warmup=True),),
            )
        ],
    )
    assert entry(svc.ranking(con_peso, today=TODAY), "pectoral").development == con_calentamiento


# --------------------------------------------------------------------------
# Calibración
# --------------------------------------------------------------------------


def test_la_calibracion_deja_a_un_principiante_en_la_parte_baja_de_la_escalera(con_peso, weekly):
    """El reparto de rangos es el objetivo de la calibración, no un detalle.

    Press banca 3x8 a 40 kg pesando 75 no puede dar Platinum: si la escalera
    se agota en el primer mes, el ranking deja de significar nada.
    """
    entrenar(con_peso, MONDAY, WEDNESDAY)
    pectoral = entry(svc.ranking(con_peso, today=TODAY), "pectoral")

    assert pectoral.tier in (Tier.IRON, Tier.BRONZE, Tier.SILVER)


def test_los_ajustes_pueden_recalibrar_sin_tocar_el_codigo(con_peso, weekly):
    """ADR-0003: umbrales editables en configuración.

    En v2 las escaleras de rango viven en el dominio, y lo que queda ajustable
    es el objetivo de volumen semanal, que gobierna el halo de actividad.
    """
    entrenar(con_peso, MONDAY, WEDNESDAY)
    base = entry(svc.ranking(con_peso, today=TODAY), "pectoral").score.activity

    history_repo.set_setting(con_peso, svc.TARGET_VOLUME_SETTING, 500.0)
    con_peso.commit()
    ajustado = entry(svc.ranking(con_peso, today=TODAY), "pectoral").score.activity

    assert ajustado > base


def test_un_objetivo_invalido_se_ignora_en_vez_de_romper_la_escala(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    base = entry(svc.ranking(con_peso, today=TODAY), "pectoral").score.activity

    history_repo.set_setting(con_peso, svc.TARGET_VOLUME_SETTING, -5)
    con_peso.commit()

    assert entry(svc.ranking(con_peso, today=TODAY), "pectoral").score.activity == base


# --------------------------------------------------------------------------
# Ficha del músculo
# --------------------------------------------------------------------------


def test_la_ficha_explica_de_donde_sale_el_rango(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    detail = svc.muscle_detail(con_peso, "pectoral", today=TODAY)

    assert detail.entry.score.factors["marca_confirmada"] > 0
    assert detail.entry.score.factors["puntuación_del_ejercicio"] > 0
    assert detail.points_to_next_tier is not None
    assert detail.next_tier is not None
    # Lo accionable: qué ejercicio manda y qué marca desbloquea el siguiente.
    assert detail.entry.score.leading_exercise
    assert detail.entry.score.next_mark
    assert [e.exercise_slug for e in detail.exercises]
    assert detail.exercises[0].role in ("primario", "secundario", "estabilizador")


def test_la_ficha_ordena_los_ejercicios_por_lo_que_aportan(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    detail = svc.muscle_detail(con_peso, "pectoral", today=TODAY)

    volumenes = [e.volume_kg for e in detail.exercises]
    assert volumenes == sorted(volumenes, reverse=True)


def test_la_ficha_cuenta_volumen_y_frecuencia_recientes(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    detail = svc.muscle_detail(con_peso, "pectoral", today=TODAY)

    assert detail.recent.sessions == 2
    assert detail.recent.volume_kg > 0
    assert detail.recent.sessions_per_week > 0


def test_la_ficha_de_un_musculo_inexistente_no_existe(db):
    with pytest.raises(NotFound):
        svc.muscle_detail(db, "musculo_inventado", today=TODAY)


# --------------------------------------------------------------------------
# Equilibrio (M7)
# --------------------------------------------------------------------------


def test_entrenar_solo_empuje_produce_el_aviso_de_equilibrio(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    view = svc.ranking(con_peso, today=TODAY)

    empuje = next(c for c in view.balance if c.key == "empuje_tiron")
    assert empuje.verdict.value in ("desequilibrio", "sin_datos")
    assert empuje.message


# --------------------------------------------------------------------------
# Snapshots
# --------------------------------------------------------------------------


def test_el_snapshot_guarda_los_dieciocho_musculos(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    assert svc.take_snapshot(con_peso, today=TODAY) == 18


def test_el_snapshot_es_semanal_y_no_se_repite_a_diario(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    assert svc.snapshot_if_stale(con_peso, today=TODAY) == 18
    assert svc.snapshot_if_stale(con_peso, today=TODAY + timedelta(days=3)) == 0
    assert svc.snapshot_if_stale(con_peso, today=TODAY + timedelta(days=7)) == 18


def test_recalcular_un_dia_sobrescribe_su_snapshot_porque_es_cache(con_peso, weekly):
    entrenar(con_peso, MONDAY)
    svc.take_snapshot(con_peso, today=TODAY)
    entrenar(con_peso, WEDNESDAY)
    svc.take_snapshot(con_peso, today=TODAY)

    puntos = svc.muscle_detail(con_peso, "pectoral", today=TODAY).history
    fechas = [p.date for p in puntos]

    assert fechas == [TODAY]  # un punto por día, no dos


def test_el_historico_de_la_ficha_sale_de_los_snapshots(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    svc.take_snapshot(con_peso, today=TODAY)
    svc.take_snapshot(con_peso, today=TODAY + timedelta(days=7))

    puntos = svc.muscle_detail(con_peso, "pectoral", today=TODAY + timedelta(days=7)).history

    assert [p.date for p in puntos] == [TODAY, TODAY + timedelta(days=7)]
    assert all(p.tier is not None for p in puntos)


def test_el_snapshot_registra_la_version_de_formula_con_la_que_se_calculo(con_peso, weekly):
    entrenar(con_peso, MONDAY, WEDNESDAY)
    svc.take_snapshot(con_peso, today=TODAY)

    versiones = {
        r["formula_version"]
        for r in con_peso.execute("SELECT formula_version FROM muscle_score_snapshot")
    }
    assert versiones == {FORMULA_VERSION}


def test_el_snapshot_automatico_no_guarda_puntos_vacios(db, weekly):
    """Arrancar el servidor sin nada registrado no debe dejar un valle de ceros.

    El automático se salta el punto; forzarlo a mano sigue siendo posible.
    """
    assert svc.snapshot_if_stale(db, today=TODAY) == 0
    assert svc.take_snapshot(db, today=TODAY) == 18
