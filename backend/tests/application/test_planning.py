"""Rutinas versionadas y planificación semanal."""

from __future__ import annotations

from datetime import date

import pytest

from fitup.application.errors import Invalid, NotFound
from fitup.application.repositories import planning as planning_repo
from fitup.application.services import planning as svc
from helpers_app import plan

# --------------------------------------------------------------------------
# Generación de series
# --------------------------------------------------------------------------


def test_una_prescripcion_compacta_produce_filas_explicitas():
    """La UI dice 3x15; el modelo guarda tres series."""
    sets = svc.build_sets(count=3, reps=15)
    assert [s.set_no for s in sets] == [1, 2, 3]
    assert all(s.target_reps == 15 for s in sets)


def test_las_series_de_calentamiento_van_primero_y_marcadas():
    sets = svc.build_sets(count=3, reps=8, weight_kg=60.0, warmup=1)
    assert sets[0].is_warmup and sets[0].target_weight_kg == 30.0
    assert not any(s.is_warmup for s in sets[1:])


def test_una_serie_necesita_repeticiones_o_tiempo():
    with pytest.raises(Invalid, match="repeticiones o tiempo"):
        svc.build_sets(count=3)


def test_el_maximo_de_repeticiones_no_puede_ser_menor_que_el_objetivo():
    with pytest.raises(Invalid):
        svc.build_sets(count=3, reps=12, reps_max=8)


# --------------------------------------------------------------------------
# Crear y validar
# --------------------------------------------------------------------------


def test_crear_una_rutina_arranca_en_la_version_uno(db):
    detail = svc.create_routine(db, name="Empuje", exercises=[plan("flexiones")])
    assert detail.version_no == 1
    assert detail.exercises[0].exercise_slug == "flexiones"
    assert len(detail.exercises[0].sets) == 3


def test_una_rutina_sin_ejercicios_se_rechaza(db):
    with pytest.raises(Invalid, match="al menos un ejercicio"):
        svc.create_routine(db, name="Vacía", exercises=[])


def test_una_rutina_sin_nombre_se_rechaza(db):
    with pytest.raises(Invalid, match="nombre"):
        svc.create_routine(db, name="   ", exercises=[plan("flexiones")])


def test_un_ejercicio_inexistente_se_rechaza(db):
    with pytest.raises(NotFound, match="no_existe"):
        svc.create_routine(db, name="X", exercises=[plan("no_existe")])


def test_un_ejercicio_repetido_se_rechaza(db):
    with pytest.raises(Invalid, match="repetido"):
        svc.create_routine(db, name="X", exercises=[plan("flexiones"), plan("flexiones")])


def test_una_regla_inexistente_se_rechaza(db):
    exercise = plan("flexiones")
    exercise = type(exercise)(
        exercise_slug=exercise.exercise_slug,
        position=0,
        sets=exercise.sets,
        rule_slug="regla_fantasma",
    )
    with pytest.raises(NotFound, match="regla"):
        svc.create_routine(db, name="X", exercises=[exercise])


def test_el_descanso_por_defecto_sale_del_catalogo(db):
    """Si la rutina no fija descanso, se hereda del ejercicio."""
    detail = svc.create_routine(db, name="X", exercises=[plan("press_banca")])
    assert detail.exercises[0].rest_seconds == 150


# --------------------------------------------------------------------------
# Versionado inmutable
# --------------------------------------------------------------------------


def test_editar_crea_una_version_nueva(db, push_routine):
    updated = svc.update_routine(
        db, push_routine, exercises=[plan("flexiones", reps=16)], note="progresion"
    )
    assert updated.version_no == 2
    assert updated.note == "progresion"


def test_la_version_anterior_queda_intacta(db, push_routine):
    """Es lo que permite que el historial de hace meses siga siendo cierto."""
    original = svc.get_routine(db, push_routine)
    svc.update_routine(db, push_routine, exercises=[plan("flexiones", reps=16)])

    v1 = svc.get_routine(db, push_routine, version_no=1)
    assert v1.exercises == original.exercises
    assert len(v1.exercises) == 3
    assert len(svc.get_routine(db, push_routine, version_no=2).exercises) == 1


def test_renombrar_no_pierde_las_versiones(db, push_routine):
    svc.update_routine(db, push_routine, name="Empuje A", exercises=[plan("flexiones")])
    assert svc.get_routine(db, push_routine).name == "Empuje A"
    assert svc.get_routine(db, push_routine, version_no=1).name == "Empuje A"


def test_editar_una_rutina_inexistente_falla(db):
    with pytest.raises(NotFound):
        svc.update_routine(db, 999, exercises=[plan("flexiones")])


def test_archivar_no_borra(db, push_routine):
    """El historial referencia sus versiones: borrarlas rompería el pasado."""
    svc.archive_routine(db, push_routine)
    assert svc.get_routine(db, push_routine).status == "archived"
    assert svc.list_routines(db) == []
    assert len(svc.list_routines(db, include_archived=True)) == 1


def test_el_listado_muestra_la_ultima_version(db, push_routine):
    svc.update_routine(db, push_routine, exercises=[plan("flexiones")])
    summary = svc.list_routines(db)[0]
    assert summary.version_no == 2
    assert summary.exercise_count == 1


def test_la_version_vigente_en_una_fecha_es_la_de_entonces(db, push_routine):
    """Registrar el martes desde el domingo debe usar el plan del martes."""
    svc.update_routine(db, push_routine, exercises=[plan("flexiones", reps=99)])
    db.execute(
        "UPDATE routine_version SET created_at = '2026-03-12T10:00:00+01:00' "
        "WHERE routine_id = ? AND version_no = 2",
        (push_routine,),
    )
    db.commit()

    antes = planning_repo.version_at(db, push_routine, date(2026, 3, 10))
    despues = planning_repo.version_at(db, push_routine, date(2026, 3, 13))
    assert planning_repo.get_version(db, antes).version_no == 1
    assert planning_repo.get_version(db, despues).version_no == 2


def test_una_fecha_anterior_a_la_rutina_usa_la_primera_version(db, push_routine):
    """Mejor registrar con la v1 que negarse a anotar algo que sí ocurrió."""
    vid = planning_repo.version_at(db, push_routine, date(2020, 1, 1))
    assert planning_repo.get_version(db, vid).version_no == 1


# --------------------------------------------------------------------------
# Semana
# --------------------------------------------------------------------------


def test_organizar_la_semana(db, push_routine):
    week = svc.set_week(db, {0: push_routine, 2: push_routine}, effective_from=date(2026, 3, 1))
    assert week.days[0] == push_routine
    assert week.days[1] is None
    assert week.names[2] == "Empuje"


def test_un_dia_de_la_semana_invalido_se_rechaza(db, push_routine):
    with pytest.raises(Invalid, match="Día de la semana"):
        svc.set_week(db, {9: push_routine}, effective_from=date(2026, 3, 1))


def test_una_rutina_inexistente_no_puede_programarse(db):
    with pytest.raises(NotFound):
        svc.set_week(db, {0: 999}, effective_from=date(2026, 3, 1))


def test_cambiar_la_semana_no_reescribe_el_pasado(db, push_routine):
    """Un día de hace un mes debe seguir sabiendo qué tocaba entonces."""
    svc.set_week(db, {0: push_routine}, effective_from=date(2026, 3, 1))
    svc.set_week(db, {0: None}, effective_from=date(2026, 3, 10))

    assert planning_repo.scheduled_routine(db, date(2026, 3, 2)) is not None  # lunes previo
    assert planning_repo.scheduled_routine(db, date(2026, 3, 16)) is None  # lunes posterior


def test_reprogramar_el_mismo_dia_sustituye_el_tramo(db, push_routine):
    otra = svc.create_routine(db, name="Tirón", exercises=[plan("dominadas")]).id
    svc.set_week(db, {0: push_routine}, effective_from=date(2026, 3, 1))
    svc.set_week(db, {0: otra}, effective_from=date(2026, 3, 1))

    scheduled = planning_repo.scheduled_routine(db, date(2026, 3, 2))
    assert scheduled is not None and scheduled[0] == otra


def test_archivar_una_rutina_la_saca_del_calendario(db, weekly):
    svc.archive_routine(db, weekly)
    assert planning_repo.scheduled_routine(db, date(2030, 1, 7)) is None
