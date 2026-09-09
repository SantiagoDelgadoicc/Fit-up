"""Política del agente: quién escribe, qué se le permite y qué queda registrado.

El agente de IA es un proceso externo con control del PC (ADR-0004): puede
abrir `fitup.db`, editar esta configuración o parar el servidor. Nada de lo que
hay aquí se lo impide, y no pretende hacerlo.

Lo que sí consigue, que es el objetivo real:

1. **Saber quién hizo qué.** Sin `actor`, una escritura del agente queda
   registrada como del usuario y la traza no sirve para nada.
2. **Parar la equivocación más probable**, que es un modelo confundido
   escribiendo historial falso. Los scopes son un guardarraíl contra errores,
   nunca una frontera de seguridad.
3. **Poder volver atrás.** Antes del primer cambio de un lote se guarda una
   copia de la base.

El cliente **se declara**: ni la cabecera HTTP ni el arranque del servidor MCP
se verifican, ni podrían verificarse. Un agente que mienta diciendo ser
`usuario` esquiva los scopes, y eso está asumido. Lo que se gana es que el
agente honesto —que es el caso real— deje huella y opere dentro de unos
límites.

Esto vive en `application` y no en `api` porque **es política de negocio, no de
HTTP**: el servidor MCP tiene que aplicar exactamente las mismas reglas, y un
adaptador no puede depender de otro (invariante 6).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ...domain.enums import Actor
from ..errors import Denied, Invalid
from ..repositories import history
from . import maintenance

#: Ajuste que guarda los permisos del agente.
SCOPES_KEY = "agent_scopes"

#: Marca de la última escritura del agente, para delimitar los lotes.
LAST_WRITE_KEY = "ultima_escritura_agente"

#: Minutos de silencio tras los que la siguiente escritura abre un lote nuevo
#: y dispara una copia de seguridad.
BATCH_GAP_MINUTES = 30

#: Permisos por defecto: leer y proponer sí, escribir no (ADR-0004 §3).
#: Se activan desde Ajustes, a mano y a sabiendas.
DEFAULT_SCOPES: dict[str, bool] = {
    "read": True,
    "propose": True,
    "write_sessions": False,
    "write_routines": False,
    "write_settings": False,
}


class Scope:
    """Los permisos, como constantes: un literal mal escrito abriría el paso."""

    READ = "read"
    PROPOSE = "propose"
    WRITE_SESSIONS = "write_sessions"
    WRITE_ROUTINES = "write_routines"
    WRITE_SETTINGS = "write_settings"


def get_scopes(conn: sqlite3.Connection) -> dict[str, bool]:
    """Permisos vigentes, completados con los de por defecto.

    Se rellenan los que falten para que añadir un scope nuevo en una versión
    posterior no lo deje indefinido —y por tanto ambiguo— en una base ya
    existente.
    """
    stored = history.get_setting(conn, SCOPES_KEY) or {}
    if not isinstance(stored, dict):
        return dict(DEFAULT_SCOPES)
    return {name: bool(stored.get(name, default)) for name, default in DEFAULT_SCOPES.items()}


def parse_actor(value: str | None) -> Actor:
    """Actor declarado por el cliente. Sin valor, `usuario`.

    Uno desconocido se rechaza en vez de degradarse a `usuario`: escribirlo mal
    dejaría al agente operando de incógnito, que es justo lo que esto viene a
    evitar.
    """
    if value is None:
        return Actor.USUARIO
    try:
        return Actor(value.strip().lower())
    except ValueError:
        raise Invalid(
            f"Actor '{value}' desconocido. Valores válidos: {', '.join(a.value for a in Actor)}"
        ) from None


def _parse_instant(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def opens_new_batch(conn: sqlite3.Connection, *, now: datetime | None = None) -> bool:
    """¿Esta escritura del agente empieza un lote nuevo?

    Un lote es una ráfaga de cambios seguidos. Se corta por inactividad porque
    el agente no anuncia dónde empieza ni dónde acaba: lo que se puede medir es
    cuánto tiempo lleva sin tocar nada.
    """
    last = _parse_instant(history.get_setting(conn, LAST_WRITE_KEY))
    if last is None:
        return True
    reference = now or datetime.now(UTC)
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return (reference - last).total_seconds() >= BATCH_GAP_MINUTES * 60


def mark_write(conn: sqlite3.Connection, *, now: datetime | None = None) -> None:
    history.set_setting(conn, LAST_WRITE_KEY, (now or datetime.now(UTC)).isoformat())


def ensure_scope(
    conn: sqlite3.Connection,
    scope: str,
    *,
    actor: Actor,
    db_path: Path | None = None,
) -> None:
    """Comprueba un permiso **solo si quien llama es el agente**, y prepara el lote.

    Al usuario no se le piden permisos: es el dueño de sus datos y actúa desde
    su propia interfaz.

    Un rechazo se deja escrito con `result='rechazado'`. Un intento bloqueado
    dice más que uno permitido: es la señal de que el agente está intentando
    algo que no se esperaba de él.

    `db_path` solo hace falta para escrituras, que son las que disparan la
    copia previa; sin él se omite la copia y se dice en el registro, en vez de
    escribir en silencio sin red.
    """
    if actor is not Actor.AGENTE:
        return

    if not get_scopes(conn).get(scope, False):
        history.audit(
            conn,
            actor=actor,
            action=f"scope:{scope}",
            payload={"scope": scope},
            result="rechazado",
            error="permiso desactivado",
        )
        conn.commit()
        raise Denied(
            f"El permiso '{scope}' está desactivado para el agente. "
            f"Se activa en Ajustes, o con PUT /api/ajustes/{SCOPES_KEY}."
        )

    if not scope.startswith("write_"):
        return

    # La copia se hace **antes** de tocar nada, y solo al abrir lote: una por
    # escritura llenaría el disco durante una ráfaga.
    if opens_new_batch(conn):
        if db_path is not None:
            maintenance.backup_before_agent_batch(conn, db_path)
        else:
            history.audit(
                conn,
                actor=actor,
                action="backup_lote_agente",
                result="error",
                error="sin ruta de base de datos: lote sin copia previa",
            )
    mark_write(conn)
    conn.commit()
