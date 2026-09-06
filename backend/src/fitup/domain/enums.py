"""Vocabulario del dominio.

Los valores coinciden literalmente con los CHECK de la migración 0001: si
cambian aquí, cambian allí. Los nombres están en español porque el dominio es
el modelo de negocio del usuario, no un detalle técnico.
"""

from __future__ import annotations

# StrEnum de la stdlib (3.11+): serializable a JSON y comparable con str
# sin necesidad de una clase base propia.
from enum import StrEnum


class Modality(StrEnum):
    REPS = "reps"
    TIEMPO = "tiempo"
    DISTANCIA = "distancia"


class LoadType(StrEnum):
    EXTERNA = "externa"  # mancuernas, barra, máquina
    CORPORAL = "corporal"  # dominadas, flexiones
    ASISTIDA = "asistida"  # dominada asistida: la ayuda resta carga
    NINGUNA = "ninguna"  # movilidad, estiramientos


class MuscleRole(StrEnum):
    PRIMARIO = "primario"
    SECUNDARIO = "secundario"
    ESTABILIZADOR = "estabilizador"


# Contribución de cada rol al volumen atribuido a un músculo.
# Vive aquí y no en la base de datos (regla R15): es configuración de la
# fórmula, no un dato del catálogo. Cambiarla debe recalcular, no migrar.
ROLE_CONTRIBUTION: dict[MuscleRole, float] = {
    MuscleRole.PRIMARIO: 1.0,
    MuscleRole.SECUNDARIO: 0.5,
    MuscleRole.ESTABILIZADOR: 0.2,
}


class Strategy(StrEnum):
    REPS_LINEAL = "reps_lineal"
    DOBLE_PROGRESION = "doble_progresion"
    PESO_LINEAL = "peso_lineal"
    SERIES = "series"
    TIEMPO = "tiempo"
    VARIANTE = "variante"
    MANUAL = "manual"


class SessionStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    SKIPPED = "skipped"  # registro explícito de "no lo hice"


class SessionOrigin(StrEnum):
    PLANIFICADA = "planificada"
    ADHOC = "adhoc"


class Actor(StrEnum):
    USUARIO = "usuario"
    AGENTE = "agente"
    SISTEMA = "sistema"


class ExceptionReason(StrEnum):
    DESCANSO = "descanso"
    LESION = "lesion"
    VIAJE = "viaje"
    MOVIDO = "movido"
    OTRO = "otro"


class DayState(StrEnum):
    """Estado de cumplimiento de un día del calendario.

    PENDING es la razón de ser de este enum: distingue "aún no lo he
    registrado" de "no lo hice". Sin él, abrir la app el domingo pintaría de
    rojo toda la semana.
    """

    REST = "rest"  # ⚪ sin rutina programada
    DONE = "done"  # 🟢 sesión completa
    PARTIAL = "partial"  # 🟡 sesión parcial
    PENDING = "pending"  # 🟠 programado, sin registrar, dentro de la gracia
    MISSED = "missed"  # 🔴 programado y no realizado
    EXTRA = "extra"  # 🔵 entrenamiento sin rutina programada
    EXCUSED = "excused"  # ⚫ descanso/lesión/viaje declarado


class Tier(StrEnum):
    """Rangos del ranking muscular, de menor a mayor.

    SIN_DATOS no es el escalón más bajo: es la ausencia de escalón. Un músculo
    sin ejercicios asociados no está "débil", está "no medido" (ADR-0003).
    """

    SIN_DATOS = "sin_datos"
    IRON = "iron"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    ASCENDANT = "ascendant"
    IMMORTAL = "immortal"
    RADIANT = "radiant"


#: Rangos ordenados de menor a mayor, excluyendo SIN_DATOS.
TIER_LADDER: tuple[Tier, ...] = (
    Tier.IRON,
    Tier.BRONZE,
    Tier.SILVER,
    Tier.GOLD,
    Tier.PLATINUM,
    Tier.DIAMOND,
    Tier.ASCENDANT,
    Tier.IMMORTAL,
    Tier.RADIANT,
)


class ProgressionOutcome(StrEnum):
    """Resultado de evaluar una progresión.

    UNDETERMINED es un ciudadano de primera clase: cuando el sistema no puede
    determinar con seguridad cómo progresar, lo dice en vez de inventarlo.
    """

    READY = "ready"
    NOT_YET = "not_yet"
    UNDETERMINED = "undetermined"
    DELOAD_SUGGESTED = "deload_suggested"
