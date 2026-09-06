"""Estado de cumplimiento de un día del calendario.

Este módulo existe por una distinción que el resto de apps de entrenamiento
suele ignorar: **"no registrado" no es "no realizado"**. Quien abre la app dos
veces por semana no ha fallado cinco entrenamientos, simplemente aún no los ha
anotado. Pintar eso de rojo sería mentir sobre el propio historial.

La solución es una ventana de gracia y un estado ``PENDING`` que se excluye del
cálculo de adherencia en lugar de contarse como fallo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta

from ..enums import DayState, SessionStatus
from ..models import ScheduleException, WorkoutSession

DEFAULT_GRACE_DAYS = 3


@dataclass(frozen=True, slots=True)
class DayVerdict:
    """Estado de un día, con su porqué.

    ``reason`` es texto para el usuario: el calendario debe poder explicar por
    qué un día está en rojo sin obligar a deducirlo.
    """

    date: Date
    state: DayState
    reason: str

    @property
    def counts_for_adherence(self) -> bool:
        """Si el día entra en el cálculo de adherencia.

        ``PENDING`` no cuenta: aún no se sabe qué pasó, y asumir lo peor
        distorsionaría la métrica. ``REST`` y ``EXCUSED`` tampoco: no había
        nada que cumplir.
        """
        return self.state in (
            DayState.DONE,
            DayState.PARTIAL,
            DayState.MISSED,
        )

    @property
    def is_success(self) -> bool:
        return self.state in (DayState.DONE, DayState.PARTIAL)


def resolve_day_state(
    day: Date,
    *,
    today: Date,
    was_scheduled: bool,
    session: WorkoutSession | None = None,
    exception: ScheduleException | None = None,
    grace_days: int = DEFAULT_GRACE_DAYS,
) -> DayVerdict:
    """Determina el estado de ``day``.

    ``today`` se inyecta: el dominio nunca consulta el reloj, de modo que los
    tests son deterministas y el pasado siempre se evalúa igual.

    Precedencia (de mayor a menor):

    1. Una sesión registrada manda sobre cualquier suposición — es el hecho.
    2. Una excepción declarada excusa el día.
    3. Sin sesión ni excepción, decide la ventana de gracia.
    """
    if grace_days < 0:
        raise ValueError("grace_days no puede ser negativo")
    if day > today:
        raise ValueError("no se evalúa el estado de un día futuro")

    # 1. Hay registro: es el dato duro, prevalece sobre todo lo demás.
    if session is not None:
        if session.status is SessionStatus.COMPLETED:
            if was_scheduled:
                return DayVerdict(day, DayState.DONE, "Rutina completada")
            return DayVerdict(day, DayState.EXTRA, "Entrenamiento extra, sin rutina programada")
        if session.status is SessionStatus.PARTIAL:
            return DayVerdict(day, DayState.PARTIAL, "Rutina completada parcialmente")
        # SKIPPED: el usuario declaró explícitamente que no entrenó.
        return DayVerdict(day, DayState.MISSED, "Marcado como no realizado")

    # 2. Día excusado: descanso, lesión, viaje o entrenamiento movido.
    if exception is not None:
        return DayVerdict(day, DayState.EXCUSED, f"Día excusado: {exception.reason}")

    # 3. Sin rutina programada y sin sesión: no había nada que cumplir.
    if not was_scheduled:
        return DayVerdict(day, DayState.REST, "Sin rutina programada")

    # 4. Programado y sin registrar: la ventana de gracia decide.
    deadline = day + timedelta(days=grace_days)
    if today <= deadline:
        remaining = (deadline - today).days
        return DayVerdict(
            day,
            DayState.PENDING,
            f"Pendiente de registrar ({remaining} día(s) de margen)",
        )

    return DayVerdict(
        day,
        DayState.MISSED,
        f"Sin registrar tras {grace_days} día(s) de margen",
    )


def adherence(verdicts: list[DayVerdict]) -> float | None:
    """Porcentaje de cumplimiento sobre los días que sí computan.

    Devuelve ``None`` si ningún día computa todavía: un 0 % sería una
    afirmación falsa sobre datos inexistentes.
    """
    countable = [v for v in verdicts if v.counts_for_adherence]
    if not countable:
        return None
    return sum(1 for v in countable if v.is_success) / len(countable)
