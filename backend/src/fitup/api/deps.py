"""Configuración, conexión y autenticación del adaptador HTTP."""

from __future__ import annotations

import os
import secrets
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request, status

from ..infrastructure.db import migrator
from ..infrastructure.db.connection import connect

DEFAULT_DB = Path("data/fitup.db")
TOKEN_FILE_NAME = "token"


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    token: str | None
    #: Con bind a 0.0.0.0 la app queda expuesta en la red doméstica y el token
    #: pasa a ser obligatorio: ahí sí es una frontera real (ADR-0004).
    require_token: bool = True


def load_settings(
    *, db_path: Path | None = None, token: str | None = None, require_token: bool = True
) -> Settings:
    path = db_path or Path(os.environ.get("FITUP_DB", DEFAULT_DB))
    return Settings(
        db_path=path,
        token=token or os.environ.get("FITUP_TOKEN"),
        require_token=require_token,
    )


def ensure_token(config_dir: Path) -> str:
    """Token persistente, generado la primera vez.

    Se guarda en disco en vez de pedirlo al usuario: un token que hay que
    inventar y recordar acaba siendo `1234`.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / TOKEN_FILE_NAME
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    path.write_text(token, encoding="utf-8")
    return token


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """Una conexion por peticion.

    FastAPI ejecuta los endpoints sincronos en un threadpool y SQLite prohibe
    usar una conexion desde otro hilo. Compartir una global obligaria a
    `check_same_thread=False` y a serializar a mano; abrir por peticion cuesta
    microsegundos, evita estado mutable compartido y deja que cada transaccion
    quede aislada por si sola.
    """
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def today() -> Date:
    """Fecha local de hoy.

    Existe como dependencia para poder inyectarla en los tests: el dominio ya
    no consulta el reloj, y la API tampoco debería hacerlo a escondidas.
    """
    return Date.today()


def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Comprueba el token si la instancia lo exige.

    Protege frente a otros dispositivos de la red doméstica. **No** frente al
    agente de IA local, que tiene control del PC y podría leer el fichero del
    token: esa no es la frontera que este control defiende (ADR-0004).
    """
    if not settings.require_token or settings.token is None:
        return

    provided = None
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    elif authorization:
        provided = authorization.strip()

    if provided is None or not secrets.compare_digest(provided, settings.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso ausente o inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def open_database(path: Path) -> sqlite3.Connection:
    """Abre la base y aplica migraciones pendientes."""
    conn = connect(path)
    migrator.migrate(conn)
    return conn
