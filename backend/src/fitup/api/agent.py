"""Quién escribe, qué se le permite y qué queda registrado.

El agente de IA es un proceso externo con control del PC (ADR-0004): puede
abrir `fitup.db`, editar esta configuración o parar el servidor. Nada de lo
que hay aquí se lo impide, y no pretende hacerlo.

Lo que sí consigue, que es el objetivo real:

1. **Saber quién hizo qué.** Sin `actor`, una escritura del agente queda
   registrada como tuya y la traza no sirve para nada.
2. **Parar la equivocación más probable**, que es un modelo confundido
   escribiendo historial falso. Los scopes son un guardarraíl contra errores,
   nunca una frontera de seguridad.
3. **Poder volver atrás.** Antes del primer cambio de un lote del agente se
   guarda una copia de la base.

El cliente **se declara**: la cabecera no se verifica ni podría verificarse.
Un agente que mienta diciendo ser `usuario` esquiva los scopes, y eso está
asumido. Lo que se gana es que el agente honesto —que es el caso real— deje
huella y opere dentro de unos límites.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status

from ..application.repositories import history
from ..application.services import maintenance
from ..domain.enums import Actor
from .deps import Settings, get_db, get_settings

#: Cabecera con la que un cliente dice quién es.
ACTOR_HEADER = "X-Fitup-Actor"

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


def actor_header(
    x_fitup_actor: str | None = Header(default=None, alias=ACTOR_HEADER),
) -> Actor:
    """Actor declarado por el cliente. Sin cabecera, `usuario`.

    Un valor desconocido se rechaza en vez de degradarse a `usuario`: escribir
    mal la cabecera dejaría al agente operando de incógnito, que es justo lo
    que esto viene a evitar.
    """
    if x_fitup_actor is None:
        return Actor.USUARIO
    try:
        return Actor(x_fitup_actor.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Actor '{x_fitup_actor}' desconocido. "
                f"Valores válidos: {', '.join(a.value for a in Actor)}"
            ),
        ) from None


@dataclass(frozen=True, slots=True)
class Caller:
    """Quién llama y con qué permiso, ya resuelto."""

    actor: Actor

    @property
    def is_agent(self) -> bool:
        return self.actor is Actor.AGENTE


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def opens_new_batch(conn: sqlite3.Connection, *, now: datetime | None = None) -> bool:
    """¿Esta escritura del agente empieza un lote nuevo?

    Un lote es una ráfaga de cambios seguidos. Se corta por inactividad porque
    el agente no anuncia dónde empieza ni dónde acaba: lo que se puede medir
    es cuánto tiempo lleva sin tocar nada.
    """
    last = _parse(history.get_setting(conn, LAST_WRITE_KEY))
    if last is None:
        return True
    reference = now or datetime.now(UTC)
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return (reference - last).total_seconds() >= BATCH_GAP_MINUTES * 60


def mark_write(conn: sqlite3.Connection, *, now: datetime | None = None) -> None:
    history.set_setting(conn, LAST_WRITE_KEY, (now or datetime.now(UTC)).isoformat())


def require_scope(scope: str):
    """Dependencia que exige un permiso **solo si quien llama es el agente**.

    Al usuario no se le piden permisos: es el dueño de sus datos y actúa desde
    su propia interfaz.

    Cuando rechaza, lo deja escrito en el registro con `result='rechazado'`.
    Un intento bloqueado dice más que uno permitido: es la señal de que el
    agente está intentando algo que no se esperaba de él.
    """

    def dependency(
        actor: Actor = Depends(actor_header),
        db: sqlite3.Connection = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> Caller:
        caller = Caller(actor=actor)
        if not caller.is_agent:
            return caller

        if not get_scopes(db).get(scope, False):
            history.audit(
                db,
                actor=actor,
                action=f"scope:{scope}",
                payload={"scope": scope},
                result="rechazado",
                error="permiso desactivado",
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"El permiso '{scope}' está desactivado para el agente. "
                    f"Se activa en Ajustes, o con PUT /api/ajustes/{SCOPES_KEY}."
                ),
            )

        # La copia se hace **antes** de tocar nada, y solo al abrir lote: una
        # por escritura llenaría el disco durante una ráfaga.
        if scope.startswith("write_"):
            if opens_new_batch(db):
                maintenance.backup_before_agent_batch(db, settings.db_path)
            mark_write(db)
            db.commit()

        return caller

    return dependency


# Dependencias ya construidas, una por permiso. Crearlas aquí y no dentro de
# cada `Depends(...)` evita fabricar una función nueva por endpoint, y deja el
# conjunto de permisos que la API usa a la vista en un solo sitio.
read = require_scope(Scope.READ)
propose = require_scope(Scope.PROPOSE)
write_sessions = require_scope(Scope.WRITE_SESSIONS)
write_routines = require_scope(Scope.WRITE_ROUTINES)
write_settings = require_scope(Scope.WRITE_SETTINGS)
