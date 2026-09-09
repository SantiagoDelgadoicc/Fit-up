"""Estado de cumplimiento de un día del calendario.

Este módulo existe por una distinción que el resto de apps de entrenamiento
suele ignorar: **"no registrado" no es "no realizado"**. Quien abre la app dos
veces por semana no ha fallado cinco entrenamientos, simplemente aún no los ha
anotado. Pintar eso de rojo sería mentir sobre el propio historial.

La solución es una ventana de gracia y un estado ``PENDING`` que se excluye del
cálculo de adherencia en lugar de contarse como fallo.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    scheduled_count: int = 0,
    sessions: Sequence[WorkoutSession] = (),
    exception: ScheduleException | None = None,
    grace_days: int = DEFAULT_GRACE_DAYS,
) -> DayVerdict:
    """Determina el estado de ``day``.

    ``today`` se inyecta: el dominio nunca consulta el reloj, de modo que los
    tests son deterministas y el pasado siempre se evalúa igual.

    Un día puede tener **varias rutinas programadas y varias sesiones**: quien
    entrena calistenia por la mañana y pesas por la tarde hace dos, y fundirlas
    en una sola perdería justo el dato de cuál se saltó.

    Precedencia (de mayor a menor):

    1. Lo registrado manda sobre cualquier suposición — es el hecho.
    2. Una excepción declarada excusa el día.
    3. Sin sesiones ni excepción, decide la ventana de gracia.
    """
    if grace_days < 0:
        raise ValueError("grace_days no puede ser negativo")
    if scheduled_count < 0:
        raise ValueError("scheduled_count no puede ser negativo")
    if day > today:
        raise ValueError("no se evalúa el estado de un día futuro")

    deadline = day + timedelta(days=grace_days)
    en_plazo = today <= deadline

    # 1. Hay registro: es el dato duro, prevalece sobre todo lo demás.
    if sessions:
        return _con_registro(
            day,
            sessions=sessions,
            scheduled_count=scheduled_count,
            en_plazo=en_plazo,
            grace_days=grace_days,
        )

    # 2. Día excusado: descanso, lesión, viaje o entrenamiento movido.
    if exception is not None:
        return DayVerdict(day, DayState.EXCUSED, f"Día excusado: {exception.reason}")

    # 3. Sin rutina programada y sin sesión: no había nada que cumplir.
    if scheduled_count == 0:
        return DayVerdict(day, DayState.REST, "Sin rutina programada")

    # 4. Programado y sin registrar: la ventana de gracia decide.
    if en_plazo:
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


def _con_registro(
    day: Date,
    *,
    sessions: Sequence[WorkoutSession],
    scheduled_count: int,
    en_plazo: bool,
    grace_days: int,
) -> DayVerdict:
    """Estado de un día que ya tiene algo anotado."""
    hechas = [s for s in sessions if s.status is not SessionStatus.SKIPPED]

    # Todo lo anotado es una declaración de que no se entrenó.
    if not hechas:
        return DayVerdict(day, DayState.MISSED, "Marcado como no realizado")

    if scheduled_count == 0:
        return DayVerdict(day, DayState.EXTRA, "Entrenamiento extra, sin rutina programada")

    completas = sum(1 for s in hechas if s.status is SessionStatus.COMPLETED)
    total = len(hechas)

    if completas == total and total >= scheduled_count:
        if scheduled_count > 1:
            return DayVerdict(day, DayState.DONE, f"Las {scheduled_count} rutinas completadas")
        return DayVerdict(day, DayState.DONE, "Rutina completada")

    # Falta alguna sesión del día y todavía hay margen: aún puede entrenarse,
    # así que llamarlo "parcial" sería adelantar un veredicto. El principio es
    # el mismo que con un día entero sin registrar: no anticipar el fallo.
    if completas == total and en_plazo:
        return DayVerdict(
            day,
            DayState.PENDING,
            f"{total} de {scheduled_count} rutinas registradas, con {grace_days} día(s) de margen",
        )

    if scheduled_count > 1:
        return DayVerdict(
            day, DayState.PARTIAL, f"{total} de {scheduled_count} rutinas, alguna a medias"
        )
    return DayVerdict(day, DayState.PARTIAL, "Rutina completada parcialmente")


def adherence(verdicts: list[DayVerdict]) -> float | None:
    """Porcentaje de cumplimiento sobre los días que sí computan.

    Devuelve ``None`` si ningún día computa todavía: un 0 % sería una
    afirmación falsa sobre datos inexistentes.
    """
    countable = [v for v in verdicts if v.counts_for_adherence]
    if not countable:
        return None
    return sum(1 for v in countable if v.is_success) / len(countable)
