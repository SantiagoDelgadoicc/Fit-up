"""Registro de entrenamientos, con foco en el caso retroactivo.

El criterio de aceptación de F1 es registrar el martes desde el domingo. Casi
todo lo que se prueba aquí gira alrededor de eso.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitup.application.errors import Conflict, Invalid, NotFound
from fitup.application.repositories import history
from fitup.application.services import planning as planning_svc
from fitup.application.services import training as svc
from fitup.domain.enums import DayState, SessionOrigin, SessionStatus
from fitup.domain.models import PerformedExercise, PerformedSet
from helpers_app import plan

SUNDAY = date(2026, 3, 15)
MONDAY = date(2026, 3, 9)  # programado
WEDNESDAY = date(2026, 3, 11)  # programado
TUESDAY = date(2026, 3, 10)  # sin rutina
FRIDAY = date(2026, 3, 13)  # programado


def performed(slug="flexiones", reps=15, sets=3):
    return PerformedExercise(
        exercise_slug=slug,
        position=0,
        sets=tuple(PerformedSet(set_no=i + 1, reps=reps) for i in range(sets)),
    )


# --------------------------------------------------------------------------
# Registro como planificado: el camino de un toque
# --------------------------------------------------------------------------


def test_hice_esta_rutina_copia_el_plan_completo(db, weekly):
    session = svc.log_as_planned(db, FRIDAY, today=SUNDAY)

    assert session.status is SessionStatus.COMPLETED
    assert session.origin is SessionOrigin.PLANIFICADA
    assert len(session.exercises) == 3
    flexiones = next(e for e in session.exercises if e.exercise_slug == "flexiones")
    assert [s.reps for s in flexiones.sets] == [15, 15, 15]
    assert all(s.completed for s in flexiones.sets)


def test_el_registro_del_domingo_para_el_viernes_queda_marcado_retroactivo(db, weekly):
    """Distinguirlo permite auditar la calidad del dato (regla R9)."""
    session = svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    assert session.is_retroactive


def test_se_conservan_las_series_por_tiempo_y_con_peso(db, weekly):
    session = svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    plancha = next(e for e in session.exercises if e.exercise_slug == "plancha")
    press = next(e for e in session.exercises if e.exercise_slug == "press_banca")
    assert all(s.time_s == 45 for s in plancha.sets)
    assert all(s.weight_kg == 40.0 for s in press.sets)


def test_no_se_puede_registrar_como_planificado_un_dia_sin_rutina(db, weekly):
    with pytest.raises(Invalid, match="ninguna rutina programada"):
        svc.log_as_planned(db, TUESDAY, today=SUNDAY)


def test_no_se_puede_registrar_dos_veces_la_misma_rutina(db, weekly):
    """Dos entrenamientos el mismo día sí; el mismo dos veces, no.

    Lo primero es normal —mañana y tarde—; lo segundo es un doble clic.
    """
    svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    with pytest.raises(Conflict, match="ya tiene registradas"):
        svc.log_as_planned(db, FRIDAY, today=SUNDAY)


def test_el_futuro_esta_prohibido(db, weekly):
    with pytest.raises(Invalid, match="futuro"):
        svc.log_as_planned(db, SUNDAY + timedelta(days=1), today=SUNDAY)


def test_una_fecha_absurdamente_lejana_se_rechaza(db, weekly):
    """Casi siempre es un error de tecleo, no un entrenamiento de hace dos años."""
    with pytest.raises(Invalid, match="error de tecleo"):
        svc.log_as_planned(db, SUNDAY - timedelta(days=800), today=SUNDAY)


def test_se_usa_el_plan_vigente_ese_dia_no_el_de_hoy(db, weekly):
    """Editar la rutina el sábado no debe cambiar lo que se hizo el lunes."""
    planning_svc.update_routine(db, weekly, exercises=[plan("flexiones", reps=99)])
    db.execute(
        "UPDATE routine_version SET created_at = '2026-03-14T10:00:00+01:00' "
        "WHERE routine_id = ? AND version_no = 2",
        (weekly,),
    )
    db.commit()

    session = svc.log_as_planned(db, MONDAY, today=SUNDAY)
    assert session.routine_version_no == 1
    assert len(session.exercises) == 3


def test_una_sesion_parcial_se_registra_como_tal(db, weekly):
    session = svc.log_as_planned(db, FRIDAY, today=SUNDAY, status=SessionStatus.PARTIAL)
    assert session.status is SessionStatus.PARTIAL


def test_la_clave_de_idempotencia_devuelve_la_sesion_existente(db, weekly):
    """Un cliente que reintenta no debe crear dos entrenamientos."""
    first = svc.log_as_planned(db, FRIDAY, today=SUNDAY, idempotency_key="abc")
    second = svc.log_as_planned(db, FRIDAY, today=SUNDAY, idempotency_key="abc")
    assert first.id == second.id


# --------------------------------------------------------------------------
# Registro libre
# --------------------------------------------------------------------------


def test_registro_libre_en_un_dia_sin_rutina_es_adhoc(db, weekly):
    session = svc.log_session(db, day=TUESDAY, exercises=[performed()], today=SUNDAY)
    assert session.origin is SessionOrigin.ADHOC
    assert session.routine_version_id is None


def test_registro_libre_en_un_dia_programado_se_asocia_a_la_rutina(db, weekly):
    session = svc.log_session(db, day=FRIDAY, exercises=[performed(reps=12)], today=SUNDAY)
    assert session.origin is SessionOrigin.PLANIFICADA
    assert session.routine_version_no == 1
    assert [s.reps for s in session.exercises[0].sets] == [12, 12, 12]


def test_un_registro_sin_ejercicios_se_rechaza(db, weekly):
    with pytest.raises(Invalid, match="al menos un ejercicio"):
        svc.log_session(db, day=TUESDAY, exercises=[], today=SUNDAY)


def test_un_ejercicio_inexistente_se_rechaza(db, weekly):
    with pytest.raises(NotFound):
        svc.log_session(db, day=TUESDAY, exercises=[performed("fantasma")], today=SUNDAY)


def test_se_guardan_rir_y_esfuerzo_percibido(db, weekly):
    """El RIR es lo que hará segura la progresión en F3."""
    ejercicio = PerformedExercise(
        exercise_slug="press_banca",
        position=0,
        sets=(PerformedSet(set_no=1, reps=8, weight_kg=40.0, rir=2),),
    )
    session = svc.log_session(
        db, day=TUESDAY, exercises=[ejercicio], today=SUNDAY, perceived_effort=7
    )
    assert session.exercises[0].sets[0].rir == 2
    assert session.perceived_effort == 7


def test_declarar_que_no_se_entreno_es_informacion_no_ausencia(db, weekly):
    session = svc.skip_day(db, MONDAY, today=SUNDAY)
    assert session.status is SessionStatus.SKIPPED

    day = svc.get_day(db, MONDAY, today=SUNDAY)
    assert day.state is DayState.MISSED  # sin esperar la ventana de gracia


def test_borrar_una_sesion(db, weekly):
    session = svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    svc.delete_session(db, session.id)
    assert svc.get_day(db, FRIDAY, today=SUNDAY).sessions == []


def test_borrar_una_sesion_inexistente_falla(db):
    with pytest.raises(NotFound):
        svc.delete_session(db, 999)


# --------------------------------------------------------------------------
# Vista de un día
# --------------------------------------------------------------------------


def test_el_dia_de_hoy_trae_el_plan_aunque_no_haya_registro(db, weekly):
    day = svc.get_day(db, WEDNESDAY, today=WEDNESDAY)
    assert day.state is DayState.PENDING
    assert len(day.scheduled) == 1
    assert len(day.scheduled[0].detail.exercises) == 3
    assert day.can_log


def test_un_dia_sin_rutina_es_descanso(db, weekly):
    day = svc.get_day(db, TUESDAY, today=SUNDAY)
    assert day.state is DayState.REST
    assert day.scheduled == []


def test_un_dia_registrado_ya_no_ofrece_registrar(db, weekly):
    svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    day = svc.get_day(db, FRIDAY, today=SUNDAY)
    assert day.state is DayState.DONE
    assert not day.can_log


def test_no_se_consulta_el_futuro(db, weekly):
    with pytest.raises(Invalid, match="futuro"):
        svc.get_day(db, SUNDAY + timedelta(days=1), today=SUNDAY)


def test_una_excepcion_excusa_el_dia(db, weekly):
    from fitup.domain.enums import ExceptionReason
    from fitup.domain.models import ScheduleException

    planning_svc.set_exception(db, ScheduleException(MONDAY, ExceptionReason.LESION))
    day = svc.get_day(db, MONDAY, today=SUNDAY)
    assert day.state is DayState.EXCUSED
    assert day.exception_reason == "lesion"


# --------------------------------------------------------------------------
# Pendientes de registrar
# --------------------------------------------------------------------------


def test_los_pendientes_son_lo_programado_y_no_registrado_dentro_de_la_gracia(db, weekly):
    """Es la lista que la pantalla Hoy resuelve de un toque."""
    pendientes = svc.pending_days(db, today=FRIDAY)
    assert [p.date for p in pendientes] == [FRIDAY, WEDNESDAY]
    assert pendientes[0].routine_name == "Empuje"


def test_registrar_saca_el_dia_de_pendientes(db, weekly):
    svc.log_as_planned(db, FRIDAY, today=FRIDAY)
    assert [p.date for p in svc.pending_days(db, today=FRIDAY)] == [WEDNESDAY]


def test_una_excepcion_saca_el_dia_de_pendientes(db, weekly):
    from fitup.domain.enums import ExceptionReason
    from fitup.domain.models import ScheduleException

    planning_svc.set_exception(db, ScheduleException(WEDNESDAY, ExceptionReason.VIAJE))
    assert [p.date for p in svc.pending_days(db, today=FRIDAY)] == [FRIDAY]


def test_fuera_de_la_ventana_de_gracia_deja_de_ser_pendiente(db, weekly):
    """El lunes, visto el domingo, ya no es "pendiente": es no realizado."""
    pendientes = svc.pending_days(db, today=SUNDAY)
    assert MONDAY not in [p.date for p in pendientes]
    assert svc.get_day(db, MONDAY, today=SUNDAY).state is DayState.MISSED


def test_la_ventana_de_gracia_es_configurable(db, weekly):
    from fitup.application.repositories import history

    history.set_setting(db, "dias_gracia", 10)
    db.commit()
    assert MONDAY in [p.date for p in svc.pending_days(db, today=SUNDAY)]


# --------------------------------------------------------------------------
# Calendario
# --------------------------------------------------------------------------


def test_el_calendario_resuelve_cada_dia_del_rango(db, weekly):
    svc.log_as_planned(db, MONDAY, today=SUNDAY)
    verdicts = svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)

    por_dia = {v.date: v.state for v in verdicts}
    assert por_dia[MONDAY] is DayState.DONE
    assert por_dia[TUESDAY] is DayState.REST
    assert por_dia[WEDNESDAY] is DayState.MISSED  # fuera de la gracia
    assert por_dia[FRIDAY] is DayState.PENDING  # dentro de la gracia


def test_el_calendario_nunca_pasa_de_hoy(db, weekly):
    verdicts = svc.calendar(db, MONDAY, SUNDAY + timedelta(days=30), today=SUNDAY)
    assert max(v.date for v in verdicts) == SUNDAY


def test_un_rango_invertido_devuelve_vacio(db, weekly):
    assert svc.calendar(db, SUNDAY, MONDAY, today=SUNDAY) == []


def test_la_adherencia_ignora_los_dias_pendientes(db, weekly):
    from fitup.domain.compliance.day_state import adherence

    svc.log_as_planned(db, MONDAY, today=SUNDAY)
    days = svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)
    # Lunes cumplido, miércoles no realizado; viernes pendiente no computa.
    assert adherence([d.verdict for d in days]) == 0.5


# --------------------------------------------------------------------------
# Contenido del calendario (F2)
# --------------------------------------------------------------------------


def test_el_calendario_dice_que_rutina_tocaba_cada_dia(db, weekly):
    """La vista mensual necesita el nombre, no solo el color."""
    dias = {d.date: d for d in svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)}
    assert dias[MONDAY].routine_name == "Empuje"
    assert dias[MONDAY].routine_id == weekly
    assert dias[TUESDAY].routine_name is None


def test_el_calendario_enlaza_la_sesion_registrada(db, weekly):
    sesion = svc.log_as_planned(db, FRIDAY, today=SUNDAY)
    dias = {d.date: d for d in svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)}
    assert dias[FRIDAY].session_ids == [sesion.id]
    assert dias[MONDAY].session_ids == []


def test_un_entrenamiento_extra_muestra_lo_que_se_hizo_no_lo_programado(db, weekly):
    """El calendario cuenta lo que pasó, no lo que debería haber pasado."""
    svc.log_session(db, day=TUESDAY, exercises=[performed()], today=SUNDAY, routine_id=weekly)
    dias = {d.date: d for d in svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)}
    assert dias[TUESDAY].routine_name == "Empuje"
    assert dias[TUESDAY].state is DayState.EXTRA


def test_el_veredicto_del_dominio_viaja_intacto_en_cada_dia(db, weekly):
    """Envolverlo, no copiarlo: la regla de adherencia sigue en un solo sitio."""
    dias = svc.calendar(db, MONDAY, SUNDAY, today=SUNDAY)
    for dia in dias:
        assert dia.state is dia.verdict.state
        assert dia.reason == dia.verdict.reason


# --------------------------------------------------------------------------
# Días con dos rutinas: calistenia por la mañana, pesas por la tarde.
# --------------------------------------------------------------------------


def _dos_rutinas(db) -> tuple[int, int]:
    """Lunes con rutina de mañana y de tarde."""
    from fitup.application.services import planning as planning_svc

    manana = planning_svc.create_routine(
        db, name="Calistenia mañana", exercises=[plan("dominadas")]
    ).id
    tarde = planning_svc.create_routine(db, name="Pecho tarde", exercises=[plan("flexiones")]).id
    planning_svc.set_week(db, {MONDAY.weekday(): [manana, tarde]}, effective_from=date(2026, 3, 1))
    return manana, tarde


def test_un_dia_puede_tener_dos_rutinas_programadas(db):
    manana, tarde = _dos_rutinas(db)
    dia = svc.get_day(db, MONDAY, today=SUNDAY)
    assert [s.routine_id for s in dia.scheduled] == [manana, tarde]
    assert dia.scheduled[0].name == "Calistenia mañana"


def test_con_dos_rutinas_sin_registrar_hay_que_decir_cual(db):
    """Dar por hecho que es la primera anotaría la mañana al hacer la tarde."""
    _dos_rutinas(db)
    with pytest.raises(Invalid, match="más de una rutina sin registrar"):
        svc.log_as_planned(db, MONDAY, today=SUNDAY)


def test_registrar_la_de_la_tarde_deja_la_manana_pendiente(db):
    _, tarde = _dos_rutinas(db)
    svc.log_as_planned(db, MONDAY, routine_id=tarde, today=SUNDAY)

    dia = svc.get_day(db, MONDAY, today=SUNDAY)
    assert dia.scheduled[0].session is None  # la mañana sigue sin hacer
    assert dia.scheduled[1].session is not None
    assert dia.can_log


def test_registrada_una_la_otra_ya_no_necesita_que_se_indique(db):
    """Si solo queda una pendiente, no hay ambigüedad que resolver."""
    manana, tarde = _dos_rutinas(db)
    svc.log_as_planned(db, MONDAY, routine_id=tarde, today=SUNDAY)
    sesion = svc.log_as_planned(db, MONDAY, today=SUNDAY)

    assert sesion.routine_id == manana
    assert len(svc.get_day(db, MONDAY, today=SUNDAY).sessions) == 2


def test_registrar_las_dos_completa_el_dia(db):
    manana, tarde = _dos_rutinas(db)
    svc.log_as_planned(db, MONDAY, routine_id=manana, today=SUNDAY)
    svc.log_as_planned(db, MONDAY, routine_id=tarde, today=SUNDAY)

    dia = svc.get_day(db, MONDAY, today=SUNDAY)
    assert dia.state is DayState.DONE
    assert not dia.can_log


def test_una_rutina_de_otro_dia_no_se_puede_registrar(db):
    _dos_rutinas(db)
    otra = planning_svc.create_routine(db, name="Suelta", exercises=[plan("flexiones")]).id
    with pytest.raises(Invalid, match="no estaba programada"):
        svc.log_as_planned(db, MONDAY, routine_id=otra, today=SUNDAY)


def test_los_pendientes_distinguen_que_rutina_falta(db):
    manana, tarde = _dos_rutinas(db)
    svc.log_as_planned(db, MONDAY, routine_id=manana, today=MONDAY)

    pendientes = [p for p in svc.pending_days(db, today=MONDAY) if p.date == MONDAY]
    assert [p.routine_id for p in pendientes] == [tarde]


def test_el_registro_libre_admite_dos_entrenamientos_el_mismo_dia(db):
    """Entrenar dos veces es normal; bloquearlo obligaba a juntarlo todo."""
    svc.log_session(db, day=MONDAY, exercises=[performed()], today=SUNDAY)
    svc.log_session(db, day=MONDAY, exercises=[performed()], today=SUNDAY)

    assert len(history.sessions_on(db, MONDAY)) == 2
