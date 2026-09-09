"""Estados del día. La distinción PENDING/MISSED es la razón de ser del módulo."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitup.domain.compliance.day_state import (
    DayVerdict,
    adherence,
    resolve_day_state,
)
from fitup.domain.enums import (
    DayState,
    ExceptionReason,
    SessionOrigin,
    SessionStatus,
)
from fitup.domain.models import ScheduleException, WorkoutSession

TODAY = date(2026, 3, 15)


def session(status: SessionStatus, day: date = TODAY) -> WorkoutSession:
    return WorkoutSession(date=day, status=status, origin=SessionOrigin.PLANIFICADA)


@pytest.mark.parametrize(
    ("scheduled", "status", "expected"),
    [
        (True, SessionStatus.COMPLETED, DayState.DONE),
        (True, SessionStatus.PARTIAL, DayState.PARTIAL),
        (True, SessionStatus.SKIPPED, DayState.MISSED),
        (False, SessionStatus.COMPLETED, DayState.EXTRA),
    ],
)
def test_una_sesion_registrada_manda_sobre_cualquier_suposicion(scheduled, status, expected):
    verdict = resolve_day_state(
        TODAY, today=TODAY, scheduled_count=1 if scheduled else 0, sessions=[session(status)]
    )
    assert verdict.state is expected


def test_dia_sin_rutina_ni_sesion_es_descanso():
    verdict = resolve_day_state(TODAY, today=TODAY, scheduled_count=0)
    assert verdict.state is DayState.REST


def test_excepcion_declarada_excusa_el_dia():
    day = TODAY - timedelta(days=10)
    verdict = resolve_day_state(
        day,
        today=TODAY,
        scheduled_count=1,
        exception=ScheduleException(day, ExceptionReason.LESION),
    )
    assert verdict.state is DayState.EXCUSED
    assert "lesion" in verdict.reason


@pytest.mark.parametrize("days_ago", [0, 1, 2, 3])
def test_dentro_de_la_ventana_de_gracia_queda_pendiente_no_fallado(days_ago):
    """Abrir la app el domingo no debe pintar de rojo toda la semana."""
    day = TODAY - timedelta(days=days_ago)
    verdict = resolve_day_state(day, today=TODAY, scheduled_count=1, grace_days=3)
    assert verdict.state is DayState.PENDING


def test_pasada_la_ventana_de_gracia_se_considera_no_realizado():
    day = TODAY - timedelta(days=4)
    verdict = resolve_day_state(day, today=TODAY, scheduled_count=1, grace_days=3)
    assert verdict.state is DayState.MISSED


def test_gracia_cero_marca_no_realizado_al_dia_siguiente():
    verdict = resolve_day_state(
        TODAY - timedelta(days=1), today=TODAY, scheduled_count=1, grace_days=0
    )
    assert verdict.state is DayState.MISSED
    # El propio día todavía no ha terminado.
    assert (
        resolve_day_state(TODAY, today=TODAY, scheduled_count=1, grace_days=0).state
        is DayState.PENDING
    )


def test_no_se_evalua_el_futuro():
    with pytest.raises(ValueError):
        resolve_day_state(TODAY + timedelta(days=1), today=TODAY, scheduled_count=1)


def test_gracia_negativa_es_error():
    with pytest.raises(ValueError):
        resolve_day_state(TODAY, today=TODAY, scheduled_count=1, grace_days=-1)


# --------------------------------------------------------------------------
# Adherencia
# --------------------------------------------------------------------------


def verdict(state: DayState) -> DayVerdict:
    return DayVerdict(TODAY, state, "")


def test_pendiente_no_cuenta_como_fallo_en_la_adherencia():
    """Asumir lo peor sobre lo aún no registrado distorsionaría la métrica."""
    solo_pendientes = [verdict(DayState.PENDING)] * 5
    assert adherence(solo_pendientes) is None

    mezcla = [verdict(DayState.DONE), verdict(DayState.PENDING)]
    assert adherence(mezcla) == 1.0


def test_descanso_y_excusado_no_entran_en_el_computo():
    base = [verdict(DayState.DONE), verdict(DayState.MISSED)]
    assert adherence(base) == 0.5
    ampliado = [*base, verdict(DayState.REST), verdict(DayState.EXCUSED)]
    assert adherence(ampliado) == 0.5


def test_parcial_cuenta_como_cumplimiento():
    assert adherence([verdict(DayState.PARTIAL), verdict(DayState.MISSED)]) == 0.5


def test_sin_dias_computables_devuelve_none_no_cero():
    """Un 0 % sobre datos inexistentes sería una afirmación falsa."""
    assert adherence([]) is None
    assert adherence([verdict(DayState.REST)]) is None


# --------------------------------------------------------------------------
# Días con más de una rutina: calistenia por la mañana, pesas por la tarde.
# --------------------------------------------------------------------------


def test_dos_rutinas_completadas_cumplen_el_dia():
    verdict = resolve_day_state(
        TODAY,
        today=TODAY,
        scheduled_count=2,
        sessions=[session(SessionStatus.COMPLETED), session(SessionStatus.COMPLETED)],
    )
    assert verdict.state is DayState.DONE
    assert "2" in verdict.reason


def test_falta_una_rutina_pero_queda_margen_es_pendiente_no_parcial():
    """Aún puede entrenarse por la tarde: llamarlo parcial adelanta el veredicto.

    Es el mismo principio que sostiene todo el módulo —no registrado no es no
    realizado— aplicado dentro del propio día.
    """
    verdict = resolve_day_state(
        TODAY, today=TODAY, scheduled_count=2, sessions=[session(SessionStatus.COMPLETED)]
    )
    assert verdict.state is DayState.PENDING
    assert "1 de 2" in verdict.reason


def test_falta_una_rutina_y_se_acabo_el_margen_es_parcial():
    """Pasado el plazo ya se sabe que la otra no se hizo, y eso sí es parcial."""
    day = TODAY - timedelta(days=10)
    verdict = resolve_day_state(
        day,
        today=TODAY,
        scheduled_count=2,
        sessions=[session(SessionStatus.COMPLETED, day)],
    )
    assert verdict.state is DayState.PARTIAL
    assert "1 de 2" in verdict.reason


def test_una_rutina_a_medias_es_parcial_aunque_esten_las_dos():
    verdict = resolve_day_state(
        TODAY,
        today=TODAY,
        scheduled_count=2,
        sessions=[session(SessionStatus.COMPLETED), session(SessionStatus.PARTIAL)],
    )
    assert verdict.state is DayState.PARTIAL


def test_declarar_no_realizadas_todas_las_sesiones_es_fallo():
    verdict = resolve_day_state(
        TODAY,
        today=TODAY,
        scheduled_count=2,
        sessions=[session(SessionStatus.SKIPPED), session(SessionStatus.SKIPPED)],
    )
    assert verdict.state is DayState.MISSED


def test_una_declarada_y_otra_hecha_no_borra_lo_hecho():
    """Saltarse la mañana no invalida la tarde: lo entrenado cuenta."""
    day = TODAY - timedelta(days=10)
    verdict = resolve_day_state(
        day,
        today=TODAY,
        scheduled_count=2,
        sessions=[session(SessionStatus.SKIPPED, day), session(SessionStatus.COMPLETED, day)],
    )
    assert verdict.state is DayState.PARTIAL


def test_entrenar_de_mas_sin_nada_programado_sigue_siendo_extra():
    verdict = resolve_day_state(
        TODAY,
        today=TODAY,
        scheduled_count=0,
        sessions=[session(SessionStatus.COMPLETED), session(SessionStatus.COMPLETED)],
    )
    assert verdict.state is DayState.EXTRA


def test_scheduled_count_negativo_es_error():
    with pytest.raises(ValueError, match="scheduled_count"):
        resolve_day_state(TODAY, today=TODAY, scheduled_count=-1)
