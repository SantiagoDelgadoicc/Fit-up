"""Adaptador HTTP de la política del agente.

Aquí solo vive lo que es de HTTP: leer la cabecera y envolver la comprobación
en una dependencia de FastAPI. Las reglas —qué permisos hay, cuándo se rechaza,
cuándo se hace copia previa— están en `application/services/agent.py`, porque
el servidor MCP tiene que aplicar exactamente las mismas y un adaptador no
puede depender de otro (invariante 6).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Header

from ..application.services import agent as policy
from ..domain.enums import Actor
from .deps import Settings, get_db, get_settings

#: Cabecera con la que un cliente dice quién es.
ACTOR_HEADER = "X-Fitup-Actor"

# Reexportados para que quien use el adaptador no tenga que conocer la capa de
# aplicación solo para nombrar un permiso.
DEFAULT_SCOPES = policy.DEFAULT_SCOPES
SCOPES_KEY = policy.SCOPES_KEY
Scope = policy.Scope
get_scopes = policy.get_scopes


def actor_header(
    x_fitup_actor: str | None = Header(default=None, alias=ACTOR_HEADER),
) -> Actor:
    """Actor declarado en la cabecera. Sin ella, `usuario`.

    Un valor desconocido acaba en 422 por el `Invalid` que lanza la política:
    no se degrada a `usuario`, que dejaría al agente operando de incógnito.
    """
    return policy.parse_actor(x_fitup_actor)


@dataclass(frozen=True, slots=True)
class Caller:
    """Quién llama, ya resuelto."""

    actor: Actor

    @property
    def is_agent(self) -> bool:
        return self.actor is Actor.AGENTE


def require_scope(scope: str):
    """Dependencia que exige un permiso antes de entrar al endpoint."""

    def dependency(
        actor: Actor = Depends(actor_header),
        db: sqlite3.Connection = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> Caller:
        policy.ensure_scope(db, scope, actor=actor, db_path=settings.db_path)
        return Caller(actor=actor)

    return dependency


# Dependencias ya construidas, una por permiso. Crearlas aquí y no dentro de
# cada `Depends(...)` evita fabricar una función nueva por endpoint, y deja el
# conjunto de permisos que la API usa a la vista en un solo sitio.
read = require_scope(Scope.READ)
propose = require_scope(Scope.PROPOSE)
write_sessions = require_scope(Scope.WRITE_SESSIONS)
write_routines = require_scope(Scope.WRITE_ROUTINES)
write_settings = require_scope(Scope.WRITE_SETTINGS)
